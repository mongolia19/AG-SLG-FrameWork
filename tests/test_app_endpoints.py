import pytest
from httpx import ASGITransport, AsyncClient
from server.app import app, bridge
from server.agent_driver import MockAgentDriver


@pytest.fixture(autouse=True)
def setup_mock_driver():
    # Ensure bridge uses mock driver during app tests
    bridge.driver = MockAgentDriver()


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_scenarios_api():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/scenarios")
        assert res.status_code == 200
        scenarios = res.json()["scenarios"]
        assert "black_crow_manor" in scenarios

        res_detail = await ac.get("/api/scenarios/black_crow_manor")
        assert res_detail.status_code == 200
        data = res_detail.json()
        assert data["world"]["id"] == "black_crow_manor"
        assert "manor_entrance" in data["scenes"]


@pytest.mark.asyncio
async def test_play_run_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        payload = {
            "thread_id": "test-http-thread",
            "run_id": "test-http-run",
            "messages": [
                {
                    "id": "msg-1",
                    "role": "user",
                    "content": [{"type": "text", "text": "前往阴暗会客室"}],
                }
            ],
            "forwarded_props": {"scenario_id": "black_crow_manor"},
        }
        res = await ac.post("/api/play/run", json=payload)
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]
        body = res.text
        assert "RUN_STARTED" in body
        assert "TEXT_MESSAGE_CONTENT" in body
        assert "RUN_FINISHED" in body

        # Check session state endpoint
        res_state = await ac.get("/api/session/test-http-thread/state")
        assert res_state.status_code == 200
        state_data = res_state.json()
        assert state_data["thread_id"] == "test-http-thread"
        assert state_data["scenario_id"] == "black_crow_manor"
