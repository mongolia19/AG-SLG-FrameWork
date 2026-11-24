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
