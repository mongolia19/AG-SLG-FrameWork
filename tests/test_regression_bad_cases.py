"""Regression test suite for user-reported bad cases.

Every bad case reported during development must have a corresponding test here.
This suite MUST pass before every commit and release.
"""

import pytest
import re
import json
from typing import AsyncIterator
from ag_ui.core import RunAgentInput
from server.agui_bridge import AGUIBridge, extract_message_text
from server.agent_driver import BaseAgentDriver, AgentEvent
from server.scenario_manager import ScenarioManager, PlayerState


class EmptyMockDriver(BaseAgentDriver):
    """Simulates agent CLI running out of credits or returning no text."""
    async def run_stream(self, prompt: str, conversation_id=None, cwd=None) -> AsyncIterator[AgentEvent]:
        yield AgentEvent(event_type="error", data={"error": "credits exhausted"})
        return


# ============================================================================
# BAD CASE 1: Lighter in backpack was ignored; GM claimed "没有火源"
# Reported: "从背包中取出打火机点燃甘草进而引燃火堆，开始煮食物。我明明已经说了用打火机，
#           而且背包中也有打火机，为啥现在故事推进还是说没有火源？直接无视我的输入？debug！！！！"
# ============================================================================
@pytest.mark.asyncio
async def test_regression_badcase_lighter_in_backpack_ignored():
    """Bad Case 1: Player with lighter in inventory must successfully light fire and cook food."""
    mgr = ScenarioManager()
    driver = EmptyMockDriver()
    bridge = AGUIBridge(scenario_mgr=mgr, driver=driver)

    session = bridge.get_or_create_session("test_bc1_lighter", "island_survival")
    session.player_state.inventory.append({
        "id": "lighter",
        "name": "防风打火机",
        "desc": "军用级防水防风打火机",
    })
    session.player_state.inventory.append({
        "id": "raw_crab",
        "name": "新鲜海蟹",
        "desc": "刚捕获的活青蟹",
    })

    inp = RunAgentInput(
        thread_id="test_bc1_lighter",
        run_id="run_bc1_1",
        messages=[
            {
                "id": "msg-bc1-1",
                "role": "user",
                "content": [{"type": "text", "text": "从背包中取出打火机点燃甘草进而引燃火堆，开始煮食物"}],
            }
        ],
        forwarded_props={"scenario_id": "island_survival"},
    )

    events = []
    async for raw in bridge.stream_play(inp):
        events.append(raw)

    narrative_parts = []
    for raw in events:
        for line in raw.strip().split("\n"):
            if line.startswith("data: "):
                payload = json.loads(line[6:])
                if payload.get("type") == "TEXT_MESSAGE_CONTENT":
                    narrative_parts.append(payload.get("delta", ""))
    narrative_text = "".join(narrative_parts)

    # Assertions
    assert "没有火源" not in narrative_text, "GM must NOT claim absence of fire source when lighter is owned"
    assert "打火机" in narrative_text
    assert "篝火" in narrative_text
    assert session.player_state.variables.get("fire_started") is True
    inv_ids = [item.get("id") for item in session.player_state.inventory]
    assert "raw_crab" not in inv_ids
    assert session.player_state.attributes.get("fullness") > 60


# ============================================================================
# BAD CASE 2: Picking up metal box was hijacked to searching box for lighter
# Reported: "捡起防水金属盒，洗干净带走" was hijacked to search luggage / search lighter.
# ============================================================================
@pytest.mark.asyncio
async def test_regression_badcase_pickup_metal_box_intent_hijacking():
    """Bad Case 2: Intent of picking up and washing metal box must grant metal_box, not search lighter."""
    mgr = ScenarioManager()
    driver = EmptyMockDriver()
    bridge = AGUIBridge(scenario_mgr=mgr, driver=driver)

    inp = RunAgentInput(
        thread_id="test_bc2_box",
        run_id="run_bc2_1",
        messages=[
            {
                "id": "msg-bc2-1",
                "role": "user",
                "content": [{"type": "text", "text": "捡起防水金属盒，洗干净带走"}],
            }
        ],
        forwarded_props={"scenario_id": "island_survival"},
    )

    events = []
    async for raw in bridge.stream_play(inp):
        events.append(raw)

    narrative_parts = []
    for raw in events:
        for line in raw.strip().split("\n"):
            if line.startswith("data: "):
                payload = json.loads(line[6:])
                if payload.get("type") == "TEXT_MESSAGE_CONTENT":
                    narrative_parts.append(payload.get("delta", ""))
    narrative_text = "".join(narrative_parts)

    assert "防水金属盒" in narrative_text
    assert "打火机" not in narrative_text

    session = bridge.sessions["test_bc2_box"]
    inv_ids = [item.get("id") for item in session.player_state.inventory]
    assert "metal_box" in inv_ids
    assert "lighter" not in inv_ids
    assert session.player_state.variables.get("found_metal_box") is True
    assert session.player_state.variables.get("found_lighter") is False


