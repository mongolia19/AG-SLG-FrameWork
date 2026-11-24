"""Tests for dynamic weather progression, weather conditions, and weather-aware adjudication."""

import json
import random
from typing import AsyncIterator

import pytest
from ag_ui.core import RunAgentInput

from server.agent_driver import AgentEvent, BaseAgentDriver
from server.agui_bridge import (
    AGUIBridge,
    advance_weather,
    classify_weather_type,
)
from server.scenario_manager import (
    PlayerState,
    ScenarioManager,
    evaluate_action_condition,
    resolve_scene_actions,
)
from server.script_linter import ScriptLinter


class EmptyMockDriver(BaseAgentDriver):
    """Simulates offline/empty LLM response to exercise fallback director."""

    async def run_stream(
        self, prompt: str, conversation_id=None, cwd=None
    ) -> AsyncIterator[AgentEvent]:
        yield AgentEvent(event_type="error", data={"error": "offline"})
        return


def test_weather_progression_covers_multiple_weathers():
    """Advancing weather across turns must produce varied weather types (cloudy, windy, rain, storm)."""
    rng = random.Random(42)
    cur_label = "晴朗炎热"
    cur_type = "clear"
    cur_dur = 1
    seen_types = {cur_type}
    slots = ["上午", "下午", "黄昏", "夜晚", "深夜", "清晨"]

    for i in range(25):
        slot = slots[i % len(slots)]
        cur_label, cur_type, cur_dur = advance_weather(
            cur_label, cur_type, slot, duration=cur_dur, rng=rng
        )
        assert cur_label
        assert cur_type in {"clear", "cloudy", "windy", "rain", "storm", "foggy"}
        seen_types.add(cur_type)

    assert {"clear", "cloudy", "windy", "rain"} <= seen_types


def test_weather_duration_forces_change_after_two_turns():
    """Same weather type must not persist indefinitely when duration >= 2."""
    rng = random.Random(7)
    for w_type in ("clear", "cloudy", "windy", "rain", "storm", "foggy"):
        _, next_type, next_dur = advance_weather(
            "", w_type, "下午", duration=2, rng=rng
        )
        assert next_type != w_type
        assert next_dur == 1


def test_weather_condition_matching():
    """weather_in and weather_not_in must filter actions cleanly across weather states."""
    ps = PlayerState(
        variables={"weather": "阵雨淅沥", "weather_type": "rain"}
    )
    assert evaluate_action_condition({"weather_in": ["雨天", "刮风"]}, ps) is True
    assert evaluate_action_condition({"weather_in": ["小雨", "阵雨"]}, ps) is True
    assert evaluate_action_condition({"weather_in": ["晴天", "阴天"]}, ps) is False
    assert evaluate_action_condition({"weather_not_in": ["暴雨", "晴天"]}, ps) is True
    assert evaluate_action_condition({"weather_not_in": ["雨天"]}, ps) is False

    ps_storm = PlayerState(
        variables={"weather": "狂风暴雨", "weather_type": "storm"}
    )
    assert evaluate_action_condition({"weather_in": ["暴雨"]}, ps_storm) is True
    assert evaluate_action_condition({"weather_in": ["雨天"]}, ps_storm) is True
    assert evaluate_action_condition({"weather_in": ["刮风"]}, ps_storm) is True

    ps_cloudy = PlayerState(
        variables={"weather": "阴云蔽日", "weather_type": "cloudy"}
    )
    assert evaluate_action_condition({"weather_in": ["阴天"]}, ps_cloudy) is True
    assert evaluate_action_condition({"weather_in": ["雨天"]}, ps_cloudy) is False


