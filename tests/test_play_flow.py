import pytest
from httpx import ASGITransport, AsyncClient
from server.app import app, bridge
from server.agent_driver import MockAgentDriver


@pytest.mark.asyncio
async def test_three_turn_play_branching():
    """Verify that a player can progress through at least 3 story branches with state sync."""
    # Configure mock driver to simulate realistic responses with state_delta
    mock_responses = [
        # Turn 1: Check coat rack -> gain silver_key, move to manor_foyer
        (
            "你仔细翻查了湿透的雨衣，在内衬暗袋摸到一把雕花银钥匙！\n\n"
            "```state_delta\n"
            '{"current_scene": "manor_foyer", "add_inventory": [{"id": "silver_key", "name": "雕花银钥匙"}], "san_delta": -2}\n'
            "```"
        ),
        # Turn 2: Transition to drawing room
        (
            "你沿着昏暗的走廊快步向前，推开了沉重的红木雕花门，来到了庄园会客室。\n\n"
            "```state_delta\n"
            '{"current_scene": "drawing_room", "variables": {"explored_foyer": true}}\n'
            "```"
        ),
        # Turn 3: Search desk -> gain torn_letter
        (
            "你在书桌夹层中发现了一封泛黄的信件残片，上面写着关于公馆密室的警告。\n\n"
            "```state_delta\n"
            '{"add_inventory": [{"id": "torn_letter", "name": "撕毁的信件残片"}], "variables": {"found_letter": true}}\n'
            "```"
        ),
    ]

    bridge.driver = MockAgentDriver(mock_responses=mock_responses)
    thread_id = "test-three-turn-thread"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Turn 1:
        res1 = await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "run-1",
                "messages": [
                    {"id": "m1", "role": "user", "content": [{"type": "text", "text": "【执行检定】调查衣帽架旁滴水的雨衣"}]}
                ],
                "forwarded_props": {"scenario_id": "black_crow_manor"},
            },
        )
        assert res1.status_code == 200
        assert "manor_foyer" in res1.text
        assert "silver_key" in res1.text

        # Verify state after turn 1
        s1 = (await ac.get(f"/api/session/{thread_id}/state")).json()
        assert s1["player_state"]["current_scene"] == "manor_foyer"
        assert s1["player_state"]["san"] == 78  # 80 - 2
        assert any(i["id"] == "silver_key" for i in s1["player_state"]["inventory"])

        # Turn 2:
        res2 = await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "run-2",
                "messages": [
                    {"id": "m2", "role": "user", "content": [{"type": "text", "text": "【转移场景】穿过门厅前往会客室"}]}
                ],
                "forwarded_props": {"scenario_id": "black_crow_manor"},
            },
        )
        assert res2.status_code == 200
        assert "drawing_room" in res2.text

        # Verify state after turn 2
        s2 = (await ac.get(f"/api/session/{thread_id}/state")).json()
        assert s2["player_state"]["current_scene"] == "drawing_room"
        assert s2["player_state"]["variables"].get("explored_foyer") is True

        # Turn 3:
        res3 = await ac.post(
            "/api/play/run",
            json={
                "thread_id": thread_id,
                "run_id": "run-3",
                "messages": [
                    {"id": "m3", "role": "user", "content": [{"type": "text", "text": "【执行检定】搜查书桌上的信件"}]}
                ],
                "forwarded_props": {"scenario_id": "black_crow_manor"},
            },
        )
        assert res3.status_code == 200
        assert "torn_letter" in res3.text

        # Verify state after turn 3
        s3 = (await ac.get(f"/api/session/{thread_id}/state")).json()
        assert any(i["id"] == "torn_letter" for i in s3["player_state"]["inventory"])
        assert s3["player_state"]["variables"].get("found_letter") is True
        assert len(s3["player_state"]["inventory"]) >= 3  # magnifying_glass + silver_key + torn_letter
