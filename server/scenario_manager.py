"""Scenario data models and file system loader/saver for AG-SLG-FrameWork."""

from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional
import zipfile
import yaml
from pydantic import BaseModel, Field, PrivateAttr


class PlayerState(BaseModel):
    name: str = "调查员"
    hp: int = 100
    max_hp: int = 100
    mp: Optional[int] = None
    max_mp: Optional[int] = None
    san: int = 80
    gold: int = 50
    attributes: Dict[str, int] = Field(default_factory=lambda: {
        "strength": 10,
        "agility": 10,
        "intelligence": 10,
    })
    inventory: List[Dict[str, Any]] = Field(default_factory=list)
    outfit: Dict[str, Any] = Field(default_factory=dict)
    skills: List[Dict[str, Any]] = Field(default_factory=list)
    variables: Dict[str, Any] = Field(default_factory=dict)
    hud_widgets: List[Dict[str, Any]] = Field(default_factory=list)
    current_scene: str = ""
    _scenario_id: str = PrivateAttr(default="")


class WorldSpec(BaseModel):
    id: str
    title: str
    version: str = "1.0.0"
    author: str = "Unknown"
    icon: str = ""
    sort_order: int = 100
    initial_scene: str
    opening_narration: Optional[str] = None
    dm_rules: Optional[str] = None
    initial_player_state: PlayerState
    item_catalog: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    unique_items: List[str] = Field(default_factory=list)
    scene_scoped_defaults: Dict[str, Any] = Field(default_factory=dict)
    attribute_bounds: Dict[str, List[int]] = Field(default_factory=dict)
    variable_bounds: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    adjudication_rules: List[Dict[str, Any]] = Field(default_factory=list)
    freeform_rules: List[Dict[str, Any]] = Field(default_factory=list)
    fallback_recipes: List[Dict[str, Any]] = Field(default_factory=list)
    default_fallback: Optional[Dict[str, Any]] = None
    attribute_labels: Dict[str, str] = Field(default_factory=dict)


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
    keywords: List[str] = Field(default_factory=list)
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


