"""Tests for HP/MP tracking slots, pre-boss mob combat, and multi-phase boss formulas in wow_elwynn_rpg."""

import json
import pytest
from httpx import ASGITransport, AsyncClient
from server.app import app, bridge
from server.agent_driver import MockAgentDriver
from server.scenario_manager import ScenarioManager, evaluate_action_condition
from server.script_linter import ScriptLinter


class EmptyMockDriver(MockAgentDriver):
    """Driver emitting empty text to exercise deterministic local SLG director + formulas."""

    def __init__(self):
        super().__init__(mock_responses=[""])

    async def run_stream(self, prompt: str, conversation_id=None, cwd=None):
        if False:
            yield
        return


def test_wow_vitals_and_lint_clean():
    sm = ScenarioManager()
    spec = sm.load_scenario("wow_elwynn_rpg")
    ps = spec.world.initial_player_state
    assert ps.hp == 100
    assert ps.max_hp == 100
    assert ps.mp == 100
    assert ps.max_mp == 100
    assert ps.variables.get("mp_label") == "魔法值"
    assert "fargodeep_entrance" in spec.scenes
    assert "fargodeep_cave" in spec.scenes

    report = ScriptLinter.lint_scenario(spec)
    assert report.valid is True, f"Lint errors: {report.issues}"
    assert report.errors == 0


def test_hp_mp_and_hp_lte_conditions():
    sm = ScenarioManager()
    spec = sm.load_scenario("wow_elwynn_rpg")
    player = spec.world.initial_player_state

    assert evaluate_action_condition({"min_hp": 1, "min_mp": 20}, player) is True
    assert evaluate_action_condition({"hp_lte": 0}, player) is False

    player.mp = 10
    assert evaluate_action_condition({"min_mp": 20}, player) is False
    assert evaluate_action_condition({"max_mp": 15}, player) is True

    player.hp = 0
    assert evaluate_action_condition({"min_hp": 1}, player) is False
    assert evaluate_action_condition({"hp_lte": 0}, player) is True

    player.gold = 10
    assert evaluate_action_condition({"min_gold": 15}, player) is False
    player.gold = 20
    assert evaluate_action_condition({"min_gold": 15}, player) is True


