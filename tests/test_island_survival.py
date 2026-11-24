"""End-to-end tests for the Island Survival (荒岛余生) scenario."""

import pytest
from pathlib import Path
from httpx import ASGITransport, AsyncClient
from server.app import app, bridge
from server.agent_driver import MockAgentDriver
from server.scenario_manager import ScenarioManager
from server.script_linter import ScriptLinter


def test_island_survival_scenario_spec():
    """Verify that island_survival scenario and all 3 scenes pass validation."""
    sm = ScenarioManager()
    assert "island_survival" in sm.list_scenarios()

    spec = sm.load_scenario("island_survival")
    assert spec.world.id == "island_survival"
    assert spec.world.title == "荒岛余生"
    assert spec.world.initial_scene == "beach"

    # Verify survival body attributes
    attrs = spec.world.initial_player_state.attributes
    assert "stamina" in attrs
    assert "hydration" in attrs
    assert "fullness" in attrs
    assert "temperature" in attrs

    # Verify all 3 maps exist
    assert "beach" in spec.scenes
    assert "coastal_jungle" in spec.scenes
    assert "deep_jungle" in spec.scenes

    # Lint check
    report = ScriptLinter.lint_scenario(spec)
    assert report.valid is True
    assert report.errors == 0


def test_island_survival_assets_exist():
    """Verify that background, item, and scenic decoration assets exist both in co-located scenario assets and web/public/assets."""
    base = Path(__file__).resolve().parent.parent / "web" / "public" / "assets"
    co_located = Path(__file__).resolve().parent.parent / "scripts" / "island_survival" / "assets"

    for root_dir in (base, co_located):
        # 3 scene backgrounds
        assert (root_dir / "scenes" / "island_beach.png").exists()
        assert (root_dir / "scenes" / "coastal_jungle.png").exists()
        assert (root_dir / "scenes" / "deep_jungle.png").exists()

        # Item icons
        assert (root_dir / "items" / "lighter.png").exists()
        assert (root_dir / "items" / "rope.png").exists()
        assert (root_dir / "items" / "glass_bottle.png").exists()
        assert (root_dir / "items" / "branches.png").exists()

        # 5 margin scenery props requested by user: seashell, crab, palmtree, vines, rocks
        assert (root_dir / "props" / "seashell.png").exists()
        assert (root_dir / "props" / "crab.png").exists()
        assert (root_dir / "props" / "palmtree.png").exists()
        assert (root_dir / "props" / "vines.png").exists()
        assert (root_dir / "props" / "rocks.png").exists()

        # Built durable survival structure props
        assert (root_dir / "props" / "shelter.png").exists()
        assert (root_dir / "props" / "water_collector.png").exists()



def test_island_survival_decorations_and_margin_props():
    """Verify that all scenes have configured left and right margin decorations."""
    sm = ScenarioManager()
    spec = sm.load_scenario("island_survival")

    # Beach decorations
    beach = spec.scenes["beach"]
    assert beach.visuals is not None
    beach_decs = beach.visuals.decorations
    assert len(beach_decs) >= 4
    beach_sides = {d.side for d in beach_decs}
    assert "left" in beach_sides and "right" in beach_sides
    dec_ids = {d.id for d in beach_decs}
    assert "palm_beach" in dec_ids
    assert "crab_beach" in dec_ids
    assert "shell_beach" in dec_ids
    assert "rock_beach" in dec_ids

    # Coastal jungle decorations
    cj = spec.scenes["coastal_jungle"]
    assert cj.visuals is not None
    cj_decs = cj.visuals.decorations
    assert any(d.id == "palm_jungle" for d in cj_decs)
    assert any(d.id == "vines_jungle" for d in cj_decs)

    # Deep jungle decorations
    dj = spec.scenes["deep_jungle"]
    assert dj.visuals is not None
    dj_decs = dj.visuals.decorations
    assert any(d.id == "vines_deep" for d in dj_decs)
    assert any(d.id == "rocks_deep" for d in dj_decs)



