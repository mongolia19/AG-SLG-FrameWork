import json
import pytest
from ag_ui.core import RunAgentInput, UserMessage, TextInputContent
from server.agent_driver import MockAgentDriver
from server.agui_bridge import AGUIBridge
from server.scenario_manager import ScenarioManager


@pytest.mark.asyncio
async def test_stream_play_with_mock_driver():
    mgr = ScenarioManager()
    driver = MockAgentDriver(mock_responses=[
        "管家格林微微躬身，递上一把生锈的铜钥匙。\n\n"
        "```state_delta\n"
        '{"current_scene": "drawing_room", "hp_delta": -5, "variables": {"butler_trust": 20}, "add_inventory": [{"id": "copper_key", "name": "铜钥匙"}]}\n'
        "```"
    ])
    bridge = AGUIBridge(scenario_mgr=mgr, driver=driver)

    input_data = RunAgentInput(
        thread_id="test-thread-1",
        run_id="test-run-1",
        messages=[
            UserMessage(
                id="msg-1",
                role="user",
                content=[TextInputContent(text="询问管家关于钥匙的事")],
            )
        ],
    )

    events = []
    async for chunk in bridge.stream_play(input_data):
        for line in chunk.strip().split("\n"):
            line = line.strip()
            if line.startswith("data: "):
                payload = json.loads(line[6:])
                events.append(payload)

    # Verify event types and sequence
    event_types = [e.get("type") for e in events]
    assert "RUN_STARTED" in event_types
    assert "TEXT_MESSAGE_START" in event_types
    assert "TEXT_MESSAGE_CONTENT" in event_types
    assert "TEXT_MESSAGE_END" in event_types
    assert "STATE_DELTA" in event_types
    assert "RUN_FINISHED" in event_types

    # Verify state delta content
    delta_events = [e for e in events if e.get("type") == "STATE_DELTA"]
    assert len(delta_events) == 1
    delta_patches = delta_events[0]["delta"]

    paths = [p["path"] for p in delta_patches]
    assert "/current_scene" in paths
    assert "/hp" in paths
    assert "/variables/butler_trust" in paths

    # Verify session player state mutated
    session = bridge.sessions["test-thread-1"]
    assert session.player_state.current_scene == "drawing_room"
    assert session.player_state.hp == 95  # 100 - 5
    assert session.player_state.variables.get("butler_trust") == 20
    assert any(item.get("id") == "copper_key" for item in session.player_state.inventory)