@pytest.mark.asyncio
async def test_pre_boss_vanguard_tracker_and_boss_panel_hud_widgets():
    mock_responses = [
        "奥术魔力觉醒！\n\n```state_delta\n{}\n```",
        "踏入艾尔文密林。\n\n```state_delta\n{}\n```",
        "艾莲娜加入同行。\n\n```state_delta\n{}\n```",
        "进入法戈第外围坑道，前哨进度开启！\n\n```state_delta\n{}\n```",
        "击溃狗头人矿工小队。\n\n```state_delta\n{}\n```",
        "突破护卫蛛群！\n\n```state_delta\n{}\n```",
        "战前休整完毕。\n\n```state_delta\n{}\n```",
        "踏入主巢穴，蜘蛛领主现身！\n\n```state_delta\n{}\n```",
        "火油炸药炸碎硬化甲壳！\n\n```state_delta\n{}\n```",
        "火球术轰入二阶段！\n\n```state_delta\n{\"variables\": {\"boss_phase\": 2, \"boss_minions\": 2, \"boss_casting\": \"【阶段二】毒囊幼蛛协同\"}}\n```",
        "喝下初级法力药水。\n\n```state_delta\n{}\n```",
        "炎爆术打入三阶段！\n\n```state_delta\n{\"variables\": {\"boss_phase\": 3, \"boss_armor_broken\": false, \"boss_casting\": \"【阶段三】深渊狂暴\"}}\n```",
        "照明信号箭再次破甲！\n\n```state_delta\n{}\n```",
        "终结绝杀斩杀蛛王！\n\n```state_delta\n{}\n```",
        "撤回矿洞前哨。\n\n```state_delta\n{}\n```",
    ]
    bridge.driver = MockAgentDriver(mock_responses=mock_responses)
    thread_id = "test-wow-combat-formula"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Select Gnome Mage -> max_hp=90, max_mp=140, mp_label="奥术法力"
        res_cls = await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "wow-1",
                "messages": [{"id": "m1", "role": "user", "content": [{"type": "text", "text": "选择侏儒法师"}]}],
                "forwarded_props": {
                    "scenario_id": "wow_elwynn_rpg",
                    "action_id": "choose_gnome_mage",
                    "check_passed": True,
                },
            },
        )
        assert res_cls.status_code == 200
        s1 = (await ac.get(f"/api/session/{thread_id}/state")).json()
        assert s1["player_state"]["hp"] == 90
        assert s1["player_state"]["max_hp"] == 90
        assert s1["player_state"]["mp"] == 140
        assert s1["player_state"]["max_mp"] == 140
        assert s1["player_state"]["variables"]["mp_label"] == "奥术法力"

        # 2. Transition to elwynn_wilds -> must NOT leak survival attributes (stamina/hydration)
        await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "wow-2",
                "messages": [{"id": "m2", "role": "user", "content": [{"type": "text", "text": "前往艾尔文密林"}]}],
                "forwarded_props": {"scenario_id": "wow_elwynn_rpg", "action_id": "go_to_wilds"},
            },
        )
        s2 = (await ac.get(f"/api/session/{thread_id}/state")).json()
        assert "stamina" not in s2["player_state"]["attributes"]
        assert "hydration" not in s2["player_state"]["attributes"]

        # 3. Recruit Elena + transition to fargodeep_entrance -> mounts fargodeep_vanguard tracker
        await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "wow-3",
                "messages": [{"id": "m3", "role": "user", "content": [{"type": "text", "text": "与艾莲娜结伴"}]}],
                "forwarded_props": {"scenario_id": "wow_elwynn_rpg", "action_id": "talk_elena_coop"},
            },
        )
        await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "wow-4",
                "messages": [{"id": "m4", "role": "user", "content": [{"type": "text", "text": "前往矿洞前哨"}]}],
                "forwarded_props": {"scenario_id": "wow_elwynn_rpg", "action_id": "enter_fargodeep_entrance"},
            },
        )
        s_ent = (await ac.get(f"/api/session/{thread_id}/state")).json()
        assert s_ent["player_state"]["current_scene"] == "fargodeep_entrance"
        assert any(w["id"] == "fargodeep_vanguard" for w in s_ent["player_state"].get("hud_widgets", []))
        ent_action_ids = {a["id"] for a in s_ent["available_actions"]}
        assert "clear_kobold_vanguard" in ent_action_ids
        assert "enter_fargodeep_cave" not in ent_action_ids  # Gated by pre-boss trash mobs!

        # 4. Clear Wave 1 (Kobolds) and Wave 2 (Broodguard Spiders) with deterministic high roll
        await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "wow-5",
                "messages": [{"id": "m5", "role": "user", "content": [{"type": "text", "text": "清剿狗头人"}]}],
                "forwarded_props": {
                    "scenario_id": "wow_elwynn_rpg",
                    "action_id": "clear_kobold_vanguard",
                    "client_roll": 16,
                },
            },
        )
        s_mid = (await ac.get(f"/api/session/{thread_id}/state")).json()
        assert s_mid["player_state"]["variables"]["cave_kobolds_cleared"] is True
        assert s_mid["player_state"]["mp"] < 140
        assert "stamina" not in s_mid["player_state"]["attributes"]

        await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "wow-6",
                "messages": [{"id": "m6", "role": "user", "content": [{"type": "text", "text": "清剿护卫蛛"}]}],
                "forwarded_props": {
                    "scenario_id": "wow_elwynn_rpg",
                    "action_id": "clear_broodguard_pack",
                    "client_roll": 16,
                },
            },
        )
        s_after_mob = (await ac.get(f"/api/session/{thread_id}/state")).json()
        assert s_after_mob["player_state"]["variables"]["cave_vanguard_cleared"] is True
        assert any(a["id"] == "enter_fargodeep_cave" for a in s_after_mob["available_actions"])

        # 5. Rest before boss & enter fargodeep_cave -> removes vanguard tracker & mounts arachnos_boss_panel
        await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "wow-7",
                "messages": [{"id": "m7", "role": "user", "content": [{"type": "text", "text": "战前整备"}]}],
                "forwarded_props": {"scenario_id": "wow_elwynn_rpg", "action_id": "rest_before_boss"},
            },
        )
        await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "wow-8",
                "messages": [{"id": "m8", "role": "user", "content": [{"type": "text", "text": "进入Boss巢穴"}]}],
                "forwarded_props": {"scenario_id": "wow_elwynn_rpg", "action_id": "enter_fargodeep_cave"},
            },
        )
        s_boss0 = (await ac.get(f"/api/session/{thread_id}/state")).json()
        assert s_boss0["player_state"]["current_scene"] == "fargodeep_cave"
        widget_ids = {w["id"] for w in s_boss0["player_state"].get("hud_widgets", [])}
        assert "fargodeep_vanguard" not in widget_ids
        assert "arachnos_boss_panel" in widget_ids
        bvars = s_boss0["player_state"]["variables"]
        assert bvars["boss_active"] is True
        assert bvars["boss_hp"] == 360
        assert bvars["boss_mp"] == 180
        assert bvars["boss_phase"] == 1
        assert bvars["boss_armor_broken"] is False

        # 6. Break armor with Kobold Bomb (-55 boss HP, armor broken) + Mage Burst (-85 HP -> 220)
        await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "wow-9",
                "messages": [{"id": "m9", "role": "user", "content": [{"type": "text", "text": "投掷火油炸药"}]}],
                "forwarded_props": {"scenario_id": "wow_elwynn_rpg", "action_id": "throw_kobold_bomb_armor"},
            },
        )
        s_boss2 = (await ac.get(f"/api/session/{thread_id}/state")).json()
        assert s_boss2["player_state"]["variables"]["boss_armor_broken"] is True
        assert s_boss2["player_state"]["variables"]["boss_hp"] == 305

        await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "wow-10",
                "messages": [{"id": "m10", "role": "user", "content": [{"type": "text", "text": "释放火球术"}]}],
                "forwarded_props": {
                    "scenario_id": "wow_elwynn_rpg",
                    "action_id": "coop_boss_mage",
                    "client_roll": 12,
                },
            },
        )
        s_boss3 = (await ac.get(f"/api/session/{thread_id}/state")).json()
        assert s_boss3["player_state"]["variables"]["boss_phase"] == 2
        assert s_boss3["player_state"]["variables"]["boss_minions"] == 2
        assert s_boss3["player_state"]["variables"]["boss_hp"] == 220

        # 7. Drink Mana Potion (+55 MP) and drop Boss into Phase 3
        await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "wow-11",
                "messages": [{"id": "m11", "role": "user", "content": [{"type": "text", "text": "喝法力药水"}]}],
                "forwarded_props": {"scenario_id": "wow_elwynn_rpg", "action_id": "drink_mana_potion_cave"},
            },
        )
        await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "wow-12",
                "messages": [{"id": "m12", "role": "user", "content": [{"type": "text", "text": "释放火球术"}]}],
                "forwarded_props": {
                    "scenario_id": "wow_elwynn_rpg",
                    "action_id": "coop_boss_mage",
                    "client_roll": 18,
                },
            },
        )
        s_boss4 = (await ac.get(f"/api/session/{thread_id}/state")).json()
        assert s_boss4["player_state"]["variables"]["boss_phase"] == 3
        assert s_boss4["player_state"]["variables"]["boss_armor_broken"] is False

        # 8. Break armor again with flare arrow & finish Boss
        await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "wow-13",
                "messages": [{"id": "m13", "role": "user", "content": [{"type": "text", "text": "照明信号箭破甲"}]}],
                "forwarded_props": {
                    "scenario_id": "wow_elwynn_rpg",
                    "action_id": "coop_clear_webs",
                    "client_roll": 15,
                },
            },
        )
        await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "wow-14",
                "messages": [{"id": "m14", "role": "user", "content": [{"type": "text", "text": "终结绝杀"}]}],
                "forwarded_props": {
                    "scenario_id": "wow_elwynn_rpg",
                    "action_id": "coop_boss_finisher",
                    "client_roll": 18,
                },
            },
        )
        s_boss5 = (await ac.get(f"/api/session/{thread_id}/state")).json()

        assert s_boss5["player_state"]["variables"]["boss_defeated"] is True
        assert s_boss5["player_state"]["variables"]["boss_active"] is False
        assert s_boss5["player_state"]["variables"]["level"] == 4
        assert s_boss5["player_state"]["max_hp"] == 120
        assert s_boss5["player_state"]["max_mp"] == 170
        assert not any(w["id"] == "arachnos_boss_panel" for w in s_boss5["player_state"].get("hud_widgets", []))
        inv_by_id = {it["id"]: it for it in s_boss5["player_state"]["inventory"]}
        assert "幽暗蛛王丝" in inv_by_id
        assert inv_by_id["幽暗蛛王丝"]["icon"] == "/assets/items/spider_silk.png"

        # 9. Leaving and re-entering fargodeep_cave after victory must NOT resurrect the Boss
        await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "wow-15",
                "messages": [{"id": "m15", "role": "user", "content": [{"type": "text", "text": "离开巢穴"}]}],
                "forwarded_props": {"scenario_id": "wow_elwynn_rpg", "action_id": "return_to_entrance"},
            },
        )
        s_exit = (await ac.get(f"/api/session/{thread_id}/state")).json()
        exit_action_ids = {a["id"] for a in s_exit["available_actions"]}
        assert "enter_fargodeep_cave" not in exit_action_ids
        assert "reenter_fargodeep_cave_cleared" in exit_action_ids


