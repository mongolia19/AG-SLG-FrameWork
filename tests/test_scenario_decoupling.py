"""Tests proving zero engine coupling: arbitrary YAML-defined scenarios drive HUD widgets, rules, bounds, fallbacks, and Studio guardrails."""

import json
import pytest
import yaml
from ag_ui.core import RunAgentInput

from server.agent_driver import MockAgentDriver
from server.agui_bridge import AGUIBridge
from server.scenario_manager import ScenarioManager


class _EmptyDriver(MockAgentDriver):
    def __init__(self):
        super().__init__(mock_responses=[""])

    async def run_stream(self, prompt: str, conversation_id=None, cwd=None):
        if False:
            yield
        return


def _write_synthetic_scenario(base_dir):
    sc_dir = base_dir / "cyber_heist"
    scenes_dir = sc_dir / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)

    world_data = {
        "id": "cyber_heist",
        "title": "霓虹金库劫案",
        "version": "1.0.0",
        "author": "Test Studio",
        "icon": "🛸",
        "sort_order": 5,
        "initial_scene": "lobby",
        "opening_narration": "雨水滑过霓虹幕墙，你潜入了第 99 层黑市银行大厅。",
        "dm_rules": "- 若警报等级 `alert_level >= 3`，安保无人机立即封锁出口。\n- 使用黑客终端时优先读取 `hud_widgets`。",
        "attribute_labels": {"hacking": "黑客", "stealth": "潜行"},
        "attribute_bounds": {"hacking": [0, 30]},
        "variable_bounds": {"alert_level": {"min": 0, "max": 5}, "vault_shield": {"min": 0, "max_var": "vault_shield_max"}},
        "unique_items": ["emp_chip"],
        "item_catalog": {
            "emp_chip": {
                "name": "电磁脉冲芯片",
                "icon": "⚡",
                "desc": "可瞬间瘫痪一套激光警戒网。",
            }
        },
        "adjudication_rules": [
            {
                "when": {"has_item": "emp_chip"},
                "action_keywords": ["黑入", "破解", "入侵"],
                "mod": 3,
                "label": "EMP芯片辅助(+3)",
            }
        ],
        "fallback_recipes": [
            {
                "id": "hack_terminal",
                "any_keywords": ["黑入终端", "入侵终端"],
                "branches": [
                    {
                        "when": {"has_item": "emp_chip"},
                        "narration": "你插入电磁脉冲芯片，终端防火墙瞬间崩解！",
                        "delta": {"variables_delta": {"vault_shield": -40}, "variables": {"terminal_hacked": True}},
                    }
                ],
                "narration": "防火墙太厚，警戒度上升！",
                "delta": {"variables_delta": {"alert_level": 1}},
            }
        ],
        "default_fallback": {
            "narration": "你压低身形观察大厅内的红外扫描仪。",
            "delta": {},
        },
        "initial_player_state": {
            "name": "幽灵骇客",
            "hp": 100,
            "max_hp": 100,
            "san": 90,
            "gold": 500,
            "attributes": {"hacking": 16, "stealth": 14},
            "inventory": [],
            "hud_widgets": [
                {
                    "id": "heist_metrics",
                    "type": "metrics",
                    "title": "行动指标",
                    "icon": "🛸",
                    "items": [
                        {"id": "alert", "label": "警戒值", "value_ref": "variables.alert_level", "max": 5, "color": "amber"},
                    ],
                }
            ],
            "variables": {
                "alert_level": 1,
                "vault_shield": 100,
                "vault_shield_max": 100,
                "terminal_hacked": False,
            },
            "current_scene": "lobby",
        },
    }
    (sc_dir / "world.yaml").write_text(yaml.safe_dump(world_data, allow_unicode=True), encoding="utf-8")

    scene_data = {
        "id": "lobby",
        "title": "黑市银行大厅",
        "description": "激光网格在大理石地板上交错扫描。",
        "actions": [
            {
                "id": "grab_emp",
                "label": "拾取电磁脉冲芯片",
                "type": "interact",
                "on_success": {
                    "gain_item": "emp_chip",
                    "variables_delta": {"alert_level": 10},  # tests clamping to 5!
                    "attributes_delta": {"hacking": 50},  # tests clamping to 30!
                    "message": "你悄悄拿到了电磁脉冲芯片。",
                },
            },
            {
                "id": "crack_vault",
                "label": "黑入金库主控",
                "type": "check",
                "skill": "hacking",
                "difficulty": 14,
                "on_success": {
                    "variables_delta": {"vault_shield": -200},  # tests clamping >= 0
                    "message": "金库护盾彻底瘫痪！",
                },
                "on_failure": {"message": "破解受阻。"},
            },
        ],
    }
    (scenes_dir / "lobby.yaml").write_text(yaml.safe_dump(scene_data, allow_unicode=True), encoding="utf-8")


