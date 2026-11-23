"""Scenario data models and file system loader/saver for AG-SLG-FrameWork."""

from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pydantic import BaseModel, Field


class PlayerState(BaseModel):
    name: str = "调查员"
    hp: int = 100
    san: int = 80
    gold: int = 50
    attributes: Dict[str, int] = Field(default_factory=lambda: {
        "strength": 10,
        "agility": 10,
        "intelligence": 10,
    })
    inventory: List[Dict[str, Any]] = Field(default_factory=list)
    variables: Dict[str, Any] = Field(default_factory=dict)
    current_scene: str = ""


class WorldSpec(BaseModel):
    id: str
    title: str
    version: str = "1.0.0"
    author: str = "Unknown"
    initial_scene: str
    initial_player_state: PlayerState


class NPC(BaseModel):
    id: str
    name: str
    avatar: str = ""
    greeting: str = ""


class ActionOption(BaseModel):
    id: str
    label: str
    type: str = "interact"  # interact, check, transition, custom
    target_npc: Optional[str] = None
    target_scene: Optional[str] = None
    skill: Optional[str] = None
    difficulty: Optional[int] = None
    condition: Optional[Dict[str, Any]] = None
    effects: Optional[Dict[str, Any]] = None
    source: Optional[str] = None
    on_success: Optional[Dict[str, Any]] = None
    on_failure: Optional[Dict[str, Any]] = None


def _compare_value(actual: Any, expected: Any) -> bool:
    """Compare actual state value against expected scalar or operator dict."""
    if isinstance(expected, dict):
        num_actual = actual if isinstance(actual, (int, float)) else 0
        if "lt" in expected and not (num_actual < expected["lt"]):
            return False
        if "lte" in expected and not (num_actual <= expected["lte"]):
            return False
        if "gt" in expected and not (num_actual > expected["gt"]):
            return False
        if "gte" in expected and not (num_actual >= expected["gte"]):
            return False
        if "ne" in expected and not (actual != expected["ne"]):
            return False
        if "in" in expected and actual not in expected["in"]:
            return False
        if "not_in" in expected and actual in expected["not_in"]:
            return False
        return True
    return actual == expected


def evaluate_action_condition(
    condition: Optional[Dict[str, Any]], player_state: PlayerState
) -> bool:
    """Evaluate declarative action visibility condition against current player state."""
    if not condition:
        return True

    inv_ids = {
        item.get("id", "")
        for item in (player_state.inventory or [])
        if isinstance(item, dict)
    }

    if "has_item" in condition:
        req = condition["has_item"]
        reqs = [req] if isinstance(req, str) else list(req)
        if not all(r in inv_ids for r in reqs):
            return False

    if "has_any_item" in condition:
        any_reqs = list(condition["has_any_item"])
        if not any(r in inv_ids for r in any_reqs):
            return False

    if "not_has_item" in condition:
        forb = condition["not_has_item"]
        forbs = [forb] if isinstance(forb, str) else list(forb)
        if any(f in inv_ids for f in forbs):
            return False

    if "variables" in condition and isinstance(condition["variables"], dict):
        for k, expected in condition["variables"].items():
            actual = player_state.variables.get(k)
            if not _compare_value(actual, expected):
                return False

    if "attributes" in condition and isinstance(condition["attributes"], dict):
        for k, expected in condition["attributes"].items():
            actual = player_state.attributes.get(k)
            if not _compare_value(actual, expected):
                return False

    time_slot = player_state.variables.get("time_slot")
    if "time_slot_in" in condition and time_slot not in condition["time_slot_in"]:
        return False
    if "time_slot_not_in" in condition and time_slot in condition["time_slot_not_in"]:
        return False

    if "min_day" in condition:
        day = int(player_state.variables.get("day", 1) or 1)
        if day < int(condition["min_day"]):
            return False

    return True


