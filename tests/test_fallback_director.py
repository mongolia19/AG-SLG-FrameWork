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