class _RecordingDriver(MockAgentDriver):
    def __init__(self, mock_responses):
        super().__init__(mock_responses=mock_responses)
        self.captured_prompts = []

    async def run_stream(self, prompt: str, conversation_id=None, cwd=None):
        self.captured_prompts.append(prompt)
        async for ev in super().run_stream(prompt, conversation_id=conversation_id, cwd=cwd):
            yield ev


@pytest.mark.asyncio
async def test_synthetic_scenario_runs_without_engine_changes(tmp_path):
    _write_synthetic_scenario(tmp_path)
    sm = ScenarioManager(base_dir=tmp_path)

    # 1. Summary listing exposes icon & sorts by sort_order
    summaries = sm.list_scenario_summaries()
    assert summaries == [{"id": "cyber_heist", "title": "霓虹金库劫案", "icon": "🛸"}]

    bridge = AGUIBridge(scenario_mgr=sm, driver=_EmptyDriver())

    # 2. Custom dm_rules injected into prompt
    prompt_session = bridge.get_or_create_session("prompt-heist", "cyber_heist")
    prompt = bridge.build_play_prompt(prompt_session, "观察大厅")
    assert "alert_level >= 3" in prompt
    assert "hud_widgets" in prompt

    # 3. Studio prompt strictly forbids modifying core framework code
    recorder = _RecordingDriver(["好的，我将仅修改 scripts/cyber_heist/ 下的剧本配置。"])
    bridge.driver = recorder
    async for _ in bridge.stream_studio(
        RunAgentInput(
            thread_id="studio-guard-thread",
            run_id="studio-r1",
            messages=[{"id": "sm1", "role": "user", "content": [{"type": "text", "text": "帮我新增一个隐藏boss面板"}]}],
            forwarded_props={"scenario_id": "cyber_heist"},
            state={},
            tools=[],
            context=[],
        )
    ):
        pass
    assert len(recorder.captured_prompts) == 1
    studio_prompt = recorder.captured_prompts[0]
    assert "严禁修改框架代码" in studio_prompt
    assert "server/" in studio_prompt
    assert "web/" in studio_prompt
    assert "仅限** `scripts/`" in studio_prompt
    assert "scripts/<new_scenario_id>/" in studio_prompt
    assert "仅限**当前剧本目录" not in studio_prompt

    bridge.driver = _EmptyDriver()

    # 4. Run turns via EmptyDriver -> item_catalog, bounds, unique_items, custom fallback_recipes, default_fallback
    thread_id = "synthetic-heist-thread"
    events_1 = []
    async for raw in bridge.stream_play(
        RunAgentInput(
            thread_id=thread_id,
            run_id="r1",
            messages=[{"id": "m1", "role": "user", "content": [{"type": "text", "text": "拾取芯片"}]}],
            forwarded_props={"scenario_id": "cyber_heist", "action_id": "grab_emp"},
            state={},
            tools=[],
            context=[],
        )
    ):
        events_1.append(raw)

    ps1 = bridge.sessions[thread_id].player_state
    assert len(ps1.inventory) == 1
    assert ps1.inventory[0]["icon"] == "⚡"
    assert ps1.inventory[0]["name"] == "电磁脉冲芯片"
    assert ps1.variables["alert_level"] == 5  # clamped by variable_bounds
    assert ps1.attributes["hacking"] == 30  # clamped by attribute_bounds

    # 5. Custom fallback recipe matches freeform input ("黑入终端")
    events_2 = []
    async for raw in bridge.stream_play(
        RunAgentInput(
            thread_id=thread_id,
            run_id="r2",
            messages=[{"id": "m2", "role": "user", "content": [{"type": "text", "text": "黑入终端关闭护盾"}]}],
            forwarded_props={"scenario_id": "cyber_heist"},
            state={},
            tools=[],
            context=[],
        )
    ):
        events_2.append(raw)

    ps2 = bridge.sessions[thread_id].player_state
    assert ps2.variables["terminal_hacked"] is True
    assert ps2.variables["vault_shield"] == 60
    assert any("防火墙瞬间崩解" in ev for ev in events_2)

    # 6. Custom adjudication_rules grants +3 modifier from emp_chip on "黑入" check
    events_3 = []
    async for raw in bridge.stream_play(
        RunAgentInput(
            thread_id=thread_id,
            run_id="r3",
            messages=[{"id": "m3", "role": "user", "content": [{"type": "text", "text": "黑入金库主控"}]}],
            forwarded_props={"scenario_id": "cyber_heist", "action_id": "crack_vault", "client_roll": 10},
            state={},
            tools=[],
            context=[],
        )
    ):
        events_3.append(raw)

    ps3 = bridge.sessions[thread_id].player_state
    assert ps3.variables["vault_shield"] == 0  # clamped >= 0
    assert any("EMP芯片辅助(+3)" in ev for ev in events_3)

    # 7. AG-UI MockAgentDriver can dynamically mount & remove hud_widgets via state_delta
    bridge.driver = MockAgentDriver(
        mock_responses=[
            "无人机警报拉响！\n\n```state_delta\n"
            + json.dumps(
                {
                    "hud_widgets": [
                        {
                            "id": "drone_panel",
                            "type": "panel",
                            "title": "安保无人机群",
                            "tone": "danger",
                            "bars": [{"label": "无人机护盾", "value": 80, "max": 100, "color": "rose"}],
                        }
                    ]
                },
                ensure_ascii=False,
            )
            + "\n```",
            "无人机群被彻底关闭！\n\n```state_delta\n"
            + json.dumps({"remove_hud_widgets": ["drone_panel"]}, ensure_ascii=False)
            + "\n```",
        ]
    )

    async for _ in bridge.stream_play(
        RunAgentInput(
            thread_id=thread_id,
            run_id="r4",
            messages=[{"id": "m4", "role": "user", "content": [{"type": "text", "text": "触发警报"}]}],
            forwarded_props={"scenario_id": "cyber_heist"},
            state={},
            tools=[],
            context=[],
        )
    ):
        pass
    assert any(w["id"] == "drone_panel" for w in bridge.sessions[thread_id].player_state.hud_widgets)
    assert any(w["id"] == "heist_metrics" for w in bridge.sessions[thread_id].player_state.hud_widgets)

    async for _ in bridge.stream_play(
        RunAgentInput(
            thread_id=thread_id,
            run_id="r5",
            messages=[{"id": "m5", "role": "user", "content": [{"type": "text", "text": "关闭警报"}]}],
            forwarded_props={"scenario_id": "cyber_heist"},
            state={},
            tools=[],
            context=[],
        )
    ):
        pass
    assert not any(w["id"] == "drone_panel" for w in bridge.sessions[thread_id].player_state.hud_widgets)
    assert any(w["id"] == "heist_metrics" for w in bridge.sessions[thread_id].player_state.hud_widgets)