# ============================================================================
# BAD CASE 3: Client-Server state desynchronization & empty backpack hallucination
# Reported: "明明背包里面有好几个打火机，为啥GM说没有？ 背包和当前故事进度不同步？"
# ============================================================================
@pytest.mark.asyncio
async def test_regression_badcase_client_server_inventory_sync():
    """Bad Case 3: When client passes player_state in forwarded_props, server must sync inventory and Prompt."""
    mgr = ScenarioManager()
    driver = EmptyMockDriver()
    bridge = AGUIBridge(scenario_mgr=mgr, driver=driver)

    # Client has accumulated items in LocalStorage
    client_state = {
        "current_scene": "beach",
        "hp": 90,
        "san": 85,
        "attributes": {"stamina": 75, "hydration": 65, "fullness": 60},
        "inventory": [
            {"id": "lighter", "name": "防风打火机"},
            {"id": "glass_bottle", "name": "厚壁玻璃瓶"},
            {"id": "branches", "name": "干燥树枝"},
        ],
        "variables": {"fire_started": False},
    }

    # Simulate fresh thread or server restart
    inp = RunAgentInput(
        thread_id="test_bc3_sync",
        run_id="run_bc3_1",
        messages=[
            {
                "id": "msg-bc3-1",
                "role": "user",
                "content": [{"type": "text", "text": "检查周围环境并准备点燃干燥树枝"}],
            }
        ],
        forwarded_props={
            "scenario_id": "island_survival",
            "player_state": client_state,
        },
    )

    events = []
    async for raw in bridge.stream_play(inp):
        events.append(raw)

    session = bridge.sessions["test_bc3_sync"]
    inv_ids = [item.get("id") for item in session.player_state.inventory]
    assert "lighter" in inv_ids, "Server must have synced lighter from client_state"
    assert "glass_bottle" in inv_ids
    assert "branches" in inv_ids

    # Prompt generated for LLM must NOT say "背包物品：空"
    prompt = bridge.build_play_prompt(session, "检查周围环境")
    assert "背包物品：空" not in prompt
    assert "防风打火机" in prompt


# ============================================================================
# BAD CASE 4: Duplicate unique tools in inventory
# Reported: User screenshot showed 3 duplicate "防风打火机" in backpack modal.
# ============================================================================
@pytest.mark.asyncio
async def test_regression_badcase_duplicate_unique_tools_cleaned():
    """Bad Case 4: Unique tools like lighter, metal_box, rope, stone_blade must not duplicate."""
    mgr = ScenarioManager()
    driver = EmptyMockDriver()
    bridge = AGUIBridge(scenario_mgr=mgr, driver=driver)

    # Client state containing 3 identical lighters
    client_state = {
        "current_scene": "beach",
        "hp": 90,
        "san": 85,
        "attributes": {"stamina": 75, "hydration": 65, "fullness": 60},
        "inventory": [
            {"id": "lighter", "name": "防风打火机"},
            {"id": "lighter", "name": "防风打火机"},
            {"id": "lighter", "name": "防风打火机"},
            {"id": "glass_bottle", "name": "厚壁玻璃瓶"},
        ],
        "variables": {},
    }

    inp = RunAgentInput(
        thread_id="test_bc4_dedup",
        run_id="run_bc4_1",
        messages=[
            {
                "id": "msg-bc4-1",
                "role": "user",
                "content": [{"type": "text", "text": "清点背包"}],
            }
        ],
        forwarded_props={
            "scenario_id": "island_survival",
            "player_state": client_state,
        },
    )

    events = []
    async for raw in bridge.stream_play(inp):
        events.append(raw)

    session = bridge.sessions["test_bc4_dedup"]
    lighter_count = sum(1 for item in session.player_state.inventory if item.get("id") == "lighter")
    assert lighter_count == 1, "Duplicate lighters must be deduplicated to exactly 1"

    # Also test add_inventory in apply_delta ignores duplicate unique tools
    patches = session.apply_delta({"add_inventory": [{"id": "lighter", "name": "防风打火机"}]})
    new_count = sum(1 for item in session.player_state.inventory if item.get("id") == "lighter")
    assert new_count == 1, "Adding existing unique tool must not create duplicate"