@pytest.mark.asyncio
async def test_island_survival_play_flow():
    """Verify complete gameplay loop in island_survival: beach search -> jungle transit -> campfire."""
    mock_responses = [
        # Turn 1: Beach search -> find lighter, glass bottle, branches
        (
            "你跪在滚烫的沙滩上用力撬开了失事残骸中的防水金属盒！里面赫然躺着一只防风打火机和一只完好的厚壁玻璃瓶。\n\n"
            "```state_delta\n"
            "{\n"
            '  "add_inventory": [\n'
            '    {"id": "lighter", "name": "防风打火机"},\n'
            '    {"id": "glass_bottle", "name": "厚壁玻璃瓶"},\n'
            '    {"id": "branches", "name": "干燥树枝浮木"}\n'
            "  ],\n"
            '  "attributes": {"stamina": 90, "hydration": 65},\n'
            '  "visuals": {\n'
            '    "background": "/assets/scenes/island_beach.png",\n'
            '    "hero_image": "/assets/items/lighter.png"\n'
            "  }\n"
            "}\n"
            "```"
        ),
        # Turn 2: Move to coastal jungle -> craft rope
        (
            "你迈步穿过碎石滩，钻入了海边茂密的密林阴凉处。你用随手折断的利木剥取老藤，编织出一捆结实的纤维绳！\n\n"
            "```state_delta\n"
            "{\n"
            '  "current_scene": "coastal_jungle",\n'
            '  "add_inventory": [{"id": "rope", "name": "坚韧纤维绳"}],\n'
            '  "attributes": {"stamina": 80, "hydration": 55},\n'
            '  "visuals": {\n'
            '    "background": "/assets/scenes/coastal_jungle.png",\n'
            '    "hero_image": "/assets/items/rope.png"\n'
            "  }\n"
            "}\n"
            "```"
        ),
        # Turn 3: Deep jungle exploration -> campfire & fresh water
        (
            "你拨开巨型蕨类植物，终于抵达了古木参天的丛林深处！清澈的山溪在眼前流淌。你用玻璃瓶灌满甘泉，并用收集的干燥树枝和打火机成功点燃了温暖的营火！\n\n"
            "```state_delta\n"
            "{\n"
            '  "current_scene": "deep_jungle",\n'
            '  "variables": {"fire_started": true, "water_purified": true},\n'
            '  "attributes": {"hydration": 95, "temperature": 37},\n'
            '  "visuals": {\n'
            '    "background": "/assets/scenes/deep_jungle.png",\n'
            '    "hero_image": "/assets/illustrations/campfire.png"\n'
            "  }\n"
            "}\n"
            "```"
        ),
    ]

    bridge.driver = MockAgentDriver(mock_responses=mock_responses)
    thread_id = "test-island-survival-thread"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Turn 1: Search beach
        res1 = await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "island-run-1",
                "messages": [
                    {"id": "m1", "role": "user", "content": [{"type": "text", "text": "【搜寻沙滩】搜查半掩在沙里的防水金属盒与漂流物"}]}
                ],
                "forwarded_props": {"scenario_id": "island_survival"},
            },
        )
        assert res1.status_code == 200
        assert "lighter" in res1.text
        assert "glass_bottle" in res1.text

        # Verify state after turn 1
        s1 = (await ac.get(f"/api/session/{thread_id}/state")).json()
        item_ids = [i["id"] for i in s1["player_state"]["inventory"]]
        assert "lighter" in item_ids
        assert "glass_bottle" in item_ids
        assert "branches" in item_ids
        # Item metadata enriched
        lighter_item = next(i for i in s1["player_state"]["inventory"] if i["id"] == "lighter")
        assert lighter_item["name"] == "防风打火机"
        assert "/assets/items/lighter.png" in lighter_item["icon"]

        # Turn 2: Move to coastal jungle
        res2 = await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "island-run-2",
                "messages": [
                    {"id": "m2", "role": "user", "content": [{"type": "text", "text": "【转移场景】离开沙滩，向海边丛林前进"}]}
                ],
                "forwarded_props": {"scenario_id": "island_survival"},
            },
        )
        assert res2.status_code == 200
        assert "coastal_jungle" in res2.text

        s2 = (await ac.get(f"/api/session/{thread_id}/state")).json()
        assert s2["player_state"]["current_scene"] == "coastal_jungle"
        item_ids_2 = [i["id"] for i in s2["player_state"]["inventory"]]
        assert "rope" in item_ids_2

        # Turn 3: Move to deep jungle & campfire
        res3 = await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "island-run-3",
                "messages": [
                    {"id": "m3", "role": "user", "content": [{"type": "text", "text": "【深入密林】生起篝火并汲取溪流淡水"}]}
                ],
                "forwarded_props": {"scenario_id": "island_survival"},
            },
        )
        assert res3.status_code == 200
        assert "deep_jungle" in res3.text

        # Final verification of session state
        s3 = (await ac.get(f"/api/session/{thread_id}/state")).json()
        assert s3["player_state"]["current_scene"] == "deep_jungle"
        assert s3["player_state"]["variables"]["fire_started"] is True
        assert s3["player_state"]["attributes"]["hydration"] == 95

        # Check all 4 requested items exist in inventory: lighter, rope, glass_bottle, branches
        final_inv_ids = [i["id"] for i in s3["player_state"]["inventory"]]
        for required_item in ["lighter", "rope", "glass_bottle", "branches"]:
            assert required_item in final_inv_ids


