"""Tests for multi-layer visual staging and ag-slg-director protocol integration."""

import json
import pytest
from httpx import ASGITransport, AsyncClient
from server.app import app, bridge
from server.agent_driver import MockAgentDriver


@pytest.mark.asyncio
async def test_visual_staging_state_delta():
    """Verify that an agent can stage visuals across multiple layers in state_delta."""
    mock_response = (
        "你轻轻按下了书桌夹层的铜扣，暗格弹开，露出一张被烧焦一角的泛黄信纸！\n\n"
        "```state_delta\n"
        "{\n"
        '  "current_scene": "drawing_room",\n'
        '  "add_inventory": [{"id": "charred_letter", "name": "焦黑信纸"}],\n'
        '  "visuals": {\n'
        '    "background": "/assets/scenes/drawing_room.png",\n'
        '    "foreground": "",\n'
        '    "hero_image": "/assets/illustrations/charred_letter.png",\n'
        '    "atmosphere": "幽暗密闭、阴冷"\n'
        "  }\n"
        "}\n"
        "```"
    )

    bridge.driver = MockAgentDriver(mock_responses=[mock_response])
    thread_id = "test-visual-staging-thread"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "run-visual-1",
                "messages": [
                    {"id": "m1", "role": "user", "content": [{"type": "text", "text": "【调查】按动暗格"}]}
                ],
                "forwarded_props": {"scenario_id": "black_crow_manor"},
            },
        )
        assert res.status_code == 200
        response_text = res.text

        # Verify that STATE_DELTA event with visuals was emitted
        assert "STATE_DELTA" in response_text
        assert "/visuals" in response_text
        assert "/assets/illustrations/charred_letter.png" in response_text
        assert "/assets/scenes/drawing_room.png" in response_text


def test_build_play_prompt_includes_visual_inventory():
    """Verify that build_play_prompt provides full visual asset inventory and staging rules."""
    session = bridge.get_or_create_session("test-prompt-session", "black_crow_manor")
    prompt = bridge.build_play_prompt(session, "你好，请问你是？")

    assert "ag-slg-director" in prompt
    assert "当前场景预设视觉资源" in prompt
    assert "场景底图 (Background)" in prompt
    assert "焦点插图 (Hero Image)" in prompt
    assert "前景立绘 (Foreground)" in prompt
    assert "视觉舞台导演原则" in prompt
