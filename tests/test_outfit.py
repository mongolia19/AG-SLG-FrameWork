"""Tests for PlayerState outfit & accessories panel, state_delta, and scenario integration."""

import pytest
from httpx import ASGITransport, AsyncClient
from server.app import app, bridge
from server.agent_driver import MockAgentDriver
from server.scenario_manager import ScenarioManager, evaluate_action_condition
from server.script_linter import ScriptLinter


def test_initial_outfit_loaded_and_lint_clean():
    sm = ScenarioManager()
    for scenario_id in ("island_survival", "black_crow_manor"):
        spec = sm.load_scenario(scenario_id)
        outfit = spec.world.initial_player_state.outfit
        assert isinstance(outfit, dict)
        assert len(outfit) >= 4
        assert "top" in outfit
        assert "bottom" in outfit
        assert "shoes" in outfit
        report = ScriptLinter.lint_scenario(spec)
        assert report.valid is True
        assert report.errors == 0


def test_outfit_condition_evaluation():
    sm = ScenarioManager()
    spec = sm.load_scenario("island_survival")
    player = spec.world.initial_player_state

    assert evaluate_action_condition({"has_outfit": "torn_linen_shirt"}, player) is True
    assert evaluate_action_condition({"not_has_outfit": "pilot_windbreaker"}, player) is True
    assert evaluate_action_condition({"has_outfit": "pilot_windbreaker"}, player) is False
    assert evaluate_action_condition({"not_has_outfit": "broken_watch"}, player) is False


@pytest.mark.asyncio
async def test_outfit_state_delta_and_action_equip():
    mock_responses = [
        # Turn 1: Preset beach windbreaker action (even with empty LLM delta, YAML equip_outfit applies)
        "你拉出救生包，套上了亮橙色的失事机长防风夹克！\n\n```state_delta\n{}\n```",
        # Turn 2: Custom LLM state_delta updates accessory and unequips broken watch
        (
            "你摘下裂屏腕表收好，换上了一枚在沙中闪耀的海玻璃手链。\n\n"
            "```state_delta\n"
            "{\n"
            '  "unequip_outfit": ["wrist"],\n'
            '  "outfit": {"accessory": {"id": "sea_glass_charm", "name": "海玻璃手链", "desc": "海水打磨圆润的蓝绿色海玻璃饰品", "tag": "幸运 · 配饰"}}\n'
            "}\n"
            "```"
        ),
    ]
    bridge.driver = MockAgentDriver(mock_responses=mock_responses)
    thread_id = "test-outfit-flow-thread"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res1 = await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "outfit-run-1",
                "messages": [
                    {"id": "m1", "role": "user", "content": [{"type": "text", "text": "【执行检定】翻找残骸座椅旁的救生包"}]}
                ],
                "forwarded_props": {
                    "scenario_id": "island_survival",
                    "action_id": "scavenge_pilot_windbreaker",
                    "check_passed": True,
                },
            },
        )
        assert res1.status_code == 200
        assert "/outfit" in res1.text

        s1 = (await ac.get(f"/api/session/{thread_id}/state")).json()
        outfit1 = s1["player_state"]["outfit"]
        assert outfit1["outer"]["id"] == "pilot_windbreaker"
        assert outfit1["outer"]["name"] == "失事机长防风夹克"
        # Action with not_has_outfit: pilot_windbreaker should disappear once equipped
        avail_ids_1 = [a["id"] for a in s1["available_actions"]]
        assert "scavenge_pilot_windbreaker" not in avail_ids_1

        # Verify prompt contains outfit context
        prompt = bridge.build_play_prompt(bridge.sessions[thread_id], "检查身上的装备")
        assert "当前穿着与配饰" in prompt
        assert "失事机长防风夹克" in prompt

        # Turn 2: unequip wrist & equip accessory
        res2 = await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "outfit-run-2",
                "messages": [
                    {"id": "m2", "role": "user", "content": [{"type": "text", "text": "戴上海玻璃手链"}]}
                ],
                "forwarded_props": {"scenario_id": "island_survival"},
            },
        )
        assert res2.status_code == 200
        s2 = (await ac.get(f"/api/session/{thread_id}/state")).json()
        outfit2 = s2["player_state"]["outfit"]
        assert "wrist" not in outfit2
        assert outfit2["accessory"]["id"] == "sea_glass_charm"
