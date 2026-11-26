"""Local Agent CLI Drivers (agy / codex) for AG-SLG-FrameWork."""

import abc
import asyncio
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional


@dataclass
class AgentEvent:
    event_type: str  # text_delta, tool_call_start, tool_call_end, state_delta, done, error
    data: Dict[str, Any] = field(default_factory=dict)
    raw: Optional[Dict[str, Any]] = None


class BaseAgentDriver(abc.ABC):
    """Abstract interface for local Agent CLI drivers."""

    @abc.abstractmethod
    async def run_stream(
        self,
        prompt: str,
        conversation_id: Optional[str] = None,
        cwd: Optional[Path] = None,
    ) -> AsyncIterator[AgentEvent]:
        """Run agent with prompt and yield AgentEvent stream."""
        raise NotImplementedError


def _prepare_command(cmd: List[str]) -> List[str]:
    """On Windows, wrap .cmd/.bat shims (e.g. npx.cmd) so create_subprocess_exec can run them."""
    if os.name != "nt" or not cmd:
        return list(cmd)
    resolved = shutil.which(cmd[0]) or cmd[0]
    if resolved.lower().endswith((".cmd", ".bat")):
        comspec = os.environ.get("COMSPEC") or "cmd.exe"
        return [comspec, "/d", "/c", resolved, *cmd[1:]]
    return [resolved, *cmd[1:]]


