import pytest
import asyncio
from typing import AsyncIterator
from ag_ui.core import RunAgentInput
from server.agui_bridge import AGUIBridge, extract_message_text
from server.agent_driver import BaseAgentDriver, AgentEvent
from server.scenario_manager import ScenarioManager


class EmptyMockDriver(BaseAgentDriver):
    """Simulates agent CLI running out of credits or returning no text."""
    async def run_stream(self, prompt: str, conversation_id=None, cwd=None) -> AsyncIterator[AgentEvent]:
        # Emits error event and terminates without text deltas
        yield AgentEvent(event_type="error", data={"error": "credits exhausted"})
        return


@pytest.mark.asyncio
async def test_extract_message_text():
    assert extract_message_text("hello world") == "hello world"
    assert extract_message_text([{"type": "text", "text": "再次尝试抓取玻璃瓶"}]) == "再次尝试抓取玻璃瓶"
    assert extract_message_text([{"type": "text", "text": "行1"}, {"type": "text", "text": "行2"}]) == "行1\n行2"


@pytest.mark.asyncio
async def test_fallback_director_bottle_custom_input():
    mgr = ScenarioManager()
    driver = EmptyMockDriver()
    bridge = AGUIBridge(scenario_mgr=mgr, driver=driver)

    inp = RunAgentInput(
        thread_id="test_fallback_bottle",
        run_id="run_1",
        messages=[
            {
                "id": "msg-1",
                "role": "user",
                "content": [{"type": "text", "text": "再次尝试抓取玻璃瓶"}],
            }
        ],
        forwarded_props={"scenario_id": "island_survival"},
    )

    events = []
    async for raw in bridge.stream_play(inp):
        events.append(raw)

    combined = "".join(events)
    # Check that text was generated and streamed
    assert "TEXT_MESSAGE_CONTENT" in combined
    assert "玻璃瓶" in combined
    # Check that STATE_DELTA was emitted
    assert "STATE_DELTA" in combined
    assert "RUN_FINISHED" in combined


@pytest.mark.asyncio
async def test_fallback_director_seashell_custom_input():
    mgr = ScenarioManager()
    driver = EmptyMockDriver()
    bridge = AGUIBridge(scenario_mgr=mgr, driver=driver)

    inp = RunAgentInput(
        thread_id="test_fallback_seashell",
        run_id="run_2",
        messages=[
            {
                "id": "msg-2",
                "role": "user",
                "content": [{"type": "text", "text": "拾取一些沙滩贝壳"}],
            }
        ],
        forwarded_props={"scenario_id": "island_survival"},
    )

    events = []
    async for raw in bridge.stream_play(inp):
        events.append(raw)

    combined = "".join(events)
    assert "TEXT_MESSAGE_CONTENT" in combined
    assert "STATE_DELTA" in combined


@pytest.mark.asyncio
async def test_fallback_director_pickup_metal_box_not_hijacked_to_lighter():
    """Picking up and washing the waterproof metal box must grant metal_box, not search for lighter."""
    mgr = ScenarioManager()
    driver = EmptyMockDriver()
    bridge = AGUIBridge(scenario_mgr=mgr, driver=driver)

    inp = RunAgentInput(
        thread_id="test_pickup_metal_box_fallback",
        run_id="run_metal_box_1",
        messages=[
            {
                "id": "msg-box-1",
                "role": "user",
                "content": [{"type": "text", "text": "捡起防水金属盒，洗干净带走"}],
            }
        ],
        forwarded_props={"scenario_id": "island_survival"},
    )

    events = []
    async for raw in bridge.stream_play(inp):
        events.append(raw)

    import json
    narrative_parts = []
    for raw in events:
        for line in raw.strip().split("\n"):
            if line.startswith("data: "):
                payload = json.loads(line[6:])
                if payload.get("type") == "TEXT_MESSAGE_CONTENT":
                    narrative_parts.append(payload.get("delta", ""))
    narrative_text = "".join(narrative_parts)

    combined = "".join(events)
    assert "STATE_DELTA" in combined
    assert "metal_box" in combined
    assert "防水金属盒" in narrative_text
    assert "打火机" not in narrative_text

    session = bridge.sessions["test_pickup_metal_box_fallback"]
    inv_ids = [item.get("id") for item in session.player_state.inventory]
    assert "metal_box" in inv_ids
    assert "lighter" not in inv_ids
    assert session.player_state.variables.get("found_metal_box") is True
    assert session.player_state.variables.get("found_lighter") is False


@pytest.mark.asyncio
async def test_fallback_director_lighter_campfire_and_cooking():
    """Player with lighter in inventory ignites fire and cooks food without being told there is no fire source."""
    mgr = ScenarioManager()
    driver = EmptyMockDriver()
    bridge = AGUIBridge(scenario_mgr=mgr, driver=driver)

    session = bridge.get_or_create_session("test_lighter_fire_thread", "island_survival")
    # Grant lighter and raw_crab to player inventory
    session.player_state.inventory.append({
        "id": "lighter",
        "name": "防风打火机",
        "desc": "军用级防水防风打火机",
    })
    session.player_state.inventory.append({
        "id": "raw_crab",
        "name": "肥硕海蟹",
        "desc": "刚捕获的活青蟹",
    })
    assert session.player_state.variables.get("fire_started") is False

    inp = RunAgentInput(
        thread_id="test_lighter_fire_thread",
        run_id="run_fire_1",
        messages=[
            {
                "id": "msg-fire-1",
                "role": "user",
                "content": [{"type": "text", "text": "从背包中取出打火机点燃甘草进而引燃火堆，开始煮食物"}],
            }
        ],
        forwarded_props={"scenario_id": "island_survival"},
    )

    events = []
    async for raw in bridge.stream_play(inp):
        events.append(raw)

    import json
    narrative_parts = []
    for raw in events:
        for line in raw.strip().split("\n"):
            if line.startswith("data: "):
                payload = json.loads(line[6:])
                if payload.get("type") == "TEXT_MESSAGE_CONTENT":
                    narrative_parts.append(payload.get("delta", ""))
    narrative_text = "".join(narrative_parts)

    # Must NOT claim lack of fire source
    assert "没有火源" not in narrative_text
    assert "打火机" in narrative_text
    assert "篝火" in narrative_text

    # Fire must be started!
    assert session.player_state.variables.get("fire_started") is True

    # Crab should be cooked/consumed, fullness increased
    inv_ids = [item.get("id") for item in session.player_state.inventory]
    assert "raw_crab" not in inv_ids
    assert session.player_state.attributes.get("fullness") > 60
