"""FastAPI AG-UI Bridge Server for AG-SLG-FrameWork."""

from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import re
import tempfile
import time
from typing import Any, Dict, List, Optional
import uuid
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from ag_ui.core import RunAgentInput
from pydantic import BaseModel, Field

from server.agent_driver import AgyDriver, CodexDriver, MockAgentDriver, BaseAgentDriver
from server.agui_bridge import AGUIBridge
from server.scenario_manager import (
    ScenarioManager,
    SceneNode,
    resolve_scene_actions,
    resolve_scene_decorations,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        yield
    finally:
        aclose = getattr(bridge.driver, "aclose", None)
        if callable(aclose):
            await aclose()


app = FastAPI(title="AG-SLG-FrameWork Bridge Server", version="0.1.0", lifespan=lifespan)

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

# Select driver: explicit AG_DRIVER env > persisted UI choice (.agent_driver) > agy
DRIVER_FILE = BASE_DIR / ".agent_driver"
KNOWN_DRIVERS = ("agy", "codex", "mock")


def build_driver(name: str) -> BaseAgentDriver:
    if name == "mock":
        return MockAgentDriver()
    if name == "codex":
        return CodexDriver()
    return AgyDriver()


def resolve_initial_driver_name() -> str:
    env_name = os.getenv("AG_DRIVER", "").strip().lower()
    if env_name:
        return env_name
    try:
        saved = DRIVER_FILE.read_text(encoding="utf-8").strip().lower()
        if saved in KNOWN_DRIVERS:
            return saved
    except OSError:
        pass
    return "agy"


DRIVER_NAME = resolve_initial_driver_name()
driver: BaseAgentDriver = build_driver(DRIVER_NAME)

bridge = AGUIBridge(scenario_mgr=scenario_manager, driver=driver)


def driver_info() -> Dict[str, Any]:
    available = ["agy", "codex"] + (["mock"] if DRIVER_NAME == "mock" else [])
    return {"current": DRIVER_NAME, "available": available}


class DriverSwitchRequest(BaseModel):
    name: str


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "driver": DRIVER_NAME}


@app.get("/api/driver")
def get_driver() -> Dict[str, Any]:
    return driver_info()


@app.post("/api/driver")
async def switch_driver(req: DriverSwitchRequest) -> Dict[str, Any]:
    """Hot-swap the Agent backend (agy / codex) without restarting the service."""
    global DRIVER_NAME
    name = req.name.strip().lower()
    if name not in KNOWN_DRIVERS:
        raise HTTPException(status_code=400, detail=f"Unknown driver: {req.name}")
    if name != DRIVER_NAME:
        old_driver = bridge.set_driver(build_driver(name))
        DRIVER_NAME = name
        try:
            DRIVER_FILE.write_text(name + "\n", encoding="utf-8")
        except OSError:
            pass  # persistence is best-effort; the in-memory switch already took effect
        aclose = getattr(old_driver, "aclose", None)
        if callable(aclose):
            try:
                await aclose()
            except Exception:
                pass
    return driver_info()


@app.get("/api/scenarios")
def list_scenarios():
    scenarios = scenario_manager.list_scenarios()
    items = scenario_manager.list_scenario_summaries()
    return {"scenarios": scenarios, "items": items}


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


SAVES_DIR = BASE_DIR / "saves"
_SAFE_SAVE_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")


class SaveProgressRequest(BaseModel):
    name: Optional[str] = None
    scene_title: Optional[str] = None
    player_state: Dict[str, Any]
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    active_visuals: Optional[Dict[str, Any]] = None
    dynamic_actions: Optional[List[Dict[str, Any]]] = None
    last_turn: Optional[Dict[str, Any]] = None


