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
    on_success: Optional[Dict[str, Any]] = None
    on_failure: Optional[Dict[str, Any]] = None


class SceneNode(BaseModel):
    id: str
    title: str
    background: str = ""
    music: str = ""
    description: str = ""
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