@pytest.mark.asyncio
async def test_eating_updates_fullness_and_dynamic_options():
    """Verify eating updates fullness/stamina, consumes food, advances time, and updates available_actions."""
    mock_responses = [
        # Turn 1: Forage food in deep jungle (preset action_id=forage_food, check_passed=True)
        "你在林间摘到了饱满的野生坚果与棕榈芯。\n\n```state_delta\n{}\n```",
        # Turn 2: Eat wild_food via preset action_id=eat_wild_food_raw (even without LLM state_delta!)
        "你大口吃下野生坚果与棕榈芯，腹中的饥饿感瞬间消退。\n\n```state_delta\n{}\n```",
        # Turn 3: Custom free-text eat/drink with attributes_delta & dynamic available_actions
        (
            "你又捧起溪水畅饮几口，并在岸边发现了一只搁浅的大海蟹！\n\n"
            "```state_delta\n"
            "{\n"
            '  "attributes_delta": {"hydration": 20, "fullness": -5},\n'
            '  "time_cost": 3,\n'
            '  "available_actions": [\n'
            '    {"id": "inspect_signal_flare", "label": "查看林间挂在树梢的信号弹残骸", "type": "interact"}\n'
            "  ]\n"
            "}\n"
            "```"
        ),
    ]

    bridge.driver = MockAgentDriver(mock_responses=mock_responses)
    thread_id = "test-island-eat-dynamic"

    # Pre-create session and place player in deep_jungle with low fullness
    session = bridge.get_or_create_session(thread_id, "island_survival")
    session.player_state.current_scene = "deep_jungle"
    session.player_state.attributes["fullness"] = 40
    session.player_state.attributes["stamina"] = 60

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Turn 1: Forage food
        res1 = await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "eat-run-1",
                "messages": [{"id": "m1", "role": "user", "content": [{"type": "text", "text": "【执行检定】搜寻野生棕榈芯与热带坚果"}]}],
                "forwarded_props": {
                    "scenario_id": "island_survival",
                    "action_id": "forage_food",
                    "check_passed": True,
                },
            },
        )
        assert res1.status_code == 200
        s1 = (await ac.get(f"/api/session/{thread_id}/state")).json()
        assert any(i["id"] == "wild_food" for i in s1["player_state"]["inventory"])
        action_ids_1 = [a["id"] for a in s1["available_actions"]]
        # eat_wild_food_raw is now dynamically available, forage_food is hidden while holding wild_food
        assert "eat_wild_food_raw" in action_ids_1
        assert "forage_food" not in action_ids_1

        fullness_before_eat = s1["player_state"]["attributes"]["fullness"]
        stamina_before_eat = s1["player_state"]["attributes"]["stamina"]

        # Turn 2: Eat wild_food
        res2 = await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "eat-run-2",
                "messages": [{"id": "m2", "role": "user", "content": [{"type": "text", "text": "【收集/互动】直接食用背包里的野生坚果与棕榈芯充饥"}]}],
                "forwarded_props": {
                    "scenario_id": "island_survival",
                    "action_id": "eat_wild_food_raw",
                    "check_passed": True,
                },
            },
        )
        assert res2.status_code == 200
        assert "/attributes/fullness" in res2.text
        assert "/available_actions" in res2.text

        s2 = (await ac.get(f"/api/session/{thread_id}/state")).json()
        assert s2["player_state"]["attributes"]["fullness"] == min(100, fullness_before_eat + 28)
        assert s2["player_state"]["attributes"]["stamina"] == min(100, stamina_before_eat + 12)
        assert not any(i["id"] == "wild_food" for i in s2["player_state"]["inventory"])
        action_ids_2 = [a["id"] for a in s2["available_actions"]]
        # After eating, eat_wild_food_raw disappears and forage_food becomes available again
        assert "eat_wild_food_raw" not in action_ids_2
        assert "forage_food" in action_ids_2

        # Turn 3: Time advances into night + DM injects dynamic action
        res3 = await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "eat-run-3",
                "messages": [{"id": "m3", "role": "user", "content": [{"type": "text", "text": "喝水并环顾四周"}]}],
                "forwarded_props": {"scenario_id": "island_survival"},
            },
        )
        assert res3.status_code == 200
        s3 = (await ac.get(f"/api/session/{thread_id}/state")).json()
        # Time started at 上午 (+1 from forage = 下午, +3 = 深夜)
        assert s3["player_state"]["variables"]["time_slot"] == "深夜"
        action_ids_3 = [a["id"] for a in s3["available_actions"]]
        # Daytime foraging hidden at night; DM dynamic action present
        assert "forage_food" not in action_ids_3
        assert "inspect_signal_flare" in action_ids_3


