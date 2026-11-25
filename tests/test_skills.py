"""Tests for PlayerState skills bar, state_delta, rank progression, and wow_elwynn_rpg integration."""

import pytest
from httpx import ASGITransport, AsyncClient
from server.app import app, bridge
from server.agent_driver import MockAgentDriver
from server.scenario_manager import ScenarioManager, evaluate_action_condition
from server.script_linter import ScriptLinter


def test_wow_skills_loaded_and_lint_clean():
    sm = ScenarioManager()
    spec = sm.load_scenario("wow_elwynn_rpg")
    assert isinstance(spec.world.initial_player_state.skills, list)
    assert spec.world.initial_player_state.skills == []

    abbey = spec.scenes["northshire_abbey"]
    class_actions = [
        a for a in abbey.actions
        if a.id in (
            "choose_human_paladin",
            "choose_nightelf_hunter",
            "choose_gnome_mage",
            "choose_dwarf_warrior",
        )
    ]
    assert len(class_actions) == 4
    for act in class_actions:
        skills = act.on_success.get("skills")
        assert isinstance(skills, list) and len(skills) == 3
        for sk in skills:
            assert sk.get("id")
            assert sk.get("name")
            assert sk.get("desc")
            assert sk.get("effect")
            assert sk.get("cost")
            assert sk.get("cooldown")

    report = ScriptLinter.lint_scenario(spec)
    assert report.valid is True
    assert report.errors == 0


def test_skill_condition_evaluation():
    sm = ScenarioManager()
    spec = sm.load_scenario("wow_elwynn_rpg")
    player = spec.world.initial_player_state

    assert evaluate_action_condition({"not_has_skill": "crusader_strike"}, player) is True
    assert evaluate_action_condition({"has_skill": "crusader_strike"}, player) is False

    player.skills = [{"id": "crusader_strike", "name": "十字军打击", "desc": "圣光重击"}]
    assert evaluate_action_condition({"has_skill": "crusader_strike"}, player) is True
    assert evaluate_action_condition({"has_skill": "十字军打击"}, player) is True
    assert evaluate_action_condition({"not_has_skill": "crusader_strike"}, player) is False


@pytest.mark.asyncio
async def test_skills_bar_class_selection_upgrade_and_custom_delta():
    mock_responses = [
        # Turn 1: Choose Human Paladin -> YAML on_success.skills populates /skills
        "圣光在你掌心燃起温暖金芒！你觉醒为人类圣骑士。\n\n```state_delta\n{}\n```",
        # Turn 2: Upgrade to Lv.2 -> variables.skill_rank=2 auto-upgrades skills level
        "麦格布莱德指点了你圣光的运用之道，你的技能全面晋升至 Lv.2！\n\n```state_delta\n{}\n```",
        # Turn 3: Custom learn_skills & remove_skills via state_delta
        (
            "你在战斗中顿悟了新技能【制裁之锤】，同时将【虔诚光环】精炼为高阶形态。\n\n"
            "```state_delta\n"
            "{\n"
            '  "learn_skills": [{"id": "hammer_of_justice", "name": "制裁之锤", "description": "投掷圣光之锤击晕目标。", "usage": "强力单体控制，打断Boss危险蓄力并赋予优势。", "cost": "30 圣能", "cooldown": "3 回合", "level": 2, "tag": "控制 · 圣光"}],\n'
            '  "remove_skills": ["devotion_aura"]\n'
            "}\n"
            "```"
        ),
    ]
    bridge.driver = MockAgentDriver(mock_responses=mock_responses)
    thread_id = "test-skills-flow-thread"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Turn 1: Choose Paladin
        res1 = await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "skills-run-1",
                "messages": [
                    {"id": "m1", "role": "user", "content": [{"type": "text", "text": "选择人类圣骑士"}]}
                ],
                "forwarded_props": {
                    "scenario_id": "wow_elwynn_rpg",
                    "action_id": "choose_human_paladin",
                    "check_passed": True,
                },
            },
        )
        assert res1.status_code == 200
        assert '"/skills"' in res1.text

        s1 = (await ac.get(f"/api/session/{thread_id}/state")).json()
        skills1 = s1["player_state"]["skills"]
        assert [sk["id"] for sk in skills1] == ["crusader_strike", "flash_of_light", "devotion_aura"]
        assert skills1[0]["name"] == "十字军打击"
        assert skills1[0]["desc"]
        assert skills1[0]["effect"]
        assert skills1[0]["cost"]
        assert skills1[0]["cooldown"]
        assert skills1[0]["level"] == 1

        # Verify prompt contains skills bar context
        prompt = bridge.build_play_prompt(bridge.sessions[thread_id], "检查技能")
        assert "技能栏" in prompt
        assert "十字军打击" in prompt

        # Turn 2: Upgrade to Lv.2
        res2 = await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "skills-run-2",
                "messages": [
                    {"id": "m2", "role": "user", "content": [{"type": "text", "text": "向麦格布莱德突破等级"}]}
                ],
                "forwarded_props": {
                    "scenario_id": "wow_elwynn_rpg",
                    "action_id": "upgrade_to_lv2",
                    "check_passed": True,
                },
            },
        )
        assert res2.status_code == 200
        s2 = (await ac.get(f"/api/session/{thread_id}/state")).json()
        skills2 = s2["player_state"]["skills"]
        assert len(skills2) == 3
        assert all(sk["level"] == 2 for sk in skills2)

        # Turn 3: Custom learn_skills & remove_skills
        res3 = await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "skills-run-3",
                "messages": [
                    {"id": "m3", "role": "user", "content": [{"type": "text", "text": "领悟新技能"}]}
                ],
                "forwarded_props": {"scenario_id": "wow_elwynn_rpg"},
            },
        )
        assert res3.status_code == 200
        s3 = (await ac.get(f"/api/session/{thread_id}/state")).json()
        skills3 = s3["player_state"]["skills"]
        ids3 = [sk["id"] for sk in skills3]
        assert "devotion_aura" not in ids3
        assert "hammer_of_justice" in ids3
        hoj = next(sk for sk in skills3 if sk["id"] == "hammer_of_justice")
        assert hoj["name"] == "制裁之锤"
        assert hoj["desc"] == "投掷圣光之锤击晕目标。"
        assert hoj["effect"] == "强力单体控制，打断Boss危险蓄力并赋予优势。"
        assert hoj["cost"] == "30 圣能"
        assert hoj["cooldown"] == "3 回合"