def resolve_scene_actions(
    scene: Optional[SceneNode],
    player_state: PlayerState,
    dynamic_actions: Optional[List[Dict[str, Any]]] = None,
) -> List[ActionOption]:
    """Filter scene actions by state conditions and merge dynamic DM actions."""
    resolved: List[ActionOption] = []
    seen_ids = set()

    if scene and scene.actions:
        for act in scene.actions:
            if evaluate_action_condition(act.condition, player_state):
                resolved.append(act)
                seen_ids.add(act.id)

    if dynamic_actions:
        for raw in dynamic_actions:
            try:
                dyn_act = ActionOption(**raw) if isinstance(raw, dict) else raw
                if not dyn_act.source:
                    dyn_act.source = "dynamic"
                if evaluate_action_condition(dyn_act.condition, player_state):
                    if dyn_act.id in seen_ids:
                        resolved = [a for a in resolved if a.id != dyn_act.id]
                    resolved.append(dyn_act)
                    seen_ids.add(dyn_act.id)
            except Exception:
                continue

    return resolved


class PropDecoration(BaseModel):
    id: str
    name: str
    image: str
    side: str = "left"  # "left" or "right"
    caption: str = ""
    tooltip: str = ""


class VisualLayer(BaseModel):
    background: str = ""
    foreground: str = ""
    hero_image: str = ""
    atmosphere: str = ""
    decorations: List[PropDecoration] = Field(default_factory=list)


class SceneNode(BaseModel):
    id: str
    title: str
    background: str = ""
    foreground: str = ""
    hero_image: str = ""
    music: str = ""
    description: str = ""
    visuals: Optional[VisualLayer] = None
    decorations: List[PropDecoration] = Field(default_factory=list)
    npcs: List[NPC] = Field(default_factory=list)
    actions: List[ActionOption] = Field(default_factory=list)



class ScenarioSpec(BaseModel):
    world: WorldSpec
    scenes: Dict[str, SceneNode] = Field(default_factory=dict)


class ScenarioManager:
    """Manages loading and updating scenario YAML files from the local file system."""

    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir is None:
            # default to scripts/ directory in workspace
            self.base_dir = Path(__file__).resolve().parent.parent / "scripts"
        else:
            self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def list_scenarios(self) -> List[str]:
        if not self.base_dir.exists():
            return []
        return [
            p.name for p in self.base_dir.iterdir()
            if p.is_dir() and (p / "world.yaml").exists()
        ]

    def load_scenario(self, scenario_id: str) -> ScenarioSpec:
        scenario_path = self.base_dir / scenario_id
        world_file = scenario_path / "world.yaml"
        if not world_file.exists():
            raise FileNotFoundError(f"Scenario world file not found: {world_file}")

        with open(world_file, "r", encoding="utf-8") as f:
            world_data = yaml.safe_load(f) or {}

        # Set current scene to initial scene if not explicitly set
        world_spec = WorldSpec(**world_data)
        if not world_spec.initial_player_state.current_scene:
            world_spec.initial_player_state.current_scene = world_spec.initial_scene

        scenes_dir = scenario_path / "scenes"
        scenes: Dict[str, SceneNode] = {}
        if scenes_dir.exists():
            for scene_file in scenes_dir.glob("*.yaml"):
                with open(scene_file, "r", encoding="utf-8") as f:
                    scene_data = yaml.safe_load(f) or {}
                    scene_id = scene_file.stem
                    if "id" not in scene_data:
                        scene_data["id"] = scene_id
                    scenes[scene_id] = SceneNode(**scene_data)

        return ScenarioSpec(world=world_spec, scenes=scenes)

    def get_scene(self, scenario_id: str, scene_id: str) -> Optional[SceneNode]:
        scene_file = self.base_dir / scenario_id / "scenes" / f"{scene_id}.yaml"
        if not scene_file.exists():
            return None
        with open(scene_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            if "id" not in data:
                data["id"] = scene_id
            return SceneNode(**data)

    def save_scene(self, scenario_id: str, scene: SceneNode) -> Path:
        scenes_dir = self.base_dir / scenario_id / "scenes"
        scenes_dir.mkdir(parents=True, exist_ok=True)
        target = scenes_dir / f"{scene.id}.yaml"
        with open(target, "w", encoding="utf-8") as f:
            yaml.safe_dump(scene.model_dump(), f, allow_unicode=True, sort_keys=False)
        return target

    def save_world(self, scenario_id: str, world: WorldSpec) -> Path:
        scenario_dir = self.base_dir / scenario_id
        scenario_dir.mkdir(parents=True, exist_ok=True)
        target = scenario_dir / "world.yaml"
        with open(target, "w", encoding="utf-8") as f:
            yaml.safe_dump(world.model_dump(), f, allow_unicode=True, sort_keys=False)
        return target