class AcpDriver(BaseAgentDriver):
    """Persistent stdio ACP (Agent Client Protocol, JSON-RPC 2.0) driver."""

    def __init__(
        self,
        cmd: List[str],
        env: Optional[Dict[str, str]] = None,
        handshake_timeout: float = 30.0,
        prompt_timeout: float = 600.0,
    ):
        self.cmd = list(cmd)
        self.env = dict(env) if env else None
        self.handshake_timeout = handshake_timeout
        self.prompt_timeout = prompt_timeout

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._start_lock: Optional[asyncio.Lock] = None
        self._write_lock: Optional[asyncio.Lock] = None
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._reader_task: Optional[asyncio.Task[None]] = None
        self._stderr_task: Optional[asyncio.Task[None]] = None
        self._next_id = 1
        self._pending: Dict[int, asyncio.Future[Dict[str, Any]]] = {}
        self._session_queues: Dict[str, asyncio.Queue[Optional[Dict[str, Any]]]] = {}
        self._known_sessions: set[str] = set()
        self._last_stderr = ""

    def _reset_loop_state(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._start_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()
        self._proc = None
        self._reader_task = None
        self._stderr_task = None
        self._next_id = 1
        self._pending = {}
        self._session_queues = {}
        self._known_sessions = set()
        self._last_stderr = ""

    async def aclose(self) -> None:
        proc = self._proc
        tasks = [t for t in (self._reader_task, self._stderr_task) if t and not t.done()]
        self._proc = None
        self._reader_task = None
        self._stderr_task = None
        self._known_sessions.clear()
        if proc and proc.returncode is None:
            if proc.stdin:
                try:
                    proc.stdin.close()
                except Exception:
                    pass
            if os.name == "nt":
                # cmd.exe /d /c wrappers leave child node processes behind on plain terminate()
                try:
                    await asyncio.to_thread(
                        subprocess.run,
                        ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except Exception:
                    pass
            if proc.returncode is None:
                proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=3.0)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
        for t in tasks:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass

    async def _write_json(self, payload: Dict[str, Any]) -> None:
        assert self._proc is not None and self._proc.stdin is not None
        assert self._write_lock is not None
        raw = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        async with self._write_lock:
            self._proc.stdin.write(raw)
            await self._proc.stdin.drain()

    async def _rpc_call(
        self, method: str, params: Dict[str, Any], timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        assert self._loop is not None
        req_id = self._next_id
        self._next_id += 1
        fut: asyncio.Future[Dict[str, Any]] = self._loop.create_future()
        self._pending[req_id] = fut
        try:
            await self._write_json(
                {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
            )
            resp = await asyncio.wait_for(fut, timeout=timeout or self.handshake_timeout)
        except BaseException:
            self._pending.pop(req_id, None)
            raise
        if "error" in resp and resp["error"] is not None:
            err = resp["error"]
            msg = err.get("message") if isinstance(err, dict) else str(err)
            raise RuntimeError(msg or f"ACP error on {method}")
        return resp.get("result") or {}

    async def _handle_server_request(self, msg: Dict[str, Any]) -> None:
        req_id = msg.get("id")
        method = msg.get("method")
        if method == "session/request_permission":
            options = (msg.get("params") or {}).get("options") or []
            chosen = next(
                (o for o in options if isinstance(o, dict) and str(o.get("kind", "")).startswith("allow")),
                options[0] if options and isinstance(options[0], dict) else None,
            )
            outcome = (
                {"outcome": "selected", "optionId": chosen["optionId"]}
                if chosen and chosen.get("optionId")
                else {"outcome": "cancelled"}
            )
            await self._write_json({"jsonrpc": "2.0", "id": req_id, "result": {"outcome": outcome}})
            return

        await self._write_json(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Unsupported client method: {method}"},
            }
        )

    async def _drain_stderr(self, proc: asyncio.subprocess.Process) -> None:
        if not proc.stderr:
            return
        try:
            while True:
                chunk = await proc.stderr.read(2048)
                if not chunk:
                    break
                text = chunk.decode("utf-8", errors="replace").strip()
                if text:
                    self._last_stderr = (self._last_stderr + "\n" + text)[-4096:].strip()
        except asyncio.CancelledError:
            raise
        except Exception:
            pass

    async def _read_loop(self, proc: asyncio.subprocess.Process) -> None:
        try:
            assert proc.stdout is not None
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                line_str = line.decode("utf-8", errors="replace").strip()
                if not line_str:
                    continue
                try:
                    msg = json.loads(line_str)
                except json.JSONDecodeError:
                    continue
                if not isinstance(msg, dict):
                    continue

                if "id" in msg and ("result" in msg or "error" in msg):
                    fut = self._pending.pop(msg["id"], None)
                    if fut and not fut.done():
                        fut.set_result(msg)
                elif "id" in msg and "method" in msg:
                    asyncio.create_task(self._handle_server_request(msg))
                elif msg.get("method") == "session/update":
                    params = msg.get("params") or {}
                    sid = params.get("sessionId")
                    q = self._session_queues.get(sid)
                    if q is not None:
                        q.put_nowait(params.get("update") or {})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._last_stderr = str(exc)
        finally:
            if self._stderr_task and not self._stderr_task.done():
                await asyncio.sleep(0.05)
            exit_err = RuntimeError(self._last_stderr or "ACP process exited")
            for fut in list(self._pending.values()):
                if not fut.done():
                    fut.set_exception(exit_err)
            self._pending.clear()
            for q in list(self._session_queues.values()):
                q.put_nowait(None)
            self._known_sessions.clear()

    async def _ensure_started(self) -> None:
        loop = asyncio.get_running_loop()
        if self._loop is not loop:
            self._reset_loop_state(loop)
        assert self._start_lock is not None
        async with self._start_lock:
            if self._proc is not None and self._proc.returncode is None:
                return
            self._pending.clear()
            self._known_sessions.clear()
            self._last_stderr = ""
            spawn_env = None
            if self.env is not None:
                spawn_env = {**os.environ, **self.env}
            spawn_cmd = _prepare_command(self.cmd)
            self._proc = await asyncio.create_subprocess_exec(
                *spawn_cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=spawn_env,
                # ACP lines (e.g. available_commands_update) frequently exceed asyncio's 64KB default.
                limit=10 * 1024 * 1024,
            )
            self._stderr_task = asyncio.create_task(self._drain_stderr(self._proc))
            self._reader_task = asyncio.create_task(self._read_loop(self._proc))
            try:
                await self._rpc_call(
                    "initialize",
                    {
                        "protocolVersion": 1,
                        "clientCapabilities": {},
                        "clientInfo": {"name": "ag-slg-framework", "version": "0.1.0"},
                    },
                    timeout=self.handshake_timeout,
                )
            except Exception:
                await self.aclose()
                raise

    async def _acquire_session(self, conversation_id: Optional[str], work_dir: str) -> str:
        if conversation_id:
            if conversation_id in self._known_sessions:
                return conversation_id
            for method in ("session/resume", "session/load"):
                try:
                    await self._rpc_call(
                        method,
                        {"sessionId": conversation_id, "cwd": work_dir, "mcpServers": []},
                    )
                    self._known_sessions.add(conversation_id)
                    return conversation_id
                except Exception:
                    continue

        res = await self._rpc_call("session/new", {"cwd": work_dir, "mcpServers": []})
        sid = res["sessionId"]
        self._known_sessions.add(sid)
        return sid

    async def run_stream(
        self,
        prompt: str,
        conversation_id: Optional[str] = None,
        cwd: Optional[Path] = None,
    ) -> AsyncIterator[AgentEvent]:
        try:
            await self._ensure_started()
            work_dir = str(cwd.resolve()) if cwd else os.getcwd()
            sid = await self._acquire_session(conversation_id, work_dir)
        except Exception as exc:
            # asyncio.TimeoutError etc. stringify to "", which surfaced as an unhelpful blank error.
            detail = str(exc).strip() or (
                f"Agent 启动/握手超时（>{self.handshake_timeout:.0f}s）"
                if isinstance(exc, asyncio.TimeoutError)
                else type(exc).__name__
            )
            yield AgentEvent(event_type="error", data={"error": detail})
            return

        assert self._loop is not None
        q: asyncio.Queue[Optional[Dict[str, Any]]] = asyncio.Queue()
        self._session_queues[sid] = q
        req_id = self._next_id
        self._next_id += 1
        prompt_fut: asyncio.Future[Dict[str, Any]] = self._loop.create_future()
        self._pending[req_id] = prompt_fut
        prompt_fut.add_done_callback(lambda _f: q.put_nowait({"_acp_done": True}))

        full_text_accum: List[str] = []
        started_tools: set[str] = set()
        completed = False

        try:
            await self._write_json(
                {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "method": "session/prompt",
                    "params": {
                        "sessionId": sid,
                        "prompt": [{"type": "text", "text": prompt}],
                    },
                }
            )

            while True:
                item = await asyncio.wait_for(q.get(), timeout=self.prompt_timeout)
                if item is None:
                    if not completed:
                        yield AgentEvent(
                            event_type="error",
                            data={"error": self._last_stderr or "ACP process exited unexpectedly", "conversation_id": sid},
                        )
                    break

                if item.get("_acp_done"):
                    completed = True
                    exc = prompt_fut.exception()
                    if exc is not None:
                        yield AgentEvent(event_type="error", data={"error": str(exc), "conversation_id": sid})
                        break
                    resp = prompt_fut.result()
                    if "error" in resp and resp["error"] is not None:
                        err = resp["error"]
                        err_msg = err.get("message") if isinstance(err, dict) else str(err)
                        yield AgentEvent(
                            event_type="error",
                            data={"error": err_msg or "ACP session/prompt error", "conversation_id": sid},
                            raw=resp,
                        )
                    else:
                        yield AgentEvent(
                            event_type="done",
                            data={
                                "conversation_id": sid,
                                "response": "".join(full_text_accum),
                                "status": "SUCCESS",
                            },
                            raw=resp,
                        )
                    break

                kind = item.get("sessionUpdate")
                if kind == "agent_message_chunk":
                    content = item.get("content") or {}
                    text_delta = content.get("text") if content.get("type") == "text" else None
                    if text_delta:
                        full_text_accum.append(text_delta)
                        yield AgentEvent(
                            event_type="text_delta",
                            data={"text": text_delta, "conversation_id": sid},
                            raw=item,
                        )
                elif kind in ("tool_call", "tool_call_update"):
                    call_id = item.get("toolCallId") or f"call_{len(started_tools)}"
                    tool_name = item.get("title") or item.get("kind") or "tool"
                    status = item.get("status")
                    if kind == "tool_call" and call_id not in started_tools:
                        started_tools.add(call_id)
                        yield AgentEvent(
                            event_type="tool_call_start",
                            data={"call_id": call_id, "tool_name": tool_name, "args": item.get("rawInput") or {}},
                            raw=item,
                        )
                    if status in ("completed", "failed"):
                        started_tools.discard(call_id)
                        yield AgentEvent(
                            event_type="tool_call_end",
                            data={"call_id": call_id, "tool_name": tool_name, "result": item.get("rawOutput")},
                            raw=item,
                        )
        except Exception as exc:
            yield AgentEvent(event_type="error", data={"error": str(exc), "conversation_id": sid})
        finally:
            self._pending.pop(req_id, None)
            self._session_queues.pop(sid, None)
            if not completed and self._proc is not None and self._proc.returncode is None:
                try:
                    await self._write_json(
                        {"jsonrpc": "2.0", "method": "session/cancel", "params": {"sessionId": sid}}
                    )
                except Exception:
                    pass


class AgyDriver(AcpDriver):
    """ACP Driver for Google Antigravity CLI (`agy acp`)."""

    def __init__(self, executable: Optional[str] = None):
        exe = executable or shutil.which("agy") or "agy"
        super().__init__(cmd=[exe, "acp", "--dangerously-skip-permissions"])


class CodexDriver(AcpDriver):
    """ACP Driver for Codex (`codex-acp` / `npx @agentclientprotocol/codex-acp`)."""

    def __init__(self, executable: Optional[str] = None):
        codex_acp = executable or os.getenv("CODEX_ACP_BIN") or shutil.which("codex-acp")
        if codex_acp:
            cmd = [codex_acp]
            handshake_timeout = 30.0
        else:
            cmd = [shutil.which("npx") or "npx", "--yes", "@agentclientprotocol/codex-acp"]
            # First run downloads the package via npx, which can exceed the default 30s handshake.
            handshake_timeout = 120.0

        env: Dict[str, str] = {}
        if not os.getenv("CODEX_PATH"):
            codex_bin = shutil.which("codex")
            if codex_bin:
                env["CODEX_PATH"] = codex_bin
        super().__init__(cmd=cmd, env=env or None, handshake_timeout=handshake_timeout)

class MockAgentDriver(BaseAgentDriver):
    """In-memory driver for deterministic unit tests and offline testing."""

    def __init__(self, mock_responses: Optional[List[str]] = None):
        self.mock_responses = mock_responses or [
            "你推开沉重的雕花木门，门轴发出酸涩的呻吟声。\n\n"
            "```state_delta\n"
            '{"current_scene": "drawing_room", "hp_delta": 0, "variables": {"butler_trust": 15}}\n'
            "```\n"
        ]
        self._counter = 0

    async def run_stream(
        self,
        prompt: str,
        conversation_id: Optional[str] = None,
        cwd: Optional[Path] = None,
    ) -> AsyncIterator[AgentEvent]:
        active_id = conversation_id or "mock-conv-123"
        resp = self.mock_responses[self._counter % len(self.mock_responses)]
        self._counter += 1

        # Stream words
        words = resp.split(" ")
        for i, word in enumerate(words):
            chunk = word if i == len(words) - 1 else word + " "
            yield AgentEvent(
                event_type="text_delta",
                data={"text": chunk, "conversation_id": active_id},
            )
            await asyncio.sleep(0.01)

        yield AgentEvent(
            event_type="done",
            data={"conversation_id": active_id, "response": resp, "status": "SUCCESS"},
        )
