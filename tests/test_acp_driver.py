import json
import sys
import textwrap
from pathlib import Path

import pytest
from ag_ui.core import RunAgentInput, TextInputContent, UserMessage

from server.agent_driver import AcpDriver, AgyDriver, BaseAgentDriver, CodexDriver, AgentEvent
from server.agui_bridge import AGUIBridge
from server.scenario_manager import ScenarioManager


FAKE_ACP_SERVER = textwrap.dedent(
    """
    import json, sys

    sessions = {}
    counter = 0
    crash_next = False

    def send(obj):
        sys.stdout.write(json.dumps(obj) + "\\n")
        sys.stdout.flush()

    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        msg = json.loads(raw)
        method = msg.get("method")
        req_id = msg.get("id")
        params = msg.get("params") or {}

        if method == "initialize":
            send({"jsonrpc": "2.0", "id": req_id, "result": {"protocolVersion": 1}})
        elif method == "session/new":
            import os
            if not os.path.isabs(params.get("cwd", "")):
                send({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": "cwd must be an absolute path"}})
                continue
            counter += 1
            sid = f"acp-sess-{counter}"
            sessions[sid] = []
            send({"jsonrpc": "2.0", "id": req_id, "result": {"sessionId": sid}})
        elif method == "session/resume":
            import os
            if not os.path.isabs(params.get("cwd", "")):
                send({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": "cwd must be an absolute path"}})
                continue
            sid = params.get("sessionId")
            if sid == "resumable-sess":
                sessions[sid] = ["prior-context"]
                send({"jsonrpc": "2.0", "id": req_id, "result": {"sessionId": sid}})
            else:
                send({"jsonrpc": "2.0", "id": req_id, "error": {"code": -32002, "message": "not found"}})
        elif method == "session/prompt":
            sid = params["sessionId"]
            text = params["prompt"][0]["text"]
            if text == "CRASH_NOW":
                sys.stderr.write("simulated acp crash\\n")
                sys.stderr.flush()
                sys.exit(2)

            # Emit >64KB notification to verify large-line buffering
            send({
                "jsonrpc": "2.0",
                "method": "session/update",
                "params": {
                    "sessionId": sid,
                    "update": {
                        "sessionUpdate": "available_commands_update",
                        "availableCommands": [{"name": "pad", "description": "x" * 80000}],
                    },
                },
            })

            if text == "NEED_PERM":
                send({
                    "jsonrpc": "2.0",
                    "id": 9001,
                    "method": "session/request_permission",
                    "params": {
                        "sessionId": sid,
                        "options": [
                            {"optionId": "reject", "kind": "reject_once"},
                            {"optionId": "allow", "kind": "allow_once"},
                        ],
                    },
                })
                perm_raw = sys.stdin.readline()
                perm_resp = json.loads(perm_raw)
                chosen = perm_resp["result"]["outcome"]["optionId"]
                send({
                    "jsonrpc": "2.0",
                    "method": "session/update",
                    "params": {
                        "sessionId": sid,
                        "update": {
                            "sessionUpdate": "agent_message_chunk",
                            "content": {"type": "text", "text": f"perm={chosen}"},
                        },
                    },
                })
            else:
                send({
                    "jsonrpc": "2.0",
                    "method": "session/update",
                    "params": {
                        "sessionId": sid,
                        "update": {
                            "sessionUpdate": "tool_call",
                            "toolCallId": "tc-1",
                            "title": "read_scene",
                            "status": "in_progress",
                        },
                    },
                })
                send({
                    "jsonrpc": "2.0",
                    "method": "session/update",
                    "params": {
                        "sessionId": sid,
                        "update": {
                            "sessionUpdate": "tool_call_update",
                            "toolCallId": "tc-1",
                            "title": "read_scene",
                            "status": "completed",
                        },
                    },
                })
                sessions.setdefault(sid, []).append(text)
                history_str = "|".join(sessions[sid])
                send({
                    "jsonrpc": "2.0",
                    "method": "session/update",
                    "params": {
                        "sessionId": sid,
                        "update": {
                            "sessionUpdate": "agent_message_chunk",
                            "content": {"type": "text", "text": f"echo:{history_str}"},
                        },
                    },
                })

            send({"jsonrpc": "2.0", "id": req_id, "result": {"stopReason": "end_turn"}})
    """
).strip()


