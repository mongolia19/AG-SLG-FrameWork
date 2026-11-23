"""Local Agent CLI Drivers (agy / codex) for AG-SLG-FrameWork."""

import abc
import asyncio
import json
import os
import re
import shutil
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


class AgyDriver(BaseAgentDriver):
    """Driver for Google Antigravity CLI (`agy`).

    Executes:
    agy -p "<prompt>" --output-format stream-json [--conversation <id>]
    """

    def __init__(self, executable: Optional[str] = None):
        self.executable = executable or shutil.which("agy") or "agy"

    async def run_stream(
        self,
        prompt: str,
        conversation_id: Optional[str] = None,
        cwd: Optional[Path] = None,
    ) -> AsyncIterator[AgentEvent]:
        cmd = [
            self.executable,
            "-p",
            prompt,
            "--output-format",
            "stream-json",
            "--dangerously-skip-permissions",
        ]
        if conversation_id:
            cmd.extend(["--conversation", conversation_id])

        work_dir = str(cwd) if cwd else None

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=work_dir,
        )

        active_conv_id = conversation_id
        full_text_accum = []

        try:
            assert process.stdout is not None
            while True:
                line = await process.stdout.readline()
                if not line:
                    break

                line_str = line.decode("utf-8", errors="replace").strip()
                if not line_str:
                    continue

                try:
                    payload = json.loads(line_str)
                except json.JSONDecodeError:
                    continue

                event_name = payload.get("event")

                if event_name == "init":
                    active_conv_id = payload.get("conversation_id")

                elif event_name == "step_update":
                    step = payload.get("step_update", {})
                    step_type = step.get("step_type")

                    if step_type == "agent_response":
                        text_delta = step.get("text_delta")
                        if text_delta:
                            full_text_accum.append(text_delta)
                            yield AgentEvent(
                                event_type="text_delta",
                                data={"text": text_delta, "conversation_id": active_conv_id},
                                raw=payload,
                            )

                    elif step_type == "error_message":
                        err_text = step.get("message") or step.get("text") or "Agent error"
                        yield AgentEvent(
                            event_type="error",
                            data={"error": err_text, "conversation_id": active_conv_id},
                            raw=payload,
                        )

                    elif step_type == "tool_call":
                        tool_name = step.get("tool_name", "tool")
                        tool_args = step.get("tool_args", {})
                        call_id = step.get("tool_call_id", f"call_{len(full_text_accum)}")
                        state = step.get("state")
                        if state == "ACTIVE":
                            yield AgentEvent(
                                event_type="tool_call_start",
                                data={"call_id": call_id, "tool_name": tool_name, "args": tool_args},
                                raw=payload,
                            )
                        elif state == "DONE":
                            yield AgentEvent(
                                event_type="tool_call_end",
                                data={"call_id": call_id, "tool_name": tool_name, "result": step.get("tool_result")},
                                raw=payload,
                            )

                elif event_name == "result":
                    res = payload.get("result", {})
                    if res.get("status") == "ERROR":
                        yield AgentEvent(
                            event_type="error",
                            data={
                                "conversation_id": active_conv_id,
                                "error": res.get("error", "Agent execution error"),
                                "status": "ERROR",
                            },
                            raw=payload,
                        )
                    else:
                        yield AgentEvent(
                            event_type="done",
                            data={
                                "conversation_id": active_conv_id,
                                "response": res.get("response", "".join(full_text_accum)),
                                "status": res.get("status", "SUCCESS"),
                            },
                            raw=payload,
                        )

            await process.wait()
            if process.returncode != 0 and not full_text_accum:
                stderr_text = ""
                if process.stderr:
                    err_bytes = await process.stderr.read()
                    stderr_text = err_bytes.decode("utf-8", errors="replace").strip()
                yield AgentEvent(
                    event_type="error",
                    data={
                        "error": stderr_text or f"Agent CLI exited with code {process.returncode}",
                        "exit_code": process.returncode,
                    },
                )

        except Exception as e:
            yield AgentEvent(event_type="error", data={"error": str(e)})
            try:
                process.kill()
            except Exception:
                pass


class CodexDriver(BaseAgentDriver):
    """Fallback driver for Codex CLI (`codex`).

    Executes:
    codex exec --json ...
    """

    def __init__(self, executable: Optional[str] = None):
        self.executable = executable or shutil.which("codex") or "codex"

    async def run_stream(
        self,
        prompt: str,
        conversation_id: Optional[str] = None,
        cwd: Optional[Path] = None,
    ) -> AsyncIterator[AgentEvent]:
        # shortcut: minimal codex driver fallback, upgrade when codex specific params needed
        cmd = [self.executable, "exec", "--json"]
        if cwd:
            cmd.extend(["--cd", str(cwd)])
        cmd.append(prompt)

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd) if cwd else None,
        )

        try:
            assert process.stdout is not None
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                line_str = line.decode("utf-8", errors="replace").strip()
                if not line_str:
                    continue
                try:
                    payload = json.loads(line_str)
                    msg = payload.get("msg", {})
                    if "text" in msg:
                        yield AgentEvent(event_type="text_delta", data={"text": msg["text"]})
                except Exception:
                    yield AgentEvent(event_type="text_delta", data={"text": line_str + "\n"})

            await process.wait()
            yield AgentEvent(event_type="done", data={"status": "SUCCESS"})
        except Exception as e:
            yield AgentEvent(event_type="error", data={"error": str(e)})


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