# ============================================================================
# BAD CASE 5: Rigid binary pass/fail check adjudication
# Reported: "应该让剧本和判定标准更灵活一些：让agent综合当前玩家状态，物品，规则和剧情综合给出判定结果"
# ============================================================================
def test_regression_badcase_flexible_dm_adjudication_tiers():
    """Bad Case 5: DM must compute multi-dimensional modifiers and 4-tier graded outcomes."""
    mgr = ScenarioManager()
    driver = EmptyMockDriver()
    bridge = AGUIBridge(scenario_mgr=mgr, driver=driver)
    session = bridge.get_or_create_session("test_bc5_adj", "island_survival")

    # Set up modifiers: Survival(14 -> +2), Outer(+2), Shoes(+1), Wrist(+1), Stamina>=75(+1) -> +7
    session.player_state.attributes["survival"] = 14
    session.player_state.attributes["stamina"] = 80
    session.player_state.attributes["hydration"] = 70
    session.player_state.attributes["fullness"] = 60
    session.player_state.outfit["outer"] = {"id": "jacket", "name": "冲锋外套"}

    # Base DC = 15, roll = 7 -> total = 14 -> partial_success (14 >= 15 - 3)
    res_partial = bridge.evaluate_agent_adjudication(
        skill="survival",
        base_dc=15,
        player_state=session.player_state,
        clean_action="在恶劣天气中探寻",
        client_roll=7,
    )
    assert res_partial["outcome"] == "partial_success"
    assert res_partial["isSuccess"] is True
    assert res_partial["total"] == 14
    assert res_partial["modifier"] == 7
    assert "冲锋外套" in res_partial["reason"]

    # Base DC = 15, roll = 15 -> total = 22 -> critical_success (22 >= 15 + 5)
    res_crit = bridge.evaluate_agent_adjudication(
        skill="survival",
        base_dc=15,
        player_state=session.player_state,
        clean_action="在恶劣天气中探寻",
        client_roll=15,
    )
    assert res_crit["outcome"] == "critical_success"
    assert res_crit["total"] == 22


# ============================================================================
# BAD CASE 6: Studio scenario modification live synchronization
# Reported: "还有 让剧本在sutdio里面的修改尽量立刻生效，切换到游玩模式 就生效这样的效果"
# ============================================================================
def test_regression_badcase_studio_scene_modification_live_sync():
    """Bad Case 6: Modifications made to a scene in Studio must take immediate effect."""
    mgr = ScenarioManager()
    # Read beach scene
    beach = mgr.get_scene("island_survival", "beach")
    assert beach is not None

    orig_desc = beach.description
    try:
        # Simulate Studio modification
        beach.description = orig_desc + "\n【测试Studio实时修改文本】"
        mgr.save_scene("island_survival", beach)

        # Get scene again from manager
        updated_beach = mgr.get_scene("island_survival", "beach")
        assert "【测试Studio实时修改文本】" in updated_beach.description
    finally:
        # Revert
        beach.description = orig_desc
        mgr.save_scene("island_survival", beach)


