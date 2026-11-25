"""Tests for HP/MP vital slots and multi-phase Boss mechanics in wow_elwynn_rpg."""

import pytest
from httpx import ASGITransport, AsyncClient
from server.app import app, bridge
from server.agent_driver import MockAgentDriver
from server.scenario_manager import ScenarioManager, evaluate_action_condition, resolve_scene_actions
from server.script_linter import ScriptLinter


def test_wow_vitals_and_boss_lint_clean():
    sm = ScenarioManager()
    spec = sm.load_scenario("wow_elwynn_rpg")
    ps = spec.world.initial_player_state
    assert ps.hp == 100
    assert ps.max_hp == 100
    assert ps.mp == 100
    assert ps.max_mp == 100
    assert ps.variables["boss_hp"] == 360
    assert ps.variables["boss_max_hp"] == 360
    assert ps.variables["boss_mp"] == 180
    assert ps.variables["boss_max_mp"] == 180
    assert ps.variables["boss_active"] is False

    report = ScriptLinter.lint_scenario(spec)
    assert report.valid is True
    assert report.errors == 0
    assert report.warnings == 0


def test_min_mp_condition_gates_high_cost_boss_skills():
    sm = ScenarioManager()
    spec = sm.load_scenario("wow_elwynn_rpg")
    cave = spec.scenes["fargodeep_cave"]
    ps = spec.world.initial_player_state.model_copy(deep=True)
    ps.variables.update({
        "class_id": "mage",
        "boss_active": True,
        "boss_armor_broken": True,
        "boss_defeated": False,
        "boss_hp": 300,
    })

    ps.mp = 40
    actions_high_mp = {a.id for a in resolve_scene_actions(cave, ps)}
    assert "coop_boss_mage" in actions_high_mp
    assert "interrupt_boss_cast" in actions_high_mp

    ps.mp = 10
    actions_low_mp = {a.id for a in resolve_scene_actions(cave, ps)}
    assert "coop_boss_mage" not in actions_low_mp
    assert "interrupt_boss_cast" not in actions_low_mp
    assert "desperate_basic_attack" in actions_low_mp