def test_weather_adjudication_modifiers():
    """Adverse weather modifies checks while windbreaker/sunhat mitigate or assist."""
    mgr = ScenarioManager()
    bridge = AGUIBridge(scenario_mgr=mgr, driver=EmptyMockDriver())
    session = bridge.get_or_create_session("test_weather_adj", "island_survival")

    # Storm without windbreaker or shelter: -1 storm penalty; fire without lighter also -2
    session.player_state.outfit = {}
    session.player_state.inventory = []
    session.player_state.attributes["survival"] = 10
    session.player_state.attributes["stamina"] = 50
    session.player_state.attributes["hydration"] = 50
    session.player_state.attributes["fullness"] = 50
    session.player_state.variables["weather"] = "狂风暴雨"
    session.player_state.variables["weather_type"] = "storm"

    res_storm_fire = bridge.evaluate_agent_adjudication(
        skill="survival",
        base_dc=12,
        player_state=session.player_state,
        clean_action="尝试用干草生火",
        client_roll=10,
    )
    assert res_storm_fire["modifier"] == -3
    assert "狂风干扰生火" in res_storm_fire["reason"]
    assert "暴雨湿滑受阻" in res_storm_fire["reason"]

    # Equip windbreaker in rain/storm: outer(+2) + weather protection(+1)
    session.player_state.outfit["outer"] = {
        "id": "pilot_windbreaker",
        "name": "失事机长防风夹克",
    }
    res_rain_jacket = bridge.evaluate_agent_adjudication(
        skill="survival",
        base_dc=12,
        player_state=session.player_state,
        clean_action="冒雨探路",
        client_roll=10,
    )
    assert res_rain_jacket["modifier"] == 3
    assert "防风防水护佑" in res_rain_jacket["reason"]


@pytest.mark.asyncio
async def test_stream_play_updates_weather_and_weather_actions():
    """Advancing time in stream_play updates weather, atmosphere, and weather-gated actions."""
    mgr = ScenarioManager()
    bridge = AGUIBridge(scenario_mgr=mgr, driver=EmptyMockDriver())
    session = bridge.get_or_create_session("test_weather_stream", "island_survival")
    session.player_state.variables["weather"] = "细雨绵绵"
    session.player_state.variables["weather_type"] = "rain"
    session.player_state.current_scene = "coastal_jungle"
    session.player_state.inventory = [{"id": "glass_bottle", "name": "厚壁玻璃瓶"}]

    cj_scene = mgr.get_scene("island_survival", "coastal_jungle")
    actions_in_rain = resolve_scene_actions(cj_scene, session.player_state)
    action_ids = {a.id for a in actions_in_rain}
    assert "collect_jungle_rainwater" in action_ids
    assert "gather_windfall_branches" in action_ids

    # Execute rain-exclusive water collection
    inp = RunAgentInput(
        thread_id="test_weather_stream",
        run_id="w-run-1",
        messages=[
            {
                "id": "m-w-1",
                "role": "user",
                "content": [{"type": "text", "text": "【收集/互动】趁雨势正浓，用阔叶导流接满一瓶纯净雨水"}],
            }
        ],
        forwarded_props={
            "scenario_id": "island_survival",
            "action_id": "collect_jungle_rainwater",
            "check_passed": True,
        },
    )
    events = [raw async for raw in bridge.stream_play(inp)]
    combined = "".join(events)
    assert "STATE_DELTA" in combined
    assert "fresh_water_bottle" in combined
    assert "/variables/weather" in combined

    # Explicit weather override in apply_delta updates weather_type cleanly
    patches = session.apply_delta({"variables": {"weather": "阴云蔽日"}})
    assert session.player_state.variables["weather_type"] == "cloudy"
    assert classify_weather_type("阴云蔽日") == "cloudy"
    assert any(p.get("path") == "/variables/weather_type" for p in patches)


def test_island_survival_sea_cave_and_lint():
    """Verify sea_cave scene and all weather-updated island_survival scenes lint cleanly."""
    mgr = ScenarioManager()
    spec = mgr.load_scenario("island_survival")
    assert "sea_cave" in spec.scenes
    report = ScriptLinter.lint_scenario(spec)
    assert report.valid is True
    assert report.errors == 0
