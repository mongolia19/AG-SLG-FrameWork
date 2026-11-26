"""Tests for manual play progress save / list / load / delete endpoints."""

import json
import time

import pytest
from httpx import ASGITransport, AsyncClient

import server.app as app_module
from server.agent_driver import MockAgentDriver


@pytest.fixture
def isolated_saves(tmp_path, monkeypatch):
    saves_dir = tmp_path / "saves"
    monkeypatch.setattr(app_module, "SAVES_DIR", saves_dir)
    orig_driver = app_module.bridge.driver
    app_module.bridge.driver = MockAgentDriver(
        mock_responses=[
            "你检查了书桌抽屉。\n\n```state_delta\n"
            '{"variables": {"checked_desk": true}}\n'
            "```"
        ]
    )
    yield saves_dir
    app_module.bridge.driver = orig_driver


@pytest.mark.asyncio
async def test_save_list_load_delete_and_validation(isolated_saves):
    async with AsyncClient(transport=ASGITransport(app=app_module.app), base_url="http://test") as ac:
        # Initially empty
        r0 = await ac.get("/api/scenarios/black_crow_manor/saves")
        assert r0.status_code == 200
        assert r0.json()["saves"] == []

        # Create first save with custom name
        payload_1 = {
            "name": "进入大厅前",
            "scene_title": "黑鸦庄园入口",
            "player_state": {
                "name": "调查员",
                "hp": 85,
                "max_hp": 100,
                "san": 72,
                "gold": 50,
                "current_scene": "manor_entrance",
                "inventory": [{"id": "brass_key", "name": "黄铜钥匙"}],
                "variables": {"found_note": True},
            },
            "messages": [{"id": "m1", "kind": "narrator", "content": "雨夜降临。", "timestamp": 1000}],
            "active_visuals": {"atmosphere": "暴雨倾盆"},
            "dynamic_actions": [{"id": "a1", "label": "敲门", "type": "interact"}],
            "last_turn": {"prompt": "查看门牌", "base": {"playerState": {}, "messages": []}},
        }
        c1 = await ac.post("/api/scenarios/black_crow_manor/saves", json=payload_1)
        assert c1.status_code == 200
        s1 = c1.json()["save"]
        assert s1["name"] == "进入大厅前"
        assert s1["hp"] == 85
        assert s1["scene_id"] == "manor_entrance"

        time.sleep(0.01)

        # Create second save without name -> uses default scene_title + time
        payload_2 = {
            "player_state": {
                "name": "调查员",
                "hp": 60,
                "max_hp": 100,
                "current_scene": "drawing_room",
                "inventory": [],
                "variables": {},
            },
            "messages": [{"id": "m2", "kind": "narrator", "content": "进入会客室。", "timestamp": 2000}],
        }
        c2 = await ac.post("/api/scenarios/black_crow_manor/saves", json=payload_2)
        assert c2.status_code == 200
        s2 = c2.json()["save"]
        assert s2["name"]

        # List returns newest first and isolates per scenario
        lst = (await ac.get("/api/scenarios/black_crow_manor/saves")).json()["saves"]
        assert [item["id"] for item in lst] == [s2["id"], s1["id"]]
        other_lst = (await ac.get("/api/scenarios/island_survival/saves")).json()["saves"]
        assert other_lst == []

        # Load full snapshot and verify all fields preserved
        loaded = await ac.get(f"/api/scenarios/black_crow_manor/saves/{s1['id']}")
        assert loaded.status_code == 200
        full = loaded.json()["save"]
        assert full["player_state"]["variables"]["found_note"] is True
        assert full["player_state"]["inventory"][0]["id"] == "brass_key"
        assert full["active_visuals"] == {"atmosphere": "暴雨倾盆"}
        assert full["dynamic_actions"][0]["id"] == "a1"
        assert full["last_turn"]["prompt"] == "查看门牌"

        # Path traversal & missing resource guards
        assert (await ac.get("/api/scenarios/black_crow_manor/saves/..%2F..%2Fetc")).status_code in (400, 404)
        assert (await ac.get("/api/scenarios/black_crow_manor/saves/bad.id")).status_code == 400
        assert (await ac.get("/api/scenarios/nonexistent_scenario/saves")).status_code == 404
        assert (await ac.get("/api/scenarios/black_crow_manor/saves/save_missing")).status_code == 404

        # Delete save
        d1 = await ac.delete(f"/api/scenarios/black_crow_manor/saves/{s1['id']}")
        assert d1.status_code == 200
        lst_after = (await ac.get("/api/scenarios/black_crow_manor/saves")).json()["saves"]
        assert [item["id"] for item in lst_after] == [s2["id"]]


@pytest.mark.asyncio
async def test_loaded_save_continues_play_cleanly(isolated_saves):
    async with AsyncClient(transport=ASGITransport(app=app_module.app), base_url="http://test") as ac:
        created = await ac.post(
            "/api/scenarios/black_crow_manor/saves",
            json={
                "name": "书房存档点",
                "player_state": {
                    "name": "调查员",
                    "hp": 77,
                    "max_hp": 100,
                    "san": 65,
                    "gold": 12,
                    "current_scene": "drawing_room",
                    "inventory": [{"id": "silver_key", "name": "银钥匙"}],
                    "variables": {"opened_door": True},
                },
                "messages": [
                    {"id": "m1", "kind": "narrator", "content": "你进入了会客室。", "timestamp": 1000}
                ],
            },
        )
        save_id = created.json()["save"]["id"]
        saved = (await ac.get(f"/api/scenarios/black_crow_manor/saves/{save_id}")).json()["save"]

        # Simulate PlayView loading the save and starting the next turn with a fresh thread_id
        loaded_thread = "loaded-session-123"
        res = await ac.post(
            "/api/play/run",
            json={
                "thread_id": loaded_thread,
                "run_id": "run-after-load",
                "messages": [{"id": "u1", "role": "user", "content": [{"type": "text", "text": "检查书桌"}]}],
                "forwarded_props": {
                    "scenario_id": "black_crow_manor",
                    "player_state": saved["player_state"],
                    "recent_history": [{"role": "assistant", "content": saved["messages"][0]["content"]}],
                },
            },
        )
        assert res.status_code == 200
        assert "RUN_FINISHED" in res.text

        state_res = await ac.get(f"/api/session/{loaded_thread}/state")
        assert state_res.status_code == 200
        ps = state_res.json()["player_state"]
        assert ps["hp"] == 77
        assert ps["current_scene"] == "drawing_room"
        assert ps["variables"]["opened_door"] is True
        assert ps["variables"]["checked_desk"] is True
        assert any(it["id"] == "silver_key" for it in ps["inventory"])
