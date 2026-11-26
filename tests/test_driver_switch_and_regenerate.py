"""Agent backend hot-switch endpoint and 'edit input / regenerate this turn' rollback semantics."""

import json

import pytest
from ag_ui.core import RunAgentInput, TextInputContent, UserMessage
from httpx import ASGITransport, AsyncClient

import server.app as app_module
from server.agent_driver import AgyDriver, CodexDriver, MockAgentDriver
from server.agui_bridge import AGUIBridge
from server.scenario_manager import ScenarioManager


@pytest.fixture
def restore_driver_state(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "DRIVER_FILE", tmp_path / ".agent_driver")
    orig_name = app_module.DRIVER_NAME
    orig_driver = app_module.bridge.driver
    app_module.bridge.driver = MockAgentDriver()
    app_module.DRIVER_NAME = "mock"
    yield tmp_path / ".agent_driver"
    app_module.DRIVER_NAME = orig_name
    app_module.bridge.driver = orig_driver


@pytest.mark.asyncio
async def test_driver_switch_endpoint_swaps_backend_and_persists(restore_driver_state):
    driver_file = restore_driver_state
    session = app_module.bridge.get_or_create_session("switch-thread", "black_crow_manor")
    session.agent_conversation_id = "old-backend-conv"
    app_module.bridge.studio_conversations["switch-thread"] = "old-studio-conv"

    async with AsyncClient(transport=ASGITransport(app=app_module.app), base_url="http://test") as ac:
        res = await ac.post("/api/driver", json={"name": "codex"})
        assert res.status_code == 200
        assert res.json()["current"] == "codex"
        assert "codex" in res.json()["available"] and "agy" in res.json()["available"]
        assert isinstance(app_module.bridge.driver, CodexDriver)
        assert driver_file.read_text().strip() == "codex"
        # conversation ids of the previous backend must not leak into the new one
        assert session.agent_conversation_id is None
        assert app_module.bridge.studio_conversations == {}

        assert (await ac.get("/health")).json()["driver"] == "codex"
        assert (await ac.get("/api/driver")).json()["current"] == "codex"

        res = await ac.post("/api/driver", json={"name": "AGY"})
        assert res.json()["current"] == "agy"
        assert isinstance(app_module.bridge.driver, AgyDriver)

        bad = await ac.post("/api/driver", json={"name": "gpt-9"})
        assert bad.status_code == 400
        assert app_module.DRIVER_NAME == "agy"


def _turn_input(thread_id: str, text: str, props: dict) -> RunAgentInput:
    return RunAgentInput(
        thread_id=thread_id,
        run_id=f"run-{thread_id}",
        messages=[UserMessage(id="m1", role="user", content=[TextInputContent(text=text)])],
        forwarded_props=props,
    )


async def _drain(bridge: AGUIBridge, input_data: RunAgentInput) -> None:
    async for _ in bridge.stream_play(input_data):
        pass


@pytest.mark.asyncio
async def test_regenerate_discards_abandoned_turn_server_state():
    mgr = ScenarioManager()
    bridge = AGUIBridge(
        scenario_mgr=mgr,
        driver=MockAgentDriver(
            mock_responses=[
                "你拧开了门把手。\n\n```state_delta\n"
                '{"variables": {"leaked_flag": true}, "hp_delta": -7}\n'
                "```",
                "你只是静静观察了一会儿。",
            ]
        ),
    )
    base_state = mgr.load_scenario("black_crow_manor").world.initial_player_state.model_dump()

    # Turn 1 mutates server session (variable + hp + history + agent conversation)
    await _drain(bridge, _turn_input("regen-thread", "拧开门把手", {"scenario_id": "black_crow_manor", "player_state": base_state}))
    session = bridge.sessions["regen-thread"]
    assert session.player_state.variables.get("leaked_flag") is True
    assert len(session.history) == 2

    # Control: a normal follow-up (no regenerate) keeps the leaked state and history
    bridge.driver = MockAgentDriver(mock_responses=["什么也没发生。"])
    await _drain(bridge, _turn_input("regen-thread", "再看看", {"scenario_id": "black_crow_manor", "player_state": base_state}))
    assert bridge.sessions["regen-thread"].player_state.variables.get("leaked_flag") is True
    assert len(bridge.sessions["regen-thread"].history) == 4

    # Regenerate from the pre-turn snapshot: the abandoned attempt must leave no trace server-side
    bridge.driver = MockAgentDriver(mock_responses=["你只是静静观察了一会儿。"])
    await _drain(
        bridge,
        _turn_input(
            "regen-thread",
            "静静观察",
            {
                "scenario_id": "black_crow_manor",
                "player_state": base_state,
                "recent_history": [],
                "regenerate": True,
            },
        ),
    )
    rebuilt = bridge.sessions["regen-thread"]
    assert rebuilt is not session
    assert "leaked_flag" not in rebuilt.player_state.variables
    assert rebuilt.player_state.hp == base_state["hp"]
    assert len(rebuilt.history) == 2
    assert rebuilt.history[0]["content"] == "静静观察"


@pytest.mark.asyncio
async def test_driver_error_without_message_is_still_descriptive():
    """Timeouts stringify to '' – the surfaced error must not be blank (codex first-run npx download)."""
    import asyncio

    class SlowAcp(CodexDriver):
        async def _ensure_started(self):
            raise asyncio.TimeoutError()

    drv = SlowAcp(executable="codex-acp")
    events = [ev async for ev in drv.run_stream("hi")]
    assert events and events[0].event_type == "error"
    assert events[0].data["error"].strip()
    assert "超时" in events[0].data["error"]