@pytest.mark.asyncio
async def test_custom_pickup_metal_box_with_llm_preserves_intent():
    """Free-form '捡起防水金属盒，洗干净带走' must keep LLM's metal_box inventory delta without forcing lighter."""
    mock_responses = [
        (
            "你弯腰将半掩在沙砾中的防水金属盒刨了出来，提着它走到浅浪处仔细冲洗掉外壳泥沙，擦干后收入背包。\n\n"
            "```state_delta\n"
            "{\n"
            '  "add_inventory": [{"id": "metal_box", "name": "防水金属盒"}],\n'
            '  "variables": {"found_metal_box": true},\n'
            '  "attributes_delta": {"stamina": -3, "hydration": -2},\n'
            '  "time_cost": 1,\n'
            '  "visuals": {"background": "/assets/scenes/island_beach.png", "foreground": "", "hero_image": "【物品特写】洗净泥沙的防水金属盒"}\n'
            "}\n"
            "```"
        )
    ]
    bridge.driver = MockAgentDriver(mock_responses=mock_responses)
    thread_id = "test-custom-metal-box-llm"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "run-box-llm-1",
                "messages": [{"id": "m1", "role": "user", "content": [{"type": "text", "text": "捡起防水金属盒，洗干净带走"}]}],
                "forwarded_props": {"scenario_id": "island_survival"},
            },
        )
        assert res.status_code == 200
        state = (await ac.get(f"/api/session/{thread_id}/state")).json()
        inv_ids = [i["id"] for i in state["player_state"]["inventory"]]
        assert "metal_box" in inv_ids
        assert "lighter" not in inv_ids
        metal_box = next(i for i in state["player_state"]["inventory"] if i["id"] == "metal_box")
        assert metal_box["name"] == "防水金属盒"
        assert "铝合金" in metal_box["desc"]

        avail_ids = [a["id"] for a in state["available_actions"]]
        assert "pickup_metal_box" not in avail_ids
        assert "search_luggage" in avail_ids

    # Verify history was recorded for subsequent turns
    session = bridge.sessions[thread_id]
    assert len(session.history) == 2
    next_prompt = bridge.build_play_prompt(session, "打开金属盒看看里面有什么")
    assert "近期剧情回溯" in next_prompt
    assert "玩家意图忠实原则" in next_prompt