@pytest.mark.asyncio
async def test_acp_driver_multiturn_tool_calls_large_line_and_permissions():
    driver = AcpDriver(cmd=[sys.executable, "-u", "-c", FAKE_ACP_SERVER])
    try:
        # Turn 1: new session + >64KB notification + tool_call + text_delta
        events1 = [ev async for ev in driver.run_stream("hello", cwd=Path("."))]
        types1 = [e.event_type for e in events1]
        assert types1 == ["tool_call_start", "tool_call_end", "text_delta", "done"]
        conv_id = events1[-1].data["conversation_id"]
        assert conv_id == "acp-sess-1"
        assert events1[-1].data["response"] == "echo:hello"

        # Turn 2: reuses the exact same ACP session without creating a new one
        events2 = [ev async for ev in driver.run_stream("world", conversation_id=conv_id)]
        assert events2[-1].event_type == "done"
        assert events2[-1].data["conversation_id"] == conv_id
        assert events2[-1].data["response"] == "echo:hello|world"

        # Turn 3: server-initiated session/request_permission auto-approved
        events3 = [ev async for ev in driver.run_stream("NEED_PERM", conversation_id=conv_id)]
        assert events3[-1].event_type == "done"
        assert events3[-1].data["response"] == "perm=allow"
    finally:
        await driver.aclose()


@pytest.mark.asyncio
async def test_acp_driver_resume_and_crash_recovery():
    driver = AcpDriver(cmd=[sys.executable, "-u", "-c", FAKE_ACP_SERVER])
    try:
        # Resume existing session id across a fresh driver instance
        events1 = [ev async for ev in driver.run_stream("follow-up", conversation_id="resumable-sess")]
        assert events1[-1].event_type == "done"
        assert events1[-1].data["conversation_id"] == "resumable-sess"
        assert events1[-1].data["response"] == "echo:prior-context|follow-up"

        # Process crash emits error instead of hanging, then auto-recovers on next call
        crash_events = [ev async for ev in driver.run_stream("CRASH_NOW", conversation_id="resumable-sess")]
        assert crash_events[-1].event_type == "error"
        assert "simulated acp crash" in crash_events[-1].data["error"]

        recovered = [ev async for ev in driver.run_stream("after-crash")]
        assert recovered[-1].event_type == "done"
        assert recovered[-1].data["response"] == "echo:after-crash"
    finally:
        await driver.aclose()


def test_agy_and_codex_driver_acp_commands(monkeypatch):
    monkeypatch.setattr("server.agent_driver.shutil.which", lambda name: f"/mock/bin/{name}")
    agy = AgyDriver()
    assert agy.cmd == ["/mock/bin/agy", "acp", "--dangerously-skip-permissions"]

    monkeypatch.delenv("CODEX_ACP_BIN", raising=False)
    monkeypatch.delenv("CODEX_PATH", raising=False)
    codex = CodexDriver()
    assert codex.cmd == ["/mock/bin/codex-acp"]
    assert codex.env == {"CODEX_PATH": "/mock/bin/codex"}

    # Fallback to npx when codex-acp binary is absent
    monkeypatch.setattr(
        "server.agent_driver.shutil.which",
        lambda name: None if name == "codex-acp" else f"/mock/bin/{name}",
    )
    codex_npx = CodexDriver()
    assert codex_npx.cmd == ["/mock/bin/npx", "--yes", "@agentclientprotocol/codex-acp"]
    assert codex_npx.env == {"CODEX_PATH": "/mock/bin/codex"}