@pytest.mark.asyncio
async def test_hydrate_skills_for_legacy_client_state_and_empty_llm_skills():
    """Saved states with class_selected=true but skills=[] should auto-hydrate class skill cards."""
    mock_responses = [
        # Turn 1: LLM echoes empty skills list; YAML action skills must still apply
        '银月清辉映照你的双眸。\n\n```state_delta\n{"skills": []}\n```',
        # Turn 2: Legacy save already has class_id=hunter, skill_rank=2, skills=[]
        '你检查随身武器，整装待发。\n\n```state_delta\n{}\n```',
    ]
    bridge.driver = MockAgentDriver(mock_responses=mock_responses)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        t1 = "test-empty-llm-skills"
        res1 = await ac.post(
            "/api/play/run",
            json={
                "thread_id": t1,
                "run_id": "hydrate-1",
                "messages": [{"id": "m1", "role": "user", "content": [{"type": "text", "text": "选择暗夜精灵猎人"}]}],
                "forwarded_props": {
                    "scenario_id": "wow_elwynn_rpg",
                    "action_id": "choose_nightelf_hunter",
                    "check_passed": True,
                },
            },
        )
        assert res1.status_code == 200
        s1 = (await ac.get(f"/api/session/{t1}/state")).json()
        assert [sk["id"] for sk in s1["player_state"]["skills"]] == [
            "arcane_shot",
            "serpent_sting",
            "aspect_of_the_cheetah",
        ]

        t2 = "test-legacy-client-hydrate"
        res2 = await ac.post(
            "/api/play/run",
            json={
                "thread_id": t2,
                "run_id": "hydrate-2",
                "messages": [{"id": "m2", "role": "user", "content": [{"type": "text", "text": "查看状态"}]}],
                "forwarded_props": {
                    "scenario_id": "wow_elwynn_rpg",
                    "player_state": {
                        "name": "艾泽拉斯新兵",
                        "hp": 100,
                        "san": 95,
                        "gold": 10,
                        "attributes": {"strength": 11, "agility": 15},
                        "inventory": [],
                        "outfit": {},
                        "skills": [],
                        "variables": {
                            "class_selected": True,
                            "class_id": "hunter",
                            "skill_rank": 2,
                            "level": 2,
                        },
                        "current_scene": "northshire_abbey",
                    },
                },
            },
        )
        assert res2.status_code == 200
        assert '"/skills"' in res2.text
        s2 = (await ac.get(f"/api/session/{t2}/state")).json()
        skills2 = s2["player_state"]["skills"]
        assert [sk["id"] for sk in skills2] == [
            "arcane_shot",
            "serpent_sting",
            "aspect_of_the_cheetah",
        ]
        assert all(sk["level"] == 2 for sk in skills2)