@pytest.mark.asyncio
async def test_wow_variable_bounds_and_yaml_adjudication_rules():
    bridge.driver = EmptyMockDriver()
    thread_id = "test-wow-bounds-and-adj"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "bnd-1",
                "messages": [{"id": "m1", "role": "user", "content": [{"type": "text", "text": "选择矮人战士"}]}],
                "forwarded_props": {"scenario_id": "wow_elwynn_rpg", "action_id": "choose_dwarf_warrior"},
            },
        )
        s0 = (await ac.get(f"/api/session/{thread_id}/state")).json()["player_state"]
        s0["current_scene"] = "fargodeep_cave"
        s0["variables"].update({
            "boss_active": True,
            "boss_defeated": False,
            "boss_hp": 15,
            "boss_mp": 10,
            "boss_minions": 1,
            "boss_web_trapped": True,
            "antidote_active": True,
        })

        # EmptyMockDriver triggers warrior_thunder_shield (-55 boss_hp, -35 boss_mp, -1 minion):
        # variable_bounds from world.yaml clamp boss_hp >= 0, boss_mp >= 0, boss_minions >= 0.
        # adjudication_rules from world.yaml compute antidote (+1) + web (-2) + minion (-1) = -2 modifier.
        await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "bnd-2",
                "messages": [{"id": "m2", "role": "user", "content": [{"type": "text", "text": "盾牌格挡"}]}],
                "forwarded_props": {
                    "scenario_id": "wow_elwynn_rpg",
                    "action_id": "warrior_thunder_shield",
                    "client_roll": 15,
                    "player_state": s0,
                },
            },
        )
        s1 = (await ac.get(f"/api/session/{thread_id}/state")).json()["player_state"]
        assert s1["variables"]["boss_hp"] == 0
        assert s1["variables"]["boss_mp"] == 0
        assert s1["variables"]["boss_minions"] == 0