@pytest.mark.asyncio
async def test_stream_studio_reuses_conversation_id_across_turns(tmp_path, monkeypatch):
    seen_conv_ids = []

    class TrackingDriver(BaseAgentDriver):
        async def run_stream(self, prompt, conversation_id=None, cwd=None):
            seen_conv_ids.append(conversation_id)
            sid = conversation_id or "studio-acp-1"
            yield AgentEvent(event_type="text_delta", data={"text": "ok", "conversation_id": sid})
            yield AgentEvent(event_type="done", data={"conversation_id": sid, "status": "SUCCESS"})

    monkeypatch.setattr(AGUIBridge, "_studio_sessions_file", lambda self: tmp_path / "_studio_sessions.json")
    bridge = AGUIBridge(scenario_mgr=ScenarioManager(), driver=TrackingDriver())

    for idx in range(2):
        inp = RunAgentInput(
            thread_id="studio-thread-fixed",
            run_id=f"run-{idx}",
            messages=[
                UserMessage(id=f"m-{idx}", role="user", content=[TextInputContent(text=f"turn {idx}")])
            ],
            forwarded_props={"scenario_id": "black_crow_manor"},
        )
        chunks = [c async for c in bridge.stream_studio(inp)]
        assert any("RUN_FINISHED" in c for c in chunks)

    assert seen_conv_ids == [None, "studio-acp-1"]


@pytest.mark.asyncio
async def test_stream_studio_persists_context_across_restart_and_driver_switch(tmp_path):
    scripts_dir = tmp_path / "scripts"
    sc_dir = scripts_dir / "demo"
    (sc_dir / "scenes").mkdir(parents=True)
    (sc_dir / "world.yaml").write_text(
        'id: "demo"\ntitle: "Demo"\ninitial_scene: "s1"\ninitial_player_state:\n  hp: 100\n',
        encoding="utf-8",
    )
    (sc_dir / "scenes" / "s1.yaml").write_text(
        'id: "s1"\ntitle: "Start"\ndescription: "hi"\nactions: []\n',
        encoding="utf-8",
    )

    class DriverA(BaseAgentDriver):
        def __init__(self):
            self.calls = []

        async def run_stream(self, prompt, conversation_id=None, cwd=None):
            self.calls.append((conversation_id, prompt))
            yield AgentEvent(event_type="text_delta", data={"text": "好的，新增密室节点。", "conversation_id": "acp-a-1"})
            yield AgentEvent(event_type="done", data={"conversation_id": "acp-a-1", "status": "SUCCESS"})

    class DriverB(BaseAgentDriver):
        def __init__(self):
            self.calls = []

        async def run_stream(self, prompt, conversation_id=None, cwd=None):
            self.calls.append((conversation_id, prompt))
            yield AgentEvent(event_type="text_delta", data={"text": "收到上下文。", "conversation_id": "acp-b-1"})
            yield AgentEvent(event_type="done", data={"conversation_id": "acp-b-1", "status": "SUCCESS"})

    def make_inp(text, props=None):
        return RunAgentInput(
            thread_id="studio-persist-thread",
            run_id="r1",
            messages=[UserMessage(id="m1", role="user", content=[TextInputContent(text=text)])],
            forwarded_props={"scenario_id": "demo", **(props or {})},
        )

    # Turn 1 on bridge1
    d1 = DriverA()
    b1 = AGUIBridge(scenario_mgr=ScenarioManager(base_dir=scripts_dir), driver=d1)
    async for _ in b1.stream_studio(make_inp("在走廊后增加一间密室")):
        pass
    assert d1.calls[0][0] is None

    # Simulated full server restart: brand new AGUIBridge + DriverA receives persisted conversation_id
    d1_restarted = DriverA()
    b2 = AGUIBridge(scenario_mgr=ScenarioManager(base_dir=scripts_dir), driver=d1_restarted)
    async for _ in b2.stream_studio(make_inp("给刚才的密室加上密码锁")):
        pass
    assert d1_restarted.calls[0][0] == "acp-a-1"

    # Simulated backend switch to DriverB or regenerate: injects persisted/recent history
    d2 = DriverB()
    b2.set_driver(d2)
    async for _ in b2.stream_studio(make_inp("继续细化密码锁线索")):
        pass
    assert d2.calls[0][0] is None
    assert "在走廊后增加一间密室" in d2.calls[0][1]
    assert "给刚才的密室加上密码锁" in d2.calls[0][1]

    # Regenerate clears the driver's ACP session and restarts cleanly from recent_history
    async for _ in b2.stream_studio(
        make_inp(
            "改成机关暗门",
            props={
                "regenerate": True,
                "recent_history": [{"role": "user", "content": "第一轮设计草案"}],
            },
        )
    ):
        pass
    assert d2.calls[1][0] is None
    assert "第一轮设计草案" in d2.calls[1][1]
