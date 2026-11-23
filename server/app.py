"""FastAPI AG-UI Bridge Server for AG-SLG-FrameWork."""

import os
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from ag_ui.core import RunAgentInput

from server.agent_driver import AgyDriver, CodexDriver, MockAgentDriver, BaseAgentDriver
from server.agui_bridge import AGUIBridge
from server.scenario_manager import ScenarioManager, SceneNode, resolve_scene_actions

app = FastAPI(title="AG-SLG-FrameWork Bridge Server", version="0.1.0")

# Enable CORS for local web dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
BASE_DIR = Path(__file__).resolve().parent.parent
scenario_manager = ScenarioManager(base_dir=BASE_DIR / "scripts")

# Select driver based on environment or availability
DRIVER_NAME = os.getenv("AG_DRIVER", "agy").lower()
if DRIVER_NAME == "mock":
    driver: BaseAgentDriver = MockAgentDriver()
elif DRIVER_NAME == "codex":
    driver = CodexDriver()
else:
    driver = AgyDriver()

bridge = AGUIBridge(scenario_mgr=scenario_manager, driver=driver)


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "driver": DRIVER_NAME}


@app.get("/api/scenarios")
def list_scenarios():
    scenarios = scenario_manager.list_scenarios()
    return {"scenarios": scenarios}


@app.get("/api/scenarios/{scenario_id}")
def get_scenario(scenario_id: str):
    try:
        spec = scenario_manager.load_scenario(scenario_id)
        return spec.model_dump()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Scenario not found")


@app.post("/api/scenarios/{scenario_id}/scenes")
def update_or_create_scene(scenario_id: str, scene: SceneNode):
    try:
        saved_path = scenario_manager.save_scene(scenario_id, scene)
        return {"status": "ok", "scene_id": scene.id, "path": str(saved_path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/scenarios/{scenario_id}/lint")
def lint_scenario_endpoint(scenario_id: str):
    from server.script_linter import ScriptLinter
    try:
        spec = scenario_manager.load_scenario(scenario_id)
        report = ScriptLinter.lint_scenario(spec)
        return report.model_dump()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Scenario not found")



@app.get("/api/session/{thread_id}/state")
def get_session_state(thread_id: str):
    if thread_id not in bridge.sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    session = bridge.sessions[thread_id]
    curr_scene = scenario_manager.get_scene(
        session.scenario_id, session.player_state.current_scene
    )
    resolved_actions = resolve_scene_actions(
        curr_scene, session.player_state, session.dynamic_actions
    )
    return {
        "thread_id": thread_id,
        "scenario_id": session.scenario_id,
        "player_state": session.player_state.model_dump(),
        "available_actions": [a.model_dump() for a in resolved_actions],
        "agent_conversation_id": session.agent_conversation_id,
    }


@app.post("/api/play/run")
async def run_play(input_data: RunAgentInput):
    """AG-UI Protocol Run Endpoint for Play Mode."""
    return StreamingResponse(
        bridge.stream_play(input_data),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/studio/run")
async def run_studio(input_data: RunAgentInput):
    """AG-UI Protocol Run Endpoint for Studio Mode."""
    return StreamingResponse(
        bridge.stream_studio(input_data),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# Mount static assets & web/dist
from fastapi.staticfiles import StaticFiles

PUBLIC_ASSETS = BASE_DIR / "web" / "public" / "assets"
if PUBLIC_ASSETS.exists():
    app.mount("/assets", StaticFiles(directory=str(PUBLIC_ASSETS)), name="public_assets")

DIST_DIR = BASE_DIR / "web" / "dist"
if DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=str(DIST_DIR), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.app:app", host="127.0.0.1", port=8001, reload=True)