def _validate_scenario_for_save(scenario_id: str):
    if not _SAFE_SAVE_ID_RE.match(scenario_id):
        raise HTTPException(status_code=400, detail="Invalid scenario_id")
    try:
        return scenario_manager.load_scenario(scenario_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Scenario not found")


def _resolve_save_file(scenario_id: str, save_id: str) -> Path:
    if not _SAFE_SAVE_ID_RE.match(save_id):
        raise HTTPException(status_code=400, detail="Invalid save_id")
    _validate_scenario_for_save(scenario_id)
    return SAVES_DIR / scenario_id / f"{save_id}.json"


def _build_save_summary(data: Dict[str, Any]) -> Dict[str, Any]:
    ps = data.get("player_state") or {}
    return {
        "id": data.get("id", ""),
        "name": data.get("name", "未命名存档"),
        "scenario_id": data.get("scenario_id", ""),
        "scene_id": data.get("scene_id") or ps.get("current_scene", ""),
        "scene_title": data.get("scene_title") or data.get("scene_id") or "",
        "player_name": data.get("player_name") or ps.get("name", ""),
        "hp": data.get("hp", ps.get("hp", 0)),
        "max_hp": data.get("max_hp", ps.get("max_hp", 100)),
        "saved_at": int(data.get("saved_at", 0) or 0),
    }


@app.get("/api/scenarios/{scenario_id}/saves")
def list_scenario_saves(scenario_id: str) -> Dict[str, Any]:
    _validate_scenario_for_save(scenario_id)
    target_dir = SAVES_DIR / scenario_id
    if not target_dir.exists():
        return {"saves": []}
    summaries: List[Dict[str, Any]] = []
    for path in target_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("id", path.stem)
                summaries.append(_build_save_summary(data))
        except Exception:
            continue
    summaries.sort(key=lambda s: s["saved_at"], reverse=True)
    return {"saves": summaries}


@app.post("/api/scenarios/{scenario_id}/saves")
def create_scenario_save(scenario_id: str, req: SaveProgressRequest) -> Dict[str, Any]:
    spec = _validate_scenario_for_save(scenario_id)
    target_dir = SAVES_DIR / scenario_id
    target_dir.mkdir(parents=True, exist_ok=True)

    now_ms = int(time.time() * 1000)
    save_id = f"save_{now_ms}_{uuid.uuid4().hex[:6]}"
    scene_id = str(req.player_state.get("current_scene") or spec.world.initial_scene)
    scene_node = spec.scenes.get(scene_id)
    scene_title = (req.scene_title or (scene_node.title if scene_node else scene_id)).strip()
    custom_name = (req.name or "").strip()
    save_name = custom_name or f"{scene_title} · {time.strftime('%m-%d %H:%M')}"

    payload: Dict[str, Any] = {
        "id": save_id,
        "name": save_name,
        "scenario_id": scenario_id,
        "scene_id": scene_id,
        "scene_title": scene_title,
        "player_name": str(req.player_state.get("name") or spec.world.initial_player_state.name),
        "hp": int(req.player_state.get("hp", 0) or 0),
        "max_hp": int(req.player_state.get("max_hp", 100) or 100),
        "saved_at": now_ms,
        "player_state": req.player_state,
        "messages": req.messages,
        "active_visuals": req.active_visuals,
        "dynamic_actions": req.dynamic_actions,
        "last_turn": req.last_turn,
    }
    (target_dir / f"{save_id}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"save": _build_save_summary(payload)}


@app.get("/api/scenarios/{scenario_id}/saves/{save_id}")
def get_scenario_save(scenario_id: str, save_id: str) -> Dict[str, Any]:
    save_file = _resolve_save_file(scenario_id, save_id)
    if not save_file.exists():
        raise HTTPException(status_code=404, detail="Save not found")
    try:
        data = json.loads(save_file.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Corrupted save file: {exc}")
    return {"save": data}


@app.delete("/api/scenarios/{scenario_id}/saves/{save_id}")
def delete_scenario_save(scenario_id: str, save_id: str) -> Dict[str, Any]:
    save_file = _resolve_save_file(scenario_id, save_id)
    if not save_file.exists():
        raise HTTPException(status_code=404, detail="Save not found")
    save_file.unlink()
    return {"status": "ok", "id": save_id}


@app.get("/api/scenarios/{scenario_id}/export")
def export_scenario_endpoint(scenario_id: str):
    try:
        tmp_dir = Path(tempfile.gettempdir()) / "ag_slg_exports"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        zip_path = tmp_dir / f"{scenario_id}.zip"
        scenario_manager.export_scenario_bundle(scenario_id, target_zip=zip_path)
        return FileResponse(
            path=str(zip_path),
            filename=f"{scenario_id}.zip",
            media_type="application/zip",
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Scenario not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/scenarios/import")
async def import_scenario_endpoint(request: Request):
    try:
        tmp_dir = Path(tempfile.gettempdir()) / "ag_slg_imports"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_zip = tmp_dir / f"import_{int(time.time())}.zip"

        content = await request.body()
        if not content:
            raise HTTPException(status_code=400, detail="Empty file payload")

        tmp_zip.write_bytes(content)
        scenario_id = scenario_manager.import_scenario_bundle(tmp_zip)
        return {"status": "ok", "scenario_id": scenario_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to import scenario bundle: {str(e)}")



@app.get("/scenarios/{scenario_id}/assets/{subpath:path}")
@app.get("/api/scenarios/{scenario_id}/assets/{subpath:path}")
def get_scenario_asset(scenario_id: str, subpath: str):
    asset_file = scenario_manager.find_asset_path(subpath, scenario_id=scenario_id)
    if asset_file and asset_file.exists():
        return FileResponse(str(asset_file))
    raise HTTPException(status_code=404, detail="Asset not found")


@app.get("/assets/{subpath:path}")
def get_co_located_asset(subpath: str):
    asset_file = scenario_manager.find_asset_path(subpath)
    if asset_file and asset_file.exists():
        return FileResponse(str(asset_file))
    raise HTTPException(status_code=404, detail="Asset not found")




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
    resolved_decorations = resolve_scene_decorations(curr_scene, session.player_state)
    return {
        "thread_id": thread_id,
        "scenario_id": session.scenario_id,
        "player_state": session.player_state.model_dump(),
        "available_actions": [a.model_dump() for a in resolved_actions],
        "decorations": [d.model_dump() for d in resolved_decorations],
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