@pytest.mark.asyncio
async def test_built_durable_structures_appear_in_side_decorations():
    """Verify shelter, campfire, water collector, and dynamic structures appear in left/right decorations only after being built."""
    from server.scenario_manager import resolve_scene_decorations
    from server.agui_bridge import AGUIBridge
    from tests.test_fallback_director import EmptyMockDriver

    sm = ScenarioManager()
    local_bridge = AGUIBridge(scenario_mgr=sm, driver=EmptyMockDriver())
    thread_id = "test-built-structures-thread"
    session = local_bridge.get_or_create_session(thread_id, "island_survival")
    beach = sm.get_scene("island_survival", "beach")
    assert beach is not None

    # 1. Initially, no built structures are shown in decorations
    initial_decs = resolve_scene_decorations(beach, session.player_state)
    initial_ids = {d.id for d in initial_decs}
    assert "palm_beach" in initial_ids
    assert "built_shelter" not in initial_ids
    assert "built_campfire" not in initial_ids
    assert "built_water_collector" not in initial_ids

    # 2. Give materials and build shelter via freeform input
    session.player_state.inventory.extend([
        {"id": "branches", "name": "干燥树枝浮木"},
        {"id": "rope", "name": "坚韧纤维绳"},
        {"id": "lighter", "name": "防风打火机"},
        {"id": "glass_bottle", "name": "厚壁玻璃瓶"},
    ])

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Use global bridge for HTTP endpoint check
        srv_session = bridge.get_or_create_session(thread_id, "island_survival")
        srv_session.player_state.inventory = list(session.player_state.inventory)
        bridge.driver = EmptyMockDriver()

        # Build shelter
        res_shelter = await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "run-build-shelter",
                "messages": [{"id": "m1", "role": "user", "content": [{"type": "text", "text": "用树枝和纤维绳搭建防风窝棚"}]}],
                "forwarded_props": {"scenario_id": "island_survival"},
            },
        )
        assert res_shelter.status_code == 200
        s1 = (await ac.get(f"/api/session/{thread_id}/state")).json()
        assert s1["player_state"]["variables"]["shelter_level"] >= 1
        dec_map_1 = {d["id"]: d for d in s1["decorations"]}
        assert "built_shelter" in dec_map_1
        assert dec_map_1["built_shelter"]["side"] == "left"
        assert dec_map_1["built_shelter"]["category"] == "structure"
        assert "built_campfire" not in dec_map_1

        # Light campfire
        res_fire = await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "run-light-fire",
                "messages": [{"id": "m2", "role": "user", "content": [{"type": "text", "text": "用打火机点燃树枝生起篝火"}]}],
                "forwarded_props": {"scenario_id": "island_survival"},
            },
        )
        assert res_fire.status_code == 200
        s2 = (await ac.get(f"/api/session/{thread_id}/state")).json()
        assert s2["player_state"]["variables"]["fire_started"] is True
        dec_map_2 = {d["id"]: d for d in s2["decorations"]}
        assert "built_shelter" in dec_map_2
        assert "built_campfire" in dec_map_2
        assert dec_map_2["built_campfire"]["side"] == "right"
        assert dec_map_2["built_campfire"]["category"] == "structure"

        # Re-supply rope (consumed by shelter construction) and build water collector
        srv_session.player_state.inventory.append({"id": "rope", "name": "坚韧纤维绳"})
        res_wc = await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "run-build-wc",
                "messages": [{"id": "m3", "role": "user", "content": [{"type": "text", "text": "搭建简易雨水收集器"}]}],
                "forwarded_props": {"scenario_id": "island_survival"},
            },
        )
        assert res_wc.status_code == 200
        s3 = (await ac.get(f"/api/session/{thread_id}/state")).json()
        assert s3["player_state"]["variables"]["water_collector_built"] is True
        dec_map_3 = {d["id"]: d for d in s3["decorations"]}
        assert "built_water_collector" in dec_map_3
        assert dec_map_3["built_water_collector"]["side"] == "left"

    # 3. Verify dynamic custom structure via add_structures delta
    srv_session.apply_delta({
        "add_structures": [
            {
                "id": "custom_drying_rack",
                "name": "木制晾晒架",
                "image": "/assets/items/branches.png",
                "side": "right",
                "caption": "营地晾晒架",
            }
        ]
    })
    final_decs = resolve_scene_decorations(beach, srv_session.player_state)
    assert any(d.id == "custom_drying_rack" and d.side == "right" and d.category == "structure" for d in final_decs)