def _match_weather_condition(
    weather_str: str,
    weather_type: str,
    targets: List[str],
) -> bool:
    """Match current weather label/type against declarative condition keywords."""
    w_str = (weather_str or "").strip()
    w_type = (weather_type or "").strip().lower()
    if not w_str and not w_type:
        return False

    alias_map = {
        "晴天": {"clear"},
        "晴朗": {"clear"},
        "clear": {"clear"},
        "阴天": {"cloudy"},
        "多云": {"cloudy"},
        "cloudy": {"cloudy"},
        "overcast": {"cloudy"},
        "刮风": {"windy", "storm"},
        "大风": {"windy", "storm"},
        "狂风": {"windy", "storm"},
        "windy": {"windy", "storm"},
        "wind": {"windy", "storm"},
        "雨天": {"rain", "storm"},
        "下雨": {"rain", "storm"},
        "小雨": {"rain"},
        "阵雨": {"rain"},
        "rain": {"rain", "storm"},
        "暴雨": {"storm"},
        "雷暴": {"storm"},
        "storm": {"storm"},
        "海雾": {"foggy"},
        "雾天": {"foggy"},
        "foggy": {"foggy"},
        "fog": {"foggy"},
    }

    for raw_target in targets:
        target = str(raw_target).strip()
        if not target:
            continue
        if target == w_str or target.lower() == w_type:
            return True
        if target in w_str:
            return True
        mapped_types = alias_map.get(target.lower()) or alias_map.get(target)
        if mapped_types and w_type in mapped_types:
            return True
    return False


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

    outfit_ids = {
        item.get("id", "")
        for item in (player_state.outfit or {}).values()
        if isinstance(item, dict) and item.get("id")
    }

    if "has_outfit" in condition:
        req = condition["has_outfit"]
        reqs = [req] if isinstance(req, str) else list(req)
        if not all(r in outfit_ids for r in reqs):
            return False

    if "not_has_outfit" in condition:
        forb = condition["not_has_outfit"]
        forbs = [forb] if isinstance(forb, str) else list(forb)
        if any(f in outfit_ids for f in forbs):
            return False

    outfit_map = player_state.outfit or {}
    if "has_outfit_slot" in condition:
        req_slots = condition["has_outfit_slot"]
        slots = [req_slots] if isinstance(req_slots, str) else list(req_slots)
        if not all(bool(outfit_map.get(s)) for s in slots):
            return False

    if "not_has_outfit_slot" in condition:
        forb_slots = condition["not_has_outfit_slot"]
        slots = [forb_slots] if isinstance(forb_slots, str) else list(forb_slots)
        if any(bool(outfit_map.get(s)) for s in slots):
            return False

    skill_keys = set()
    for sk in (player_state.skills or []):
        if isinstance(sk, dict):
            if sk.get("id"):
                skill_keys.add(str(sk["id"]))
            if sk.get("name"):
                skill_keys.add(str(sk["name"]))
        elif sk:
            skill_keys.add(str(sk))

    if "has_skill" in condition:
        req = condition["has_skill"]
        reqs = [req] if isinstance(req, str) else list(req)
        if not all(r in skill_keys for r in reqs):
            return False

    if "not_has_skill" in condition:
        forb = condition["not_has_skill"]
        forbs = [forb] if isinstance(forb, str) else list(forb)
        if any(f in skill_keys for f in forbs):
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

    weather_str = str(player_state.variables.get("weather") or "")
    weather_type = str(player_state.variables.get("weather_type") or "")
    if "weather_in" in condition:
        targets = condition["weather_in"]
        target_list = [targets] if isinstance(targets, str) else list(targets or [])
        if not _match_weather_condition(weather_str, weather_type, target_list):
            return False
    if "weather_not_in" in condition:
        targets = condition["weather_not_in"]
        target_list = [targets] if isinstance(targets, str) else list(targets or [])
        if _match_weather_condition(weather_str, weather_type, target_list):
            return False

    if "min_day" in condition:
        day = int(player_state.variables.get("day", 1) or 1)
        if day < int(condition["min_day"]):
            return False

    if "min_hp" in condition:
        if int(player_state.hp or 0) < int(condition["min_hp"]):
            return False

    if "hp_lte" in condition:
        if int(player_state.hp or 0) > int(condition["hp_lte"]):
            return False

    if "min_mp" in condition:
        curr_mp = int(player_state.mp if player_state.mp is not None else 0)
        if curr_mp < int(condition["min_mp"]):
            return False

    if "max_mp" in condition:
        curr_mp = int(player_state.mp if player_state.mp is not None else 0)
        if curr_mp > int(condition["max_mp"]):
            return False

    if "min_gold" in condition:
        if int(player_state.gold or 0) < int(condition["min_gold"]):
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
    category: str = "env"  # "env" (环境) or "structure" (建造/设施)
    tag: str = ""  # optional badge label, e.g. "已建成" / "设施" / "环境"
    condition: Optional[Dict[str, Any]] = None