@pytest.mark.asyncio
async def test_player_mp_hp_scaling_and_multiphase_boss_fight():
    mock_responses = [
        # Turn 1: Choose Mage (HP 90/90, MP 140/140)
        "奥术星芒在你指尖跃动！\n\n```state_delta\n{}\n```",
        # Turn 2: Wolf trial (MP -15)
        "你施展技能击溃狗头人斥候。\n\n```state_delta\n{}\n```",
        # Turn 3: Upgrade to Lv.2 (max_hp +25 -> 115, max_mp +20 -> 160)
        "麦格布莱德指点了你的施法之道。\n\n```state_delta\n{}\n```",
        # Turn 4: Engage Boss in Fargodeep Cave (YAML mounts arachnos_boss_panel)
        "蜘蛛领主·阿拉克诺斯自穹顶垂落！\n\n```state_delta\n{}\n```",
        # Turn 5: Break armor with flare arrow (YAML Boss HP 360 -> 315, Boss MP 180 -> 160)
        "照明信号箭烧穿毒网并击碎甲壳！\n\n```state_delta\n{}\n```",
        # Turn 6: Mage burst #1 (YAML -85 -> 230) + DM emits Phase 2 & 2 minions via AG-UI state_delta
        "冰火双系法术狠狠砸中蛛王腹部，二阶段毒囊幼蛛孵化！\n\n```state_delta\n"
        "{\"variables\": {\"boss_phase\": 2, \"boss_minions\": 2, \"boss_casting\": \"【阶段二】召唤毒囊幼蛛 ×2 · 蓄力剧毒新星\"}}\n```",
        # Turn 7: Mage burst #2 (YAML -85 -> 145)
        "炽烈火球再次引爆蛛王毒囊！\n\n```state_delta\n{}\n```",
        # Turn 8: Mage burst #3 (YAML -85 -> 60) + DM emits Phase 3 via AG-UI state_delta
        "奥术炎爆轰碎半边身躯，蛛王陷入深渊狂暴！\n\n```state_delta\n"
        "{\"variables\": {\"boss_phase\": 3, \"boss_armor_broken\": false, \"boss_casting\": \"【阶段三】深渊狂暴\"}}\n```",
        # Turn 9: Finisher (YAML sets boss_defeated=True, level=4, loot, removes arachnos_boss_panel)
        "最后一击彻底粉碎了阿拉克诺斯！\n\n```state_delta\n{}\n```",
    ]
    bridge.driver = MockAgentDriver(mock_responses=mock_responses)
    thread_id = "test-wow-boss-vitals-thread"

    # Verify dm_rules from world.yaml are injected into the DM prompt without Python hardcoding
    tmp_session = bridge.get_or_create_session("prompt-check-session", "wow_elwynn_rpg")
    tmp_session.player_state.current_scene = "fargodeep_cave"
    prompt = bridge.build_play_prompt(tmp_session, "火球术攻击 Boss")
    assert "蜘蛛领主三阶段机制" in prompt
    assert "hud_widgets" in prompt

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Choose Mage
        r1 = await ac.post("/api/play/run", json={
            "thread_id": thread_id,
            "run_id": "r1",
            "messages": [{"id": "m1", "role": "user", "content": [{"type": "text", "text": "选择侏儒法师"}]}],
            "forwarded_props": {"scenario_id": "wow_elwynn_rpg", "action_id": "choose_gnome_mage", "check_passed": True},
        })
        assert r1.status_code == 200
        s1 = (await ac.get(f"/api/session/{thread_id}/state")).json()["player_state"]
        assert s1["hp"] == 90 and s1["max_hp"] == 90
        assert s1["mp"] == 140 and s1["max_mp"] == 140
        assert s1["variables"]["mp_label"] == "奥术法力"

        # 2. Northshire trial
        await ac.post("/api/play/run", json={
            "thread_id": thread_id,
            "run_id": "r2",
            "messages": [{"id": "m2", "role": "user", "content": [{"type": "text", "text": "新手试炼"}]}],
            "forwarded_props": {"scenario_id": "wow_elwynn_rpg", "action_id": "northshire_wolf_trial", "check_passed": True, "client_roll": 18},
        })
        s2 = (await ac.get(f"/api/session/{thread_id}/state")).json()["player_state"]
        assert s2["hp"] == 82
        assert s2["mp"] == 125

        # 3. Upgrade to Lv.2 -> max_hp=115, max_mp=160, hp=115, mp=160
        await ac.post("/api/play/run", json={
            "thread_id": thread_id,
            "run_id": "r3",
            "messages": [{"id": "m3", "role": "user", "content": [{"type": "text", "text": "突破Lv.2"}]}],
            "forwarded_props": {"scenario_id": "wow_elwynn_rpg", "action_id": "upgrade_to_lv2", "check_passed": True},
        })
        s3 = (await ac.get(f"/api/session/{thread_id}/state")).json()["player_state"]
        assert s3["max_hp"] == 115 and s3["hp"] == 115
        assert s3["max_mp"] == 160 and s3["mp"] == 160

        # Sync client into fargodeep_cave with flare arrow & ally recruited
        s3["current_scene"] = "fargodeep_cave"
        s3["variables"]["ally_recruited"] = True
        s3["inventory"].append({"id": "照明信号箭", "name": "照明信号箭"})

        # 4. Engage Boss -> YAML mounts arachnos_boss_panel in hud_widgets
        await ac.post("/api/play/run", json={
            "thread_id": thread_id,
            "run_id": "r4",
            "messages": [{"id": "m4", "role": "user", "content": [{"type": "text", "text": "迎战蜘蛛领主"}]}],
            "forwarded_props": {"scenario_id": "wow_elwynn_rpg", "action_id": "engage_boss_arachnos", "check_passed": True, "player_state": s3},
        })
        s4 = (await ac.get(f"/api/session/{thread_id}/state")).json()["player_state"]
        assert s4["variables"]["boss_active"] is True
        assert s4["variables"]["boss_hp"] == 360
        assert s4["variables"]["boss_mp"] == 180
        assert s4["variables"]["boss_phase"] == 1
        assert any(w["id"] == "arachnos_boss_panel" for w in s4.get("hud_widgets", []))

        # 5. Break armor (coop_clear_webs)
        await ac.post("/api/play/run", json={
            "thread_id": thread_id,
            "run_id": "r5",
            "messages": [{"id": "m5", "role": "user", "content": [{"type": "text", "text": "合作破甲"}]}],
            "forwarded_props": {"scenario_id": "wow_elwynn_rpg", "action_id": "coop_clear_webs", "check_passed": True, "client_roll": 16},
        })
        s5 = (await ac.get(f"/api/session/{thread_id}/state")).json()["player_state"]
        assert s5["variables"]["boss_armor_broken"] is True
        assert s5["variables"]["boss_hp"] == 315
        assert s5["variables"]["boss_mp"] == 160
        assert s5["mp"] == 145

        # 6. Mage burst #1 -> Boss HP 230, Phase 2 triggers + 2 minions via AG-UI state_delta
        await ac.post("/api/play/run", json={
            "thread_id": thread_id,
            "run_id": "r6",
            "messages": [{"id": "m6", "role": "user", "content": [{"type": "text", "text": "法师强攻"}]}],
            "forwarded_props": {"scenario_id": "wow_elwynn_rpg", "action_id": "coop_boss_mage", "check_passed": True, "client_roll": 16},
        })
        s6 = (await ac.get(f"/api/session/{thread_id}/state")).json()["player_state"]
        assert s6["variables"]["boss_hp"] == 230
        assert s6["variables"]["boss_phase"] == 2
        assert s6["variables"]["boss_minions"] == 2
        assert s6["variables"]["boss_defeated"] is False

        # 7. Mage burst #2 -> Boss HP 145
        await ac.post("/api/play/run", json={
            "thread_id": thread_id,
            "run_id": "r7",
            "messages": [{"id": "m7", "role": "user", "content": [{"type": "text", "text": "法师强攻"}]}],
            "forwarded_props": {"scenario_id": "wow_elwynn_rpg", "action_id": "coop_boss_mage", "check_passed": True, "client_roll": 17},
        })
        s7 = (await ac.get(f"/api/session/{thread_id}/state")).json()["player_state"]
        assert s7["variables"]["boss_hp"] == 145
        assert s7["variables"]["boss_defeated"] is False

        # 8. Mage burst #3 -> Boss HP 60, Phase 3 triggers via AG-UI state_delta
        await ac.post("/api/play/run", json={
            "thread_id": thread_id,
            "run_id": "r8",
            "messages": [{"id": "m8", "role": "user", "content": [{"type": "text", "text": "法师强攻"}]}],
            "forwarded_props": {"scenario_id": "wow_elwynn_rpg", "action_id": "coop_boss_mage", "check_passed": True, "client_roll": 18},
        })
        s8 = (await ac.get(f"/api/session/{thread_id}/state")).json()["player_state"]
        assert s8["variables"]["boss_hp"] == 60
        assert s8["variables"]["boss_phase"] == 3
        assert s8["variables"]["boss_defeated"] is False

        # 9. Finisher -> Boss defeated, Lv.4, loot obtained, boss panel unmounted
        await ac.post("/api/play/run", json={
            "thread_id": thread_id,
            "run_id": "r9",
            "messages": [{"id": "m9", "role": "user", "content": [{"type": "text", "text": "绝杀终结"}]}],
            "forwarded_props": {"scenario_id": "wow_elwynn_rpg", "action_id": "coop_boss_finisher", "check_passed": True, "client_roll": 18},
        })
        s9 = (await ac.get(f"/api/session/{thread_id}/state")).json()["player_state"]
        assert s9["variables"]["boss_defeated"] is True
        assert s9["variables"]["boss_active"] is False
        assert s9["variables"]["boss_hp"] == 0
        assert s9["variables"]["level"] == 4
        assert not any(w["id"] == "arachnos_boss_panel" for w in s9.get("hud_widgets", []))
        assert any(it["id"] == "幽暗蛛王丝" for it in s9["inventory"])