# ============================================================================
# BAD CASE 7: Scene-built structures & visuals leaked into new scene on transition
# Reported: "切换场景后 在原来的场景的东西也被带到了新的场景 修复这个问题！"
# ============================================================================
@pytest.mark.asyncio
async def test_regression_badcase_scene_structures_and_visuals_not_leaked_on_transition():
    """Bad Case 7: Structures and stale visuals from the previous scene must NOT carry over to a new scene."""
    from httpx import ASGITransport, AsyncClient
    from server.app import app, bridge as app_bridge
    from server.agent_driver import MockAgentDriver
    from server.scenario_manager import resolve_scene_decorations

    app_bridge.driver = EmptyMockDriver()
    thread_id = "test_bc7_scene_isolation"
    session = app_bridge.get_or_create_session(thread_id, "island_survival")
    session.player_state.inventory = [
        {"id": "branches", "name": "干燥树枝浮木"},
        {"id": "rope", "name": "坚韧纤维绳"},
        {"id": "lighter", "name": "防风打火机"},
        {"id": "glass_bottle", "name": "厚壁玻璃瓶"},
    ]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Build shelter, campfire, water collector, and a custom structure on beach
        await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "bc7-1",
                "messages": [{"id": "m1", "role": "user", "content": [{"type": "text", "text": "用树枝和纤维绳搭建防风窝棚"}]}],
                "forwarded_props": {"scenario_id": "island_survival"},
            },
        )
        session.player_state.inventory.append({"id": "rope", "name": "坚韧纤维绳"})
        await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "bc7-2",
                "messages": [{"id": "m2", "role": "user", "content": [{"type": "text", "text": "用打火机点燃树枝生起篝火"}]}],
                "forwarded_props": {"scenario_id": "island_survival"},
            },
        )
        await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "bc7-3",
                "messages": [{"id": "m3", "role": "user", "content": [{"type": "text", "text": "搭建简易雨水收集器"}]}],
                "forwarded_props": {"scenario_id": "island_survival"},
            },
        )
        session.apply_delta({
            "add_structures": [
                {
                    "id": "custom_drying_rack",
                    "name": "沙滩晾晒架",
                    "image": "/assets/items/branches.png",
                    "side": "right",
                }
            ]
        })

        beach_state = (await ac.get(f"/api/session/{thread_id}/state")).json()
        beach_dec_ids = {d["id"] for d in beach_state["decorations"]}
        assert {"built_shelter", "built_campfire", "built_water_collector", "custom_drying_rack"} <= beach_dec_ids

        # 2. Transition from beach -> coastal_jungle
        await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "bc7-4",
                "messages": [{"id": "m4", "role": "user", "content": [{"type": "text", "text": "【转移场景】离开沙滩，向海边丛林前进"}]}],
                "forwarded_props": {"scenario_id": "island_survival", "action_id": "enter_coastal_jungle"},
            },
        )

        cj_state = (await ac.get(f"/api/session/{thread_id}/state")).json()
        assert cj_state["player_state"]["current_scene"] == "coastal_jungle"
        cj_dec_ids = {d["id"] for d in cj_state["decorations"]}
        assert "built_shelter" not in cj_dec_ids
        assert "built_campfire" not in cj_dec_ids
        assert "built_water_collector" not in cj_dec_ids
        assert "custom_drying_rack" not in cj_dec_ids

        cj_action_ids = {a["id"] for a in cj_state["available_actions"]}
        assert "rest_in_shelter_coastal" not in cj_action_ids
        assert "collect_water_coastal" not in cj_action_ids
        assert "coastal_cook_food" not in cj_action_ids
        assert "coastal_campfire" in cj_action_ids

        # Adjudication in coastal_jungle must not get beach shelter/fire bonuses
        adj = app_bridge.evaluate_agent_adjudication(
            skill="survival",
            base_dc=10,
            player_state=session.player_state,
            clean_action="在丛林里过夜休息",
            client_roll=10,
        )
        assert "稳固防风窝棚" not in adj["reason"]
        assert "温暖营地篝火" not in adj["reason"]

        # 3. Return to beach -> beach structures are still preserved on beach
        await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "bc7-5",
                "messages": [{"id": "m5", "role": "user", "content": [{"type": "text", "text": "【转移场景】原路返回视线开阔的沙滩"}]}],
                "forwarded_props": {"scenario_id": "island_survival", "action_id": "return_to_beach"},
            },
        )
        back_state = (await ac.get(f"/api/session/{thread_id}/state")).json()
        assert back_state["player_state"]["current_scene"] == "beach"
        back_dec_ids = {d["id"] for d in back_state["decorations"]}
        assert {"built_shelter", "built_campfire", "built_water_collector", "custom_drying_rack"} <= back_dec_ids

        # 4. LLM transition with stale background & omitted foreground/hero_image is sanitized
        app_bridge.driver = MockAgentDriver(mock_responses=[
            (
                "你拨开灌木走进了海边丛林。\n\n"
                "```state_delta\n"
                '{"current_scene": "coastal_jungle", "visuals": {"background": "/assets/scenes/island_beach.png"}}\n'
                "```"
            )
        ])
        res_llm = await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "bc7-6",
                "messages": [{"id": "m6", "role": "user", "content": [{"type": "text", "text": "前往海边丛林"}]}],
                "forwarded_props": {"scenario_id": "island_survival"},
            },
        )
        assert res_llm.status_code == 200
        state_deltas = []
        for line in res_llm.text.strip().split("\n"):
            if line.startswith("data: "):
                ev = json.loads(line[6:])
                if ev.get("type") == "STATE_DELTA":
                    state_deltas.extend(ev.get("delta", []))
        vis_patch = next(p["value"] for p in state_deltas if p.get("path") == "/visuals")
        assert vis_patch["background"] == "/assets/scenes/coastal_jungle.png"
        assert vis_patch["foreground"] == ""
        assert vis_patch["hero_image"] == ""

    # 5. Deep jungle has no pre-lit campfire hero_image or beach decorations
    deep_scene = app_bridge.scenario_mgr.get_scene("island_survival", "deep_jungle")
    assert deep_scene is not None
    assert deep_scene.hero_image == ""
    deep_decs = resolve_scene_decorations(deep_scene, session.player_state)
    assert not any(d.category == "structure" for d in deep_decs)