def resolve_scene_decorations(
    scene: Optional["SceneNode"],
    player_state: PlayerState,
) -> List[PropDecoration]:
    """Filter scene decorations by declarative conditions and append dynamic built structures."""
    resolved: List[PropDecoration] = []
    seen_ids = set()

    raw_decs: List[PropDecoration] = []
    if scene:
        if scene.visuals and scene.visuals.decorations:
            raw_decs = list(scene.visuals.decorations)
        elif scene.decorations:
            raw_decs = list(scene.decorations)

    for dec in raw_decs:
        if evaluate_action_condition(dec.condition, player_state):
            resolved.append(dec)
            seen_ids.add(dec.id)

    built_list = (player_state.variables or {}).get("built_structures")
    if isinstance(built_list, list):
        curr_scene_id = scene.id if scene else player_state.current_scene
        for raw_item in built_list:
            if not isinstance(raw_item, dict):
                continue
            target_scene = raw_item.get("scene_id")
            if not target_scene or (curr_scene_id and target_scene != curr_scene_id):
                continue
            dec_id = str(raw_item.get("id", "")).strip()
            if not dec_id or dec_id in seen_ids:
                continue
            try:
                dec = PropDecoration(
                    id=dec_id,
                    name=str(raw_item.get("name", dec_id)),
                    image=str(raw_item.get("image", "")),
                    side=str(raw_item.get("side", "left")) if raw_item.get("side") in ("left", "right") else "left",
                    caption=str(raw_item.get("caption", raw_item.get("name", dec_id))),
                    tooltip=str(raw_item.get("tooltip", "")),
                    category=str(raw_item.get("category", "structure")),
                    tag=str(raw_item.get("tag", "已建成")),
                )
                resolved.append(dec)
                seen_ids.add(dec_id)
            except Exception:
                continue

    return resolved


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

    def list_scenario_summaries(self) -> List[Dict[str, Any]]:
        """Return list of scenarios with id, title, and icon from world.yaml."""
        if not self.base_dir.exists():
            return []
        entries: List[tuple[int, str, Dict[str, Any]]] = []
        for p in self.base_dir.iterdir():
            if p.is_dir():
                world_file = p / "world.yaml"
                if world_file.exists():
                    title = p.name
                    icon = ""
                    sort_order = 100
                    try:
                        with open(world_file, "r", encoding="utf-8") as f:
                            data = yaml.safe_load(f) or {}
                            title = data.get("title") or p.name
                            icon = data.get("icon") or ""
                            sort_order = int(data.get("sort_order", 100))
                    except Exception:
                        pass
                    entries.append((sort_order, p.name, {"id": p.name, "title": title, "icon": icon}))
        entries.sort(key=lambda item: (item[0], item[1]))
        return [item[2] for item in entries]

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
        world_spec.initial_player_state._scenario_id = world_spec.id

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

    def get_scenario_dir(self, scenario_id: str) -> Path:
        return self.base_dir / scenario_id

    def get_scenario_assets_dir(self, scenario_id: str) -> Path:
        assets_dir = self.base_dir / scenario_id / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        return assets_dir

    def export_scenario_bundle(self, scenario_id: str, target_zip: Optional[Path] = None) -> Path:
        """Export a scenario folder (world.yaml, scenes/, assets/) into a portable .zip bundle."""
        scenario_dir = self.base_dir / scenario_id
        if not scenario_dir.exists() or not (scenario_dir / "world.yaml").exists():
            raise FileNotFoundError(f"Scenario not found for export: {scenario_id}")

        if target_zip is None:
            target_zip = self.base_dir / f"{scenario_id}.zip"

        with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file_path in scenario_dir.rglob("*"):
                if file_path.is_file() and not file_path.name.startswith("."):
                    rel_path = file_path.relative_to(scenario_dir)
                    zf.write(file_path, arcname=rel_path.as_posix())

        return target_zip

    def import_scenario_bundle(self, zip_path: Path, scenario_id: Optional[str] = None) -> str:
        """Import a scenario .zip bundle into self.base_dir / scenario_id."""
        if not zip_path.exists():
            raise FileNotFoundError(f"Archive not found: {zip_path}")

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            world_entry = None
            has_nested_root = False
            nested_folder = ""

            for name in names:
                parts = Path(name.replace("\\", "/")).parts
                if len(parts) == 1 and parts[0] == "world.yaml":
                    world_entry = name
                    break
                elif len(parts) == 2 and parts[1] == "world.yaml":
                    world_entry = name
                    has_nested_root = True
                    nested_folder = parts[0]
                    break

            if not world_entry:
                raise ValueError("Invalid scenario bundle: 'world.yaml' not found in archive")

            target_id = scenario_id or (nested_folder if has_nested_root else zip_path.stem)
            target_dir = self.base_dir / target_id
            target_dir.mkdir(parents=True, exist_ok=True)

            for member in zf.infolist():
                if member.is_dir():
                    continue
                member_path = Path(member.filename.replace("\\", "/"))
                if ".." in member_path.parts:
                    continue

                if has_nested_root and member_path.parts[0] == nested_folder:
                    rel_parts = member_path.parts[1:]
                else:
                    rel_parts = member_path.parts

                if not rel_parts:
                    continue

                dest_file = target_dir.joinpath(*rel_parts)
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(dest_file, "wb") as dst:
                    shutil.copyfileobj(src, dst)

        return target_id

    def find_asset_path(self, subpath: str, scenario_id: Optional[str] = None) -> Optional[Path]:
        """Intelligently resolve an asset subpath from co-located scenario assets or public fallback."""
        clean_subpath = subpath.lstrip("/")
        # 1. Check specific scenario assets
        if scenario_id:
            candidate = self.base_dir / scenario_id / "assets" / clean_subpath
            if candidate.exists() and candidate.is_file():
                return candidate

        # 2. Search across all scenarios' assets/
        if self.base_dir.exists():
            for s_dir in self.base_dir.iterdir():
                if s_dir.is_dir():
                    candidate = s_dir / "assets" / clean_subpath
                    if candidate.exists() and candidate.is_file():
                        return candidate

        # 3. Check web/public/assets fallback
        public_candidate = self.base_dir.parent / "web" / "public" / "assets" / clean_subpath
        if public_candidate.exists() and public_candidate.is_file():
            return public_candidate

        return None