# ============================================================================
# BAD CASE 8: Scenario switching must isolate dialogue history and player state
# Reported: "切换剧本后 对话历史等内容不跟着变化"
# ============================================================================
@pytest.mark.asyncio
async def test_regression_badcase_scenario_switching_isolation():
    """Bad Case 8: Switching between scenarios must guarantee complete isolation of scenes, state and dialogues."""
    from httpx import ASGITransport, AsyncClient
    from server.app import app, bridge as app_bridge
    from server.agent_driver import MockAgentDriver

    mgr = ScenarioManager()
    # 1. 验证剧本列表中包含全部剧本且各剧本初始设定独立
    summaries = mgr.list_scenario_summaries()
    scenario_ids = [s["id"] for s in summaries]
    assert "island_survival" in scenario_ids
    assert "wow_elwynn_rpg" in scenario_ids
    assert "black_crow_manor" in scenario_ids

    spec_island = mgr.load_scenario("island_survival")
    spec_wow = mgr.load_scenario("wow_elwynn_rpg")
    assert spec_island.world.id == "island_survival"
    assert spec_island.world.initial_scene == "beach"
    assert spec_island.world.initial_player_state.name == "幸存者"

    assert spec_wow.world.id == "wow_elwynn_rpg"
    assert spec_wow.world.initial_scene == "northshire_abbey"
    assert spec_wow.world.initial_player_state.name == "艾泽拉斯新兵"
    wow_inv_names = [it["name"] for it in spec_wow.world.initial_player_state.inventory]
    assert any("炉石" in n for n in wow_inv_names)

    # 2. 模拟分别建立 island 与 wow 会话，验证会话间状态完全隔离
    app_bridge.driver = MockAgentDriver(mock_responses=["你环顾修道院广场。"])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # A. 运行 island_survival 回合
        res_island = await ac.post(
            "/api/play/run",
            json={
                "thread_id": "test_switch_session_island",
                "run_id": "run-switch-1",
                "messages": [{"id": "m1", "role": "user", "content": [{"type": "text", "text": "检查沙滩"}]}],
                "forwarded_props": {"scenario_id": "island_survival"},
            },
        )
        assert res_island.status_code == 200

        # B. 运行 wow_elwynn_rpg 回合
        res_wow = await ac.post(
            "/api/play/run",
            json={
                "thread_id": "test_switch_session_wow",
                "run_id": "run-switch-2",
                "messages": [{"id": "m2", "role": "user", "content": [{"type": "text", "text": "查看北郡征召榜"}]}],
                "forwarded_props": {"scenario_id": "wow_elwynn_rpg"},
            },
        )
        assert res_wow.status_code == 200

        # C. 验证从 bridge 获取的会话状态相互隔离，无任何串染
        session_island = app_bridge.get_or_create_session("test_switch_session_island", "island_survival")
        session_wow = app_bridge.get_or_create_session("test_switch_session_wow", "wow_elwynn_rpg")

        assert session_island.scenario_id == "island_survival"
        assert session_island.player_state.current_scene == "beach"
        assert session_island.player_state.name == "幸存者"

        assert session_wow.scenario_id == "wow_elwynn_rpg"
        assert session_wow.player_state.current_scene == "northshire_abbey"
        assert session_wow.player_state.name == "艾泽拉斯新兵"
        assert "炉石" in [it["id"] for it in session_wow.player_state.inventory]
        assert "lighter" not in [it.get("id") for it in session_wow.player_state.inventory]

