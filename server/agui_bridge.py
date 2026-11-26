"""AG-UI Protocol Bridge for AG-SLG-FrameWork.

Translates game interactions and Agent CLI output to standard AG-UI SSE streams:
RunStarted -> TextMessage* -> StateDelta / ToolCall -> RunFinished.
"""

import asyncio
import json
import random
import re
import uuid
from typing import Any, AsyncIterator, Dict, List, Optional
from ag_ui.core import (
    RunAgentInput,
    RunStartedEvent,
    TextMessageStartEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    StateDeltaEvent,
    ToolCallStartEvent,
    ToolCallEndEvent,
    RunFinishedEvent,
)
from ag_ui.encoder import EventEncoder
from server.agent_driver import BaseAgentDriver, AgentEvent
from server.scenario_manager import (
    ScenarioManager,
    PlayerState,
    SceneNode,
    ActionOption,
    WorldSpec,
    evaluate_action_condition,
    resolve_scene_actions,
    resolve_scene_decorations,
)


TIME_SLOTS = ["清晨", "上午", "下午", "黄昏", "夜晚", "深夜"]

WEATHER_CATALOG: Dict[str, Dict[str, Any]] = {
    "clear": {
        "labels_by_slot": {
            "清晨": "晴空微暖",
            "上午": "晴朗炎热",
            "下午": "烈日酷热",
            "黄昏": "落日余晖",
            "夜晚": "夜色星沉",
            "深夜": "静谧星夜",
        },
        "atmosphere": "晴空炙烤、天色澄明",
        "night_atmosphere": "星光微寒、夜色静谧",
        "cue": "日光穿透云隙洒下，天地一片澄明，空气中带着干爽的温热。",
        "night_cue": "夜空清澈无云，微冷的星月光洒在开阔处与枝梢之间。",
    },
    "cloudy": {
        "labels_by_slot": {
            "清晨": "阴云微凉",
            "上午": "阴天多云",
            "下午": "乌云蔽日",
            "黄昏": "阴沉暮色",
            "夜晚": "阴云蔽月",
            "深夜": "黑云压夜",
        },
        "atmosphere": "阴云压顶、闷热阴沉",
        "night_atmosphere": "黑云蔽月、沉闷压抑",
        "cue": "厚重的铅灰色云层遮住了天日，空气潮湿闷沉，似有风雨酝酿。",
        "night_cue": "浓重的阴云遮蔽了星月，四周陷入比往常更加深沉的黑暗与闷潮。",
    },
    "windy": {
        "labels_by_slot": {
            "清晨": "微风转急",
            "上午": "狂风呼啸",
            "下午": "劲风吹拂",
            "黄昏": "暮风骤起",
            "夜晚": "夜风呼啸",
            "深夜": "凛冽狂风",
        },
        "atmosphere": "狂风呼啸、草木翻飞",
        "night_atmosphere": "夜风凛冽、风声怒吼",
        "cue": "劲急的大风迎面刮来，草木剧烈摇晃，沙尘与落叶随风翻飞。",
        "night_cue": "凛冽的夜风在林间与岩隙中呜咽穿行，气温随之明显下降。",
    },
    "rain": {
        "labels_by_slot": {
            "清晨": "晨雨淅沥",
            "上午": "细雨绵绵",
            "下午": "阵雨淅沥",
            "黄昏": "暮雨潇潇",
            "夜晚": "夜雨淅沥",
            "深夜": "冷雨凄凄",
        },
        "atmosphere": "雨丝绵密、湿润清凉",
        "night_atmosphere": "夜雨微寒、水滴淅沥",
        "cue": "细密的雨点敲打着地面与枝叶，带来清凉水汽，也让人衣衫渐湿。",
        "night_cue": "冰凉的夜雨淅沥落下，周围地面湿滑，空气中寒意加重。",
    },
    "storm": {
        "labels_by_slot": {
            "清晨": "暴风雨临",
            "上午": "狂风暴雨",
            "下午": "雷雨倾盆",
            "黄昏": "风暴骤起",
            "夜晚": "暴雨夜袭",
            "深夜": "雷暴狂风",
        },
        "atmosphere": "电闪雷鸣、狂风暴雨",
        "night_atmosphere": "雷暴交加、暗夜怒涛",
        "cue": "狂风裹挟着豆大的雨点倾盆而下，远处雷声滚滚，能见度骤降，寒意透骨。",
        "night_cue": "电闪雷鸣撕裂夜幕，狂风暴雨猛烈拍打着大地，露天火源与体温都面临严峻考验。",
    },
    "foggy": {
        "labels_by_slot": {
            "清晨": "晨雾微凉",
            "上午": "薄雾未散",
            "下午": "浓雾弥漫",
            "黄昏": "暮雾沉沉",
            "夜晚": "夜雾笼罩",
            "深夜": "浓雾深重",
        },
        "atmosphere": "雾气弥漫、视野朦胧",
        "night_atmosphere": "浓雾锁夜、幽暗迷离",
        "cue": "乳白色的潮湿浓雾贴着地面缓缓流淌，十步之外的轮廓都变得朦胧。",
        "night_cue": "浓重的夜雾吞没了远处的轮廓，水汽凝结在衣领与眉梢。",
    },
}

WEATHER_TRANSITIONS: Dict[str, List[tuple[str, float]]] = {
    "clear": [("cloudy", 0.35), ("windy", 0.25), ("clear", 0.25), ("foggy", 0.15)],
    "cloudy": [("rain", 0.35), ("windy", 0.25), ("cloudy", 0.20), ("clear", 0.20)],
    "windy": [("cloudy", 0.30), ("storm", 0.25), ("rain", 0.20), ("windy", 0.15), ("clear", 0.10)],
    "rain": [("storm", 0.25), ("cloudy", 0.30), ("rain", 0.25), ("clear", 0.20)],
    "storm": [("rain", 0.40), ("windy", 0.30), ("cloudy", 0.20), ("storm", 0.10)],
    "foggy": [("clear", 0.40), ("cloudy", 0.30), ("windy", 0.20), ("foggy", 0.10)],
}


def classify_weather_type(weather_label: str, explicit_type: str = "") -> str:
    """Resolve canonical weather category from label or explicit type."""
    if explicit_type in WEATHER_CATALOG:
        return explicit_type
    label = (weather_label or "").strip()
    if any(k in label for k in ("暴雨", "雷暴", "雷雨", "风暴")):
        return "storm"
    if any(k in label for k in ("雨",)):
        return "rain"
    if any(k in label for k in ("风",)):
        return "windy"
    if any(k in label for k in ("阴", "乌云", "黑云", "多云")):
        return "cloudy"
    if any(k in label for k in ("雾",)):
        return "foggy"
    return "clear"


def advance_weather(
    current_label: str,
    current_type: str,
    new_slot: str,
    duration: int = 1,
    rng: Optional[random.Random] = None,
) -> tuple[str, str, int]:
    """Advance weather state smoothly across clear, cloudy, windy, rain, storm, and foggy."""
    cur_type = classify_weather_type(current_label, current_type)
    candidates = list(WEATHER_TRANSITIONS.get(cur_type, WEATHER_TRANSITIONS["clear"]))

    if duration >= 2:
        filtered = [(w, p) for w, p in candidates if w != cur_type]
        if filtered:
            candidates = filtered

    if new_slot not in ("清晨", "深夜"):
        candidates = [(w, p * 0.4 if w == "foggy" else p) for w, p in candidates]

    picker = rng or random
    total_w = sum(p for _, p in candidates)
    pick = picker.uniform(0, total_w)
    acc = 0.0
    next_type = candidates[0][0]
    for w_type, weight in candidates:
        acc += weight
        if pick <= acc:
            next_type = w_type
            break

    slot_labels = WEATHER_CATALOG[next_type]["labels_by_slot"]
    next_label = slot_labels.get(new_slot, list(slot_labels.values())[0])
    next_duration = duration + 1 if next_type == cur_type else 1
    return next_label, next_type, next_duration


def get_weather_atmosphere(weather_label: str, weather_type: str = "", time_slot: str = "") -> str:
    """Return concise visual atmosphere phrase matching weather and time of day."""
    w_type = classify_weather_type(weather_label, weather_type)
    entry = WEATHER_CATALOG.get(w_type, WEATHER_CATALOG["clear"])
    if time_slot in ("夜晚", "深夜"):
        return entry["night_atmosphere"]
    return entry["atmosphere"]


def get_weather_narrative_cue(weather_label: str, weather_type: str = "", time_slot: str = "") -> str:
    """Return short ambient narrative description matching weather and time of day."""
    w_type = classify_weather_type(weather_label, weather_type)
    entry = WEATHER_CATALOG.get(w_type, WEATHER_CATALOG["clear"])
    if time_slot in ("夜晚", "深夜"):
        return entry["night_cue"]
    return entry["cue"]


def extract_message_text(content: Any) -> str:
    """Extract clean text content from string, list of parts, or structured objects."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict):
                if "text" in part:
                    parts.append(str(part["text"]))
                elif "content" in part:
                    parts.append(str(part["content"]))
                else:
                    parts.append(str(part))
            elif hasattr(part, "text"):
                parts.append(str(part.text))
            elif hasattr(part, "content"):
                parts.append(str(part.content))
            else:
                parts.append(str(part))
        return "\n".join(parts)
    return str(content or "")


def _enrich_item_meta(
    raw_item: Any,
    item_catalog: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Normalize an inventory or outfit item dict and enrich missing fields from scenario catalog."""
    item = dict(raw_item) if isinstance(raw_item, dict) else {"id": str(raw_item), "name": str(raw_item)}
    item_id = item.get("id", "")
    if item_catalog and item_id in item_catalog:
        meta = item_catalog[item_id]
        if (not item.get("name") or item["name"] == item_id) and meta.get("name"):
            item["name"] = meta["name"]
        if not item.get("icon") and meta.get("icon"):
            item["icon"] = meta["icon"]
        if not item.get("desc") and meta.get("desc"):
            item["desc"] = meta["desc"]
        if not item.get("tag") and meta.get("tag"):
            item["tag"] = meta["tag"]
    return item


def _enrich_skill_meta(raw_skill: Any) -> Dict[str, Any]:
    """Normalize a skill entry so it always carries id, name, desc, and optional effect/cost/cooldown."""
    if isinstance(raw_skill, dict):
        skill = dict(raw_skill)
    else:
        val = str(raw_skill).strip()
        skill = {"id": val, "name": val, "desc": ""}

    if not skill.get("id") and skill.get("name"):
        skill["id"] = str(skill["name"])
    if not skill.get("name") and skill.get("id"):
        skill["name"] = str(skill["id"])

    desc = skill.get("desc") or skill.get("description") or skill.get("summary") or ""
    skill["desc"] = str(desc)
    skill.pop("description", None)
    skill.pop("summary", None)

    effect = skill.get("effect") or skill.get("usage") or skill.get("benefit")
    if effect is not None and str(effect).strip():
        skill["effect"] = str(effect).strip()
    skill.pop("usage", None)
    skill.pop("benefit", None)

    for meta_key in ("cost", "cooldown"):
        if meta_key in skill and skill[meta_key] is not None:
            skill[meta_key] = str(skill[meta_key]).strip()

    if "level" in skill and skill["level"] is not None:
        try:
            skill["level"] = int(skill["level"])
        except (ValueError, TypeError):
            pass
    return skill


def _bump_skill_rank(skill: Dict[str, Any], rank: int) -> Dict[str, Any]:
    """Upgrade skill level and Lv.X tag label when skill_rank advances."""
    updated = dict(skill)
    updated["level"] = rank
    if updated.get("tag"):
        updated["tag"] = re.sub(r"Lv\.\d+", f"Lv.{rank}", str(updated["tag"]))
    return updated


def _hydrate_class_skills(
    scenario_mgr: ScenarioManager,
    scenario_id: str,
    player_state: PlayerState,
) -> bool:
    """Backfill class skills from scenario actions if class_selected=true but skills list is empty."""
    if player_state.skills:
        return False
    variables = player_state.variables or {}
    if not variables.get("class_selected"):
        return False
    class_id = str(variables.get("class_id") or "").strip()
    if not class_id:
        return False

    try:
        spec = scenario_mgr.load_scenario(scenario_id)
    except Exception:
        return False

    template_skills: Optional[List[Any]] = None
    for scene in (spec.scenes or {}).values():
        for act in (scene.actions or []):
            on_succ = act.on_success or {}
            succ_vars = on_succ.get("variables") if isinstance(on_succ, dict) else None
            if (
                isinstance(succ_vars, dict)
                and str(succ_vars.get("class_id") or "") == class_id
                and isinstance(on_succ.get("skills"), list)
                and on_succ["skills"]
            ):
                template_skills = on_succ["skills"]
                break
        if template_skills:
            break

    if not template_skills:
        return False

    try:
        rank = int(variables.get("skill_rank") or variables.get("level") or 1)
    except (ValueError, TypeError):
        rank = 1

    hydrated = [_enrich_skill_meta(s) for s in template_skills]
    if rank > 1:
        hydrated = [_bump_skill_rank(s, rank) for s in hydrated]
    player_state.skills = hydrated
    return True


def _clamp_attr(key: str, val: int, world: Optional[WorldSpec] = None) -> int:
    bounds = (world.attribute_bounds or {}).get(key) if world else None
    if isinstance(bounds, list) and len(bounds) >= 2:
        return max(int(bounds[0]), min(int(bounds[1]), val))
    return val


def _clamp_variable(
    key: str,
    val: int,
    variables: Dict[str, Any],
    world: Optional[WorldSpec] = None,
) -> int:
    rule = (world.variable_bounds or {}).get(key) if world else None
    if not isinstance(rule, dict):
        return val
    if rule.get("min") is not None:
        val = max(int(rule["min"]), val)
    max_val = rule.get("max")
    max_var = rule.get("max_var")
    if max_var and variables.get(max_var) is not None:
        try:
            max_val = int(variables[max_var])
        except (TypeError, ValueError):
            pass
    if max_val is not None:
        val = min(int(max_val), val)
    return val


def _matches_keyword_rules(text: str, spec: Dict[str, Any]) -> bool:
    """Check any_keywords and all_keyword_groups declarative matchers against player action text."""
    any_kws = spec.get("any_keywords")
    if any_kws and not any(str(k) in text for k in any_kws):
        return False
    all_groups = spec.get("all_keyword_groups")
    if all_groups:
        for grp in all_groups:
            if not any(str(k) in text for k in grp):
                return False
    return True


class GameSession:
    """In-memory game session tracking player state and Agent conversation ID."""

    def __init__(
        self,
        session_id: str,
        scenario_id: str,
        initial_state: PlayerState,
        world: Optional[WorldSpec] = None,
    ):
        self.session_id = session_id
        self.scenario_id = scenario_id
        self.world = world
        self.player_state = initial_state
        self.player_state._scenario_id = scenario_id
        self.agent_conversation_id: Optional[str] = None
        self.history: List[Dict[str, str]] = []
        self.dynamic_actions: List[Dict[str, Any]] = []
        self.inventory_synced: bool = False
        self.skills_synced: bool = False

    def apply_delta(self, delta: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Apply state delta and return standard JSON-patch like delta list."""
        patches: List[Dict[str, Any]] = []
        prev_scene = self.player_state.current_scene
        world = self.world
        scoped_defaults = (world.scene_scoped_defaults if world else {}) or {}
        item_catalog = (world.item_catalog if world else {}) or {}
        unique_items = set((world.unique_items if world else []) or [])

        if "current_scene" in delta and delta["current_scene"]:
            new_scene = delta["current_scene"]
            self.player_state.current_scene = new_scene
            if new_scene != prev_scene and "available_actions" not in delta:
                self.dynamic_actions = []
            patches.append({"op": "replace", "path": "/current_scene", "value": new_scene})
            if new_scene != prev_scene:
                for base_key, default_val in scoped_defaults.items():
                    scoped_key = f"{new_scene}_{base_key}"
                    if scoped_key in self.player_state.variables:
                        synced_val = self.player_state.variables[scoped_key]
                        self.player_state.variables[base_key] = synced_val
                        patches.append({"op": "add", "path": f"/variables/{base_key}", "value": synced_val})
                    elif base_key in self.player_state.variables and any(
                        vk.endswith(f"_{base_key}") for vk in self.player_state.variables
                    ):
                        self.player_state.variables[base_key] = default_val
                        patches.append({"op": "add", "path": f"/variables/{base_key}", "value": default_val})

        if "max_hp" in delta and delta["max_hp"] is not None:
            self.player_state.max_hp = max(1, int(delta["max_hp"]))
            patches.append({"op": "replace", "path": "/max_hp", "value": self.player_state.max_hp})
        elif "max_hp_delta" in delta:
            base_max_hp = int(self.player_state.max_hp or 100)
            self.player_state.max_hp = max(1, base_max_hp + int(delta["max_hp_delta"]))
            patches.append({"op": "replace", "path": "/max_hp", "value": self.player_state.max_hp})

        hp_cap = max(1, int(self.player_state.max_hp or 100))
        if "hp" in delta:
            self.player_state.hp = max(0, min(hp_cap, int(delta["hp"])))
            patches.append({"op": "replace", "path": "/hp", "value": self.player_state.hp})
        elif "hp_delta" in delta:
            self.player_state.hp = max(0, min(hp_cap, self.player_state.hp + int(delta["hp_delta"])))
            patches.append({"op": "replace", "path": "/hp", "value": self.player_state.hp})

        if "max_mp" in delta and delta["max_mp"] is not None:
            self.player_state.max_mp = max(0, int(delta["max_mp"]))
            patches.append({"op": "replace", "path": "/max_mp", "value": self.player_state.max_mp})
        elif "max_mp_delta" in delta:
            base_max_mp = int(self.player_state.max_mp if self.player_state.max_mp is not None else 100)
            self.player_state.max_mp = max(0, base_max_mp + int(delta["max_mp_delta"]))
            patches.append({"op": "replace", "path": "/max_mp", "value": self.player_state.max_mp})

        mp_cap = max(0, int(self.player_state.max_mp if self.player_state.max_mp is not None else 100))
        if "mp" in delta and delta["mp"] is not None:
            self.player_state.mp = max(0, min(mp_cap, int(delta["mp"])))
            patches.append({"op": "replace", "path": "/mp", "value": self.player_state.mp})
        elif "mp_delta" in delta:
            curr_mp = self.player_state.mp if self.player_state.mp is not None else mp_cap
            self.player_state.mp = max(0, min(mp_cap, curr_mp + int(delta["mp_delta"])))
            patches.append({"op": "replace", "path": "/mp", "value": self.player_state.mp})

        if "san" in delta:
            self.player_state.san = max(0, min(100, int(delta["san"])))
            patches.append({"op": "replace", "path": "/san", "value": self.player_state.san})
        elif "san_delta" in delta:
            self.player_state.san = max(0, min(100, self.player_state.san + int(delta["san_delta"])))
            patches.append({"op": "replace", "path": "/san", "value": self.player_state.san})

        if "gold" in delta:
            self.player_state.gold = int(delta["gold"])
            patches.append({"op": "replace", "path": "/gold", "value": self.player_state.gold})
        elif "gold_delta" in delta:
            self.player_state.gold = max(0, self.player_state.gold + int(delta["gold_delta"]))
            patches.append({"op": "replace", "path": "/gold", "value": self.player_state.gold})

        if "variables" in delta and isinstance(delta["variables"], dict):
            active_scene = self.player_state.current_scene
            delta_vars = delta["variables"]
            for k, v in delta_vars.items():
                self.player_state.variables[k] = v
                patches.append({"op": "add", "path": f"/variables/{k}", "value": v})
                if active_scene and k in scoped_defaults:
                    scoped_key = f"{active_scene}_{k}"
                    if scoped_key not in delta_vars:
                        self.player_state.variables[scoped_key] = v
                        patches.append({"op": "add", "path": f"/variables/{scoped_key}", "value": v})
                elif active_scene:
                    for base_key in scoped_defaults:
                        if k == f"{active_scene}_{base_key}" and base_key not in delta_vars:
                            self.player_state.variables[base_key] = v
                            patches.append({"op": "add", "path": f"/variables/{base_key}", "value": v})
            if "weather" in delta_vars and "weather_type" not in delta_vars:
                inferred_type = classify_weather_type(str(delta_vars["weather"]))
                self.player_state.variables["weather_type"] = inferred_type
                self.player_state.variables["weather_duration"] = 1
                patches.append({"op": "add", "path": "/variables/weather_type", "value": inferred_type})
                patches.append({"op": "add", "path": "/variables/weather_duration", "value": 1})

        if "variables_delta" in delta and isinstance(delta["variables_delta"], dict):
            for k, v in delta["variables_delta"].items():
                curr_v = self.player_state.variables.get(k, 0)
                if not isinstance(curr_v, (int, float)):
                    curr_v = 0
                new_v = _clamp_variable(k, int(curr_v) + int(v), self.player_state.variables, world)
                self.player_state.variables[k] = new_v
                patches.append({"op": "add", "path": f"/variables/{k}", "value": new_v})

        if "add_structures" in delta and isinstance(delta["add_structures"], list):
            existing_structs = list(self.player_state.variables.get("built_structures") or [])
            target_scene_default = delta.get("current_scene") or self.player_state.current_scene
            seen_struct_keys = {
                (s.get("id"), s.get("scene_id") or "")
                for s in existing_structs
                if isinstance(s, dict) and s.get("id")
            }
            struct_added = False
            for raw_struct in delta["add_structures"]:
                if isinstance(raw_struct, dict) and raw_struct.get("id"):
                    sid = str(raw_struct["id"])
                    struct_scene = str(raw_struct.get("scene_id") or target_scene_default or "").strip()
                    if (sid, struct_scene) not in seen_struct_keys:
                        entry = {
                            "id": sid,
                            "name": raw_struct.get("name", sid),
                            "image": raw_struct.get("image", ""),
                            "side": raw_struct.get("side", "left"),
                            "caption": raw_struct.get("caption", raw_struct.get("name", sid)),
                            "tooltip": raw_struct.get("tooltip", ""),
                            "category": "structure",
                            "tag": raw_struct.get("tag", "已建成"),
                            "scene_id": struct_scene,
                        }
                        existing_structs.append(entry)
                        seen_struct_keys.add((sid, struct_scene))
                        struct_added = True
            if struct_added:
                self.player_state.variables["built_structures"] = existing_structs
                patches.append({
                    "op": "add",
                    "path": "/variables/built_structures",
                    "value": existing_structs,
                })

        if "time_cost" in delta and delta["time_cost"]:
            steps = int(delta["time_cost"])
            if steps > 0 and "time_slot" in self.player_state.variables:
                curr_slot = self.player_state.variables.get("time_slot", "上午")
                idx = TIME_SLOTS.index(curr_slot) if curr_slot in TIME_SLOTS else 1
                total = idx + steps
                day_inc = total // len(TIME_SLOTS)
                new_slot = TIME_SLOTS[total % len(TIME_SLOTS)]
                self.player_state.variables["time_slot"] = new_slot
                patches.append({"op": "add", "path": "/variables/time_slot", "value": new_slot})
                if day_inc > 0:
                    new_day = int(self.player_state.variables.get("day", 1) or 1) + day_inc
                    self.player_state.variables["day"] = new_day
                    patches.append({"op": "add", "path": "/variables/day", "value": new_day})
                new_turn = int(self.player_state.variables.get("turn_count", 0) or 0) + 1
                self.player_state.variables["turn_count"] = new_turn
                patches.append({"op": "add", "path": "/variables/turn_count", "value": new_turn})

                # Dynamically advance weather when scenario tracks weather
                explicit_weather = (
                    isinstance(delta.get("variables"), dict)
                    and "weather" in delta["variables"]
                )
                if "weather" in self.player_state.variables and not explicit_weather:
                    cur_w = str(self.player_state.variables.get("weather") or "")
                    cur_type = str(self.player_state.variables.get("weather_type") or "")
                    cur_dur = int(self.player_state.variables.get("weather_duration") or 1)
                    next_w, next_type, next_dur = advance_weather(
                        cur_w, cur_type, new_slot, duration=cur_dur
                    )
                    self.player_state.variables["weather"] = next_w
                    self.player_state.variables["weather_type"] = next_type
                    self.player_state.variables["weather_duration"] = next_dur
                    patches.append({"op": "add", "path": "/variables/weather", "value": next_w})
                    patches.append({"op": "add", "path": "/variables/weather_type", "value": next_type})
                    patches.append({"op": "add", "path": "/variables/weather_duration", "value": next_dur})

        # Track attribute modifications (relative delta first, then explicit overrides)
        attr_updates: Dict[str, int] = {}
        if "attributes_delta" in delta and isinstance(delta["attributes_delta"], dict):
            for k, v in delta["attributes_delta"].items():
                curr_val = int(self.player_state.attributes.get(k, 0))
                new_val = _clamp_attr(k, curr_val + int(v), world)
                self.player_state.attributes[k] = new_val
                attr_updates[k] = new_val

        if "attributes" in delta and isinstance(delta["attributes"], dict):
            for k, v in delta["attributes"].items():
                new_val = _clamp_attr(k, int(v), world)
                self.player_state.attributes[k] = new_val
                attr_updates[k] = new_val

        for k, val in attr_updates.items():
            patches.append({"op": "replace", "path": f"/attributes/{k}", "value": val})

        # Process item removal/consumption before addition
        removed_any = False
        remove_list = delta.get("remove_inventory") or delta.get("consume_inventory")
        if remove_list and isinstance(remove_list, list):
            for raw_rem in remove_list:
                rem_id = raw_rem.get("id") if isinstance(raw_rem, dict) else str(raw_rem)
                for i, inv_item in enumerate(self.player_state.inventory):
                    if isinstance(inv_item, dict) and inv_item.get("id") == rem_id:
                        self.player_state.inventory.pop(i)
                        removed_any = True
                        break

        added_items: List[Dict[str, Any]] = []
        if "add_inventory" in delta and isinstance(delta["add_inventory"], list):
            existing_ids = {
                (i.get("id") if isinstance(i, dict) else str(i))
                for i in self.player_state.inventory
            }
            for raw_item in delta["add_inventory"]:
                item = _enrich_item_meta(raw_item, item_catalog)
                item_id = item.get("id")
                if item_id in unique_items and item_id in existing_ids:
                    continue
                self.player_state.inventory.append(item)
                existing_ids.add(item_id)
                added_items.append(item)

        if removed_any:
            patches.append({"op": "replace", "path": "/inventory", "value": list(self.player_state.inventory)})
        else:
            for item in added_items:
                patches.append({"op": "add", "path": "/inventory/-", "value": item})

        # Process outfit & accessories updates (partial slot patch + unequip)
        outfit_changed = False
        unequip_list = delta.get("unequip_outfit")
        if unequip_list:
            targets = [unequip_list] if isinstance(unequip_list, str) else list(unequip_list)
            for target in targets:
                if target in self.player_state.outfit:
                    self.player_state.outfit.pop(target, None)
                    outfit_changed = True
                else:
                    for slot_k, slot_v in list(self.player_state.outfit.items()):
                        if isinstance(slot_v, dict) and slot_v.get("id") == target:
                            self.player_state.outfit.pop(slot_k, None)
                            outfit_changed = True

        outfit_updates = delta.get("outfit") or delta.get("equip_outfit")
        if isinstance(outfit_updates, dict):
            for slot, raw_piece in outfit_updates.items():
                if raw_piece is None or raw_piece == "" or raw_piece == {}:
                    if slot in self.player_state.outfit:
                        self.player_state.outfit.pop(slot, None)
                        outfit_changed = True
                else:
                    self.player_state.outfit[slot] = _enrich_item_meta(raw_piece, item_catalog)
                    outfit_changed = True

        if outfit_changed:
            patches.append({"op": "replace", "path": "/outfit", "value": dict(self.player_state.outfit)})

        # Process skills bar updates (full replace, upsert learn_skills/add_skills, remove, and rank bump)
        skills_changed = False
        skills_replaced = False
        if "skills" in delta and isinstance(delta["skills"], list):
            self.player_state.skills = [_enrich_skill_meta(s) for s in delta["skills"]]
            skills_changed = True
            skills_replaced = True

        rem_skills = delta.get("remove_skills")
        if isinstance(rem_skills, list) and rem_skills:
            rem_targets = {str(r.get("id") if isinstance(r, dict) else r) for r in rem_skills}
            filtered = [
                s for s in self.player_state.skills
                if s.get("id") not in rem_targets and s.get("name") not in rem_targets
            ]
            if len(filtered) != len(self.player_state.skills):
                self.player_state.skills = filtered
                skills_changed = True

        add_skills = delta.get("learn_skills") or delta.get("add_skills")
        if isinstance(add_skills, list) and add_skills:
            for raw_sk in add_skills:
                sk = _enrich_skill_meta(raw_sk)
                sk_id = sk.get("id")
                existing_idx = next(
                    (idx for idx, cur in enumerate(self.player_state.skills) if cur.get("id") == sk_id),
                    None,
                )
                if existing_idx is not None:
                    self.player_state.skills[existing_idx] = {**self.player_state.skills[existing_idx], **sk}
                else:
                    self.player_state.skills.append(sk)
                skills_changed = True

        if (
            not skills_replaced
            and isinstance(delta.get("variables"), dict)
            and "skill_rank" in delta["variables"]
            and self.player_state.skills
        ):
            try:
                new_rank = int(delta["variables"]["skill_rank"])
                self.player_state.skills = [_bump_skill_rank(s, new_rank) for s in self.player_state.skills]
                skills_changed = True
            except (ValueError, TypeError):
                pass

        if skills_changed:
            patches.append({"op": "replace", "path": "/skills", "value": list(self.player_state.skills)})

        # Process AG-UI declarative hud_widgets updates (upsert by id / replace / remove)
        hud_changed = False
        if delta.get("replace_hud_widgets") and isinstance(delta.get("hud_widgets"), list):
            self.player_state.hud_widgets = [
                dict(w) for w in delta["hud_widgets"] if isinstance(w, dict)
            ]
            hud_changed = True
        else:
            rem_widgets = delta.get("remove_hud_widgets")
            if rem_widgets:
                rem_w_ids = {
                    str(x) for x in ([rem_widgets] if isinstance(rem_widgets, str) else rem_widgets)
                }
                filtered_w = [
                    w for w in (self.player_state.hud_widgets or [])
                    if str(w.get("id", "")) not in rem_w_ids
                ]
                if len(filtered_w) != len(self.player_state.hud_widgets or []):
                    self.player_state.hud_widgets = filtered_w
                    hud_changed = True

            if isinstance(delta.get("hud_widgets"), list):
                cur_widgets = [
                    dict(w) for w in (self.player_state.hud_widgets or []) if isinstance(w, dict)
                ]
                for raw_w in delta["hud_widgets"]:
                    if not isinstance(raw_w, dict):
                        continue
                    w = dict(raw_w)
                    wid = w.get("id")
                    if wid:
                        idx = next(
                            (i for i, existing in enumerate(cur_widgets) if existing.get("id") == wid),
                            None,
                        )
                        if idx is not None:
                            cur_widgets[idx] = {**cur_widgets[idx], **w}
                        else:
                            cur_widgets.append(w)
                    else:
                        cur_widgets.append(w)
                    hud_changed = True
                self.player_state.hud_widgets = cur_widgets

        if hud_changed:
            patches.append({"op": "replace", "path": "/hud_widgets", "value": list(self.player_state.hud_widgets)})

        if "available_actions" in delta and isinstance(delta["available_actions"], list):
            self.dynamic_actions = [a for a in delta["available_actions"] if isinstance(a, dict)]

        if "visuals" in delta and isinstance(delta["visuals"], dict):
            patches.append({"op": "replace", "path": "/visuals", "value": delta["visuals"]})

        check_obj = delta.get("check_result") or delta.get("check")
        if isinstance(check_obj, dict):
            patches.append({"op": "replace", "path": "/check_result", "value": check_obj})

        return patches


class AGUIBridge:
    """Bridges game events and CLI agent output to AG-UI SSE protocol."""

    def __init__(self, scenario_mgr: ScenarioManager, driver: BaseAgentDriver):
        self.scenario_mgr = scenario_mgr
        self.driver = driver
        self.encoder = EventEncoder()
        self.sessions: Dict[str, GameSession] = {}
        self.studio_conversations: Dict[str, str] = {}

    def set_driver(self, driver: BaseAgentDriver) -> BaseAgentDriver:
        """Hot-swap the agent backend; returns the previous driver so the caller can close it.

        Agent-side conversation ids belong to the old backend and cannot be resumed on the new
        one, so they are dropped (game state itself lives in the client/session player_state).
        """
        old = self.driver
        self.driver = driver
        for session in self.sessions.values():
            session.agent_conversation_id = None
        self.studio_conversations.clear()
        return old

    def _resolve_world(self, scenario_id: Optional[str]) -> Optional[WorldSpec]:
        if not scenario_id:
            return None
        try:
            return self.scenario_mgr.load_scenario(scenario_id).world
        except Exception:
            return None

    @staticmethod
    def _sync_player_state(
        target: PlayerState,
        source: Dict[str, Any],
        world: Optional[WorldSpec] = None,
    ) -> bool:
        """Sync runtime player state from client to prevent server restart desync.

        Returns True if inventory was deduplicated or updated.
        """
        if not isinstance(source, dict):
            return False

        item_catalog = (world.item_catalog if world else {}) or {}
        unique_items = set((world.unique_items if world else []) or [])

        if "current_scene" in source and source["current_scene"]:
            target.current_scene = source["current_scene"]
        if "max_hp" in source and isinstance(source["max_hp"], (int, float)):
            target.max_hp = max(1, int(source["max_hp"]))
        if "hp" in source and isinstance(source["hp"], (int, float)):
            target.hp = int(source["hp"])
        if "max_mp" in source and isinstance(source["max_mp"], (int, float)):
            target.max_mp = max(0, int(source["max_mp"]))
        if "mp" in source and isinstance(source["mp"], (int, float)):
            target.mp = int(source["mp"])
        if "san" in source and isinstance(source["san"], (int, float)):
            target.san = int(source["san"])
        if "gold" in source and isinstance(source["gold"], (int, float)):
            target.gold = int(source["gold"])
        if "attributes" in source and isinstance(source["attributes"], dict):
            for k, v in source["attributes"].items():
                target.attributes[k] = int(v)
        if "variables" in source and isinstance(source["variables"], dict):
            for k, v in source["variables"].items():
                target.variables[k] = v
        if "outfit" in source and isinstance(source["outfit"], dict):
            target.outfit = {
                k: _enrich_item_meta(v, item_catalog)
                for k, v in source["outfit"].items()
                if isinstance(v, dict)
            }
        if "skills" in source and isinstance(source["skills"], list):
            target.skills = [
                _enrich_skill_meta(s)
                for s in source["skills"]
                if isinstance(s, (dict, str))
            ]
        if "hud_widgets" in source and isinstance(source["hud_widgets"], list):
            target.hud_widgets = [dict(w) for w in source["hud_widgets"] if isinstance(w, dict)]

        inv_changed = False
        if "inventory" in source and isinstance(source["inventory"], list):
            deduped_inv = []
            seen_unique = set()
            for raw_item in source["inventory"]:
                if isinstance(raw_item, dict):
                    item = _enrich_item_meta(raw_item, item_catalog)
                    item_id = item.get("id")
                    if item_id in unique_items:
                        if item_id in seen_unique:
                            inv_changed = True
                            continue
                        seen_unique.add(item_id)
                    deduped_inv.append(item)
            if len(deduped_inv) != len(target.inventory) or deduped_inv != target.inventory:
                target.inventory = deduped_inv
                inv_changed = True

        return inv_changed

    def get_or_create_session(
        self,
        thread_id: str,
        scenario_id: str = "black_crow_manor",
        client_state: Optional[Dict[str, Any]] = None,
    ) -> GameSession:
        if thread_id in self.sessions:
            session = self.sessions[thread_id]
            world = self._resolve_world(session.scenario_id) or session.world
            session.world = world
            session.player_state._scenario_id = session.scenario_id
            if client_state:
                if self._sync_player_state(session.player_state, client_state, world=world):
                    session.inventory_synced = True
            if _hydrate_class_skills(self.scenario_mgr, session.scenario_id, session.player_state):
                session.skills_synced = True
            return session

        spec = self.scenario_mgr.load_scenario(scenario_id)
        init_state = PlayerState(**spec.world.initial_player_state.model_dump())
        init_state._scenario_id = scenario_id
        inv_synced = False
        if client_state:
            inv_synced = self._sync_player_state(init_state, client_state, world=spec.world)
        skills_synced = _hydrate_class_skills(self.scenario_mgr, scenario_id, init_state)

        session = GameSession(thread_id, scenario_id, init_state, world=spec.world)
        session.inventory_synced = inv_synced
        session.skills_synced = skills_synced
        self.sessions[thread_id] = session
        return session

    def build_play_prompt(
        self,
        session: GameSession,
        user_input: str,
        check_eval: Optional[Dict[str, Any]] = None,
    ) -> str:
        scenario = self.scenario_mgr.load_scenario(session.scenario_id)
        curr_scene_id = session.player_state.current_scene or scenario.world.initial_scene
        curr_scene = self.scenario_mgr.get_scene(session.scenario_id, curr_scene_id)

        scene_desc = curr_scene.description if curr_scene else "未知场景"
        scene_npcs = [f"{npc.name} ({npc.greeting}) [立绘: {npc.avatar or '无'}]" for npc in (curr_scene.npcs if curr_scene else [])]
        resolved_actions = resolve_scene_actions(curr_scene, session.player_state, session.dynamic_actions)
        scene_actions = [f"[{act.id}] {act.label}" for act in resolved_actions]
        scene_bg = curr_scene.background or (curr_scene.visuals.background if curr_scene and curr_scene.visuals else "")
        scene_hero = curr_scene.hero_image or (curr_scene.visuals.hero_image if curr_scene and curr_scene.visuals else "")
        scene_fg = curr_scene.foreground or (curr_scene.visuals.foreground if curr_scene and curr_scene.visuals else "")
        scene_atmo = curr_scene.visuals.atmosphere if (curr_scene and curr_scene.visuals) else "阴冷、静谧"
        cur_weather = str((session.player_state.variables or {}).get("weather") or "")
        cur_weather_type = str((session.player_state.variables or {}).get("weather_type") or "")
        cur_slot = str((session.player_state.variables or {}).get("time_slot") or "")
        if cur_weather:
            weather_atmo = get_weather_atmosphere(cur_weather, cur_weather_type, cur_slot)
            scene_atmo = f"{scene_atmo} · {weather_atmo}"
        resolved_decs = resolve_scene_decorations(curr_scene, session.player_state)
        built_structs = [
            f"{d.name} ({'左侧图像区' if d.side == 'left' else '右侧图像区'})"
            for d in resolved_decs
            if d.category == "structure"
        ]
        inv_desc = [
            f"{item.get('name', item.get('id', ''))} (id: {item.get('id', '')})"
            for item in session.player_state.inventory
        ]
        outfit_desc = [
            f"{slot}: {piece.get('name', piece.get('id', ''))}"
            for slot, piece in (session.player_state.outfit or {}).items()
            if isinstance(piece, dict) and (piece.get("name") or piece.get("id"))
        ]
        skills_desc = [
            f"{sk.get('name', sk.get('id', ''))}"
            f"{' Lv.' + str(sk['level']) if sk.get('level') else ''}"
            f"{'（' + sk['desc'] + ('；作用：' + sk['effect'] if sk.get('effect') else '') + '）' if (sk.get('desc') or sk.get('effect')) else ''}"
            for sk in (session.player_state.skills or [])
            if isinstance(sk, dict) and (sk.get("name") or sk.get("id"))
        ]
        widgets_desc = [
            f"{w.get('id', '?')} ({w.get('type', 'panel')}: {w.get('title', '')})"
            for w in (session.player_state.hud_widgets or [])
            if isinstance(w, dict)
        ]

        history_block = ""
        if session.history:
            recent = session.history[-6:]
            history_lines = [
                f"- {'玩家' if h.get('role') == 'user' else 'DM'}: {h.get('content', '')}"
                for h in recent
            ]
            history_block = "\n近期剧情回溯：\n" + "\n".join(history_lines) + "\n"

        check_eval_block = ""
        if check_eval:
            check_eval_block = f"""
【DM 综合裁决基准参考】：
- 检定技能：{check_eval.get('skill')} | 检定难度 DC：{check_eval.get('difficulty')}
- 投骰数值：D20 = {check_eval.get('roll')}，综合状态/装备修正：{check_eval.get('modifier')}，最终判定总值：{check_eval.get('total')}
- 综合判定梯度：{check_eval.get('outcome_label')} ({check_eval.get('outcome')})
- 判定核心依据：{check_eval.get('reason')}
- 裁决导向建议：{check_eval.get('message')}
（请作为权威 DM 尊重并融合此综合修正结果，在剧情中生动展现装备/体魄/工具如何协助或制约该动作，并在 state_delta.check_result 中准确回传裁决数据）
"""

        mp_line = ""
        if session.player_state.mp is not None:
            mp_label = str((session.player_state.variables or {}).get("mp_label") or "魔法值")
            mp_max = session.player_state.max_mp if session.player_state.max_mp is not None else 100
            mp_line = f" / {mp_label}（MP）：{session.player_state.mp}/{mp_max}"

        dm_rules_block = ""
        if scenario.world.dm_rules and scenario.world.dm_rules.strip():
            dm_rules_block = f"\n【剧本专属规则与数值体系 (World Rules)】：\n{scenario.world.dm_rules.strip()}\n"

        prompt = f"""你是一款高沉浸感文字跑团（TRPG / SLG）的地下城主（DM / Game Master）兼视觉导演（遵循 ag-slg-director 规范）。
当前世界观：{scenario.world.title} (ID: {scenario.world.id})
玩家当前状态：
- 角色名：{session.player_state.name}
- HP：{session.player_state.hp}/{session.player_state.max_hp}{mp_line} / SAN：{session.player_state.san} / 金币：{session.player_state.gold}
- 角色与生存属性：{session.player_state.attributes}
- 背包物品：{inv_desc or '空'}
- 当前穿着与配饰：{outfit_desc or '常规随身衣物'}
- 技能栏：{skills_desc or '尚未习得特殊技能'}
- 剧本变量：{session.player_state.variables}
- 已挂载 AG-UI 专属界面组件 (hud_widgets)：{widgets_desc or '无'}
- 当前气象与环境基调：{cur_weather or '未设定'}（氛围：{scene_atmo}）
- 当前所在场景：{curr_scene.title if curr_scene else curr_scene_id} ({curr_scene_id}){dm_rules_block}

当前场景预设视觉资源：
- 场景底图 (Background): {scene_bg or '默认空间背景'}
- 焦点插图 (Hero Image): {scene_hero or '无'}
- 前景立绘 (Foreground): {scene_fg or '无'}
- 环境氛围 (Atmosphere): {scene_atmo}
- 左右侧图像区已建成耐用设施 (Built Structures): {built_structs or '暂无'}

当前场景环境描述：
{scene_desc}

场景中存在的人物：
{scene_npcs or '无'}

当前可用行动选项（仅供参考，非强制限制）：
{scene_actions or '无'}
{history_block}{check_eval_block}
玩家执行了以下行动：
"{user_input}"

请作为 DM 进行剧情演绎与多图层视觉编排：
1. 玩家意图忠实原则（最高优先级）：
   - 仔细分辨玩家输入的具体动词与目标，严格按玩家当前行动的字面意图推进，切勿强行套用无关的预设选项结局，也严禁无视玩家背包或已装备道具的真实持有状态。
   - 凡玩家明确拾取、清洗带走、制作、消耗或使用实体物品，都必须在 `state_delta.add_inventory`（含 `id`、`name`、`desc`）与 `state_delta.remove_inventory` 中准确更新，确保背包栏真实同步。
2. DM 综合裁决与灵活判定法则（代入感与策略性核心）：
   - 杜绝生硬机械的二元通过/失败，全面综合玩家的【属性点】+【穿戴装备与衣物】+【随身工具道具】+【剧本状态条件】给出多维裁决修正；
   - 采用 TRPG 四阶递进式裁决深度演化剧情：
     · 卓越成功 (Critical Success, Total >= DC + 5 或 Nat 20)：游刃有余、精妙达成，不仅达成全部目标，还可节省消耗或获得额外收益；
     · 顺利达成 (Success, DC <= Total < DC + 5)：稳扎稳打达成目标，消耗标准资源；
     · 代价成功 (Partial Success, DC - 3 <= Total < DC)：虽遇险阻但凭借装备或毅力达成了核心目标，付出额外代价；
     · 受挫转折 (Failure with Momentum, Total < DC - 3 或 Nat 1)：行动受阻但不卡死故事，转化为新的局势信息或转折。
   - 若本次行动包含检定，请在回复末尾的 ```state_delta``` 中附带 `check_result` 字段记录裁决明细。
3. 叙事文本与对话分明：生动叙述环境与行动结果，NPC 发言请以 角色名: “对话内容” 格式清晰表达。严禁在叙述文本中直接泄漏具体图片文件路径。
4. 视觉舞台导演原则（ag-slg-director）：
   - 背景稳定性：不要在普通对话轮换背景；仅在发生场景转移或环境巨变时更新 visuals.background。
   - 角色立绘调度：与具体 NPC 对话时，设置 visuals.foreground 为其立绘；玩家独处或离开时置空。
   - 焦点特写镜头：发现关键线索、拾获物品或遭遇高潮事件时，在 visuals.hero_image 给出特写插图路径或语义描述。
   - 左右侧耐用设施展示：建成场景耐用设施时，通过 `state_delta.variables` 或 `state_delta.add_structures`（含 `id`, `name`, `image`, `side: "left"|"right"`, `caption`, `tooltip`, `scene_id`）展示在当前场景边缘。
   - **场景隔离原则**：离开当前场景前往新场景（`current_scene` 变更）时，同步更新 `visuals.background` 为目标场景底图，清空原场景的临时立绘与特写，且绝不将原场景已建设施带入新场景。
5. 数值推演、动态选项与 AG-UI 声明式 HUD 调度：
   - 可通过 `attributes_delta`、`hp_delta`、`mp_delta`、`san_delta`、`variables`、`variables_delta`、`time_cost` 更新世界状态。
   - 如剧本需要自定义状态栏、Boss/遭遇面板、阶段追踪器或额外资源条，可通过 `hud_widgets`（支持 `metrics` / `tracker` / `panel` 三类原语，按 `id` 新增或增量更新，支持 `value_ref` 绑定 `attributes.*` / `variables.*`）自主生成或更新前端界面，并在事件结束后通过 `remove_hud_widgets` 撤除。
   - 如因剧情变化衍生出新的临时行动选项，可通过 `available_actions` 提供动态选项列表。
6. 若产生场景转移、数值变化、道具增减、HUD 变更或视觉更新，在回复最末尾附带一个 ```state_delta 代码块：
```state_delta
{{
  "current_scene": "目标场景ID（若发生转移）",
  "hp_delta": 0,
  "mp_delta": 0,
  "san_delta": 0,
  "attributes_delta": {{}},
  "time_cost": 1,
  "add_inventory": [{{"id": "item_id", "name": "道具名", "desc": "描述"}}],
  "remove_inventory": ["consumed_item_id"],
  "outfit": {{"slot": {{"id": "item_id", "name": "穿戴名称", "desc": "描述", "tag": "标签"}}}},
  "learn_skills": [{{"id": "skill_id", "name": "技能名称", "desc": "技能简介", "effect": "作用说明", "cost": "消耗", "cooldown": "冷却", "level": 1, "tag": "类型"}}],
  "variables": {{"variable_key": "variable_value"}},
  "variables_delta": {{"numeric_var": -10}},
  "hud_widgets": [
    {{
      "id": "custom_panel",
      "type": "panel",
      "title": "事件或首领名称",
      "tone": "danger",
      "bars": [{{"label": "生命", "value_ref": "variables.boss_hp", "max_ref": "variables.boss_max_hp", "color": "rose"}}]
    }}
  ],
  "remove_hud_widgets": ["obsolete_widget_id"],
  "check_result": {{
    "skill": "perception",
    "difficulty": 10,
    "roll": 12,
    "modifier": 2,
    "total": 14,
    "isSuccess": true,
    "outcome": "success",
    "outcome_label": "顺利达成",
    "reason": "属性修正(+1)、装备加成(+1)",
    "message": "成功洞察关键细节"
  }},
  "available_actions": [
    {{"id": "dynamic_act_1", "label": "新的情境行动", "type": "interact"}}
  ],
  "visuals": {{
    "background": "{scene_bg}",
    "foreground": "",
    "hero_image": "",
    "atmosphere": "{scene_atmo}"
  }}
}}
```
注意：仅输出实际发生变化的字段；若状态与视觉图层没有任何变化，无需输出 state_delta 代码块。
"""

        return prompt

    @staticmethod
    def _merge_action_effects(
        delta_dict: Dict[str, Any],
        action: ActionOption,
        check_passed: Optional[bool],
        player_state: PlayerState,
    ) -> Dict[str, Any]:
        """Ensure deterministic YAML action effects are merged without double-applying LLM delta."""
        outcome: Dict[str, Any] = {}
        if action.effects:
            outcome.update(action.effects)
        if action.type == "check":
            branch = action.on_success if check_passed is not False else action.on_failure
            if branch:
                outcome.update(branch)
        elif action.on_success:
            outcome.update(action.on_success)

        if not outcome and action.type != "transition":
            return delta_dict

        merged = dict(delta_dict)

        # Scene transition
        target_scene = outcome.get("transition_scene") or (
            action.target_scene if action.type == "transition" else None
        )
        if target_scene and not merged.get("current_scene"):
            merged["current_scene"] = target_scene

        # Gain item
        gain_item = outcome.get("gain_item")
        if gain_item:
            add_list = list(merged.get("add_inventory") or [])
            existing_add_ids = {
                (i.get("id") if isinstance(i, dict) else str(i)) for i in add_list
            }
            if gain_item not in existing_add_ids:
                add_list.append({"id": gain_item, "name": gain_item})
                merged["add_inventory"] = add_list

        # Equip / unequip outfit pieces
        equip_outfit = outcome.get("equip_outfit")
        if isinstance(equip_outfit, dict):
            outfit_dict = dict(merged.get("outfit") or {})
            for slot, piece in equip_outfit.items():
                if slot not in outfit_dict:
                    outfit_dict[slot] = piece
            if outfit_dict:
                merged["outfit"] = outfit_dict
        if outcome.get("unequip_outfit") and "unequip_outfit" not in merged:
            merged["unequip_outfit"] = outcome["unequip_outfit"]

        # Skills bar updates
        if isinstance(outcome.get("skills"), list) and not merged.get("skills"):
            merged["skills"] = outcome["skills"]
        outcome_learn = outcome.get("learn_skills") or outcome.get("add_skills")
        if isinstance(outcome_learn, list) and not merged.get("learn_skills") and not merged.get("add_skills"):
            merged["learn_skills"] = outcome_learn
        if isinstance(outcome.get("remove_skills"), list) and not merged.get("remove_skills"):
            merged["remove_skills"] = outcome["remove_skills"]

        # Consume item(s)
        rem_list = list(merged.get("remove_inventory") or merged.get("consume_inventory") or [])
        rem_ids = {(i.get("id") if isinstance(i, dict) else str(i)) for i in rem_list}
        consume_targets: List[str] = []
        if outcome.get("consume_item"):
            consume_targets.append(outcome["consume_item"])
        if isinstance(outcome.get("consume_items"), list):
            consume_targets.extend(outcome["consume_items"])
        if isinstance(outcome.get("consume_any_item"), list):
            inv_ids = [
                item.get("id", "")
                for item in (player_state.inventory or [])
                if isinstance(item, dict)
            ]
            for cand in outcome["consume_any_item"]:
                if cand in inv_ids:
                    consume_targets.append(cand)
                    break
        for cid in consume_targets:
            if cid not in rem_ids:
                rem_list.append(cid)
                rem_ids.add(cid)
        if rem_list:
            merged["remove_inventory"] = rem_list

        # Attributes delta
        if isinstance(outcome.get("attributes_delta"), dict):
            abs_attrs = merged.get("attributes") or {}
            rel_attrs = dict(merged.get("attributes_delta") or {})
            for k, v in outcome["attributes_delta"].items():
                if k not in abs_attrs and k not in rel_attrs:
                    rel_attrs[k] = v
            if rel_attrs:
                merged["attributes_delta"] = rel_attrs

        # HP / MaxHP / MP / MaxMP / SAN / Gold delta
        if "max_hp" in outcome and "max_hp" not in merged and "max_hp_delta" not in merged:
            merged["max_hp"] = outcome["max_hp"]
        elif "max_hp_delta" in outcome and "max_hp" not in merged and "max_hp_delta" not in merged:
            merged["max_hp_delta"] = outcome["max_hp_delta"]
        if "hp" in outcome and "hp" not in merged and "hp_delta" not in merged:
            merged["hp"] = outcome["hp"]
        elif "hp_delta" in outcome and "hp" not in merged and "hp_delta" not in merged:
            merged["hp_delta"] = outcome["hp_delta"]

        if "max_mp" in outcome and "max_mp" not in merged and "max_mp_delta" not in merged:
            merged["max_mp"] = outcome["max_mp"]
        elif "max_mp_delta" in outcome and "max_mp" not in merged and "max_mp_delta" not in merged:
            merged["max_mp_delta"] = outcome["max_mp_delta"]
        if "mp" in outcome and "mp" not in merged and "mp_delta" not in merged:
            merged["mp"] = outcome["mp"]
        elif "mp_delta" in outcome and "mp" not in merged and "mp_delta" not in merged:
            merged["mp_delta"] = outcome["mp_delta"]

        if "san_delta" in outcome and "san" not in merged and "san_delta" not in merged:
            merged["san_delta"] = outcome["san_delta"]
        if "gold_delta" in outcome and "gold" not in merged and "gold_delta" not in merged:
            merged["gold_delta"] = outcome["gold_delta"]

        # Variables & relative variable deltas
        if isinstance(outcome.get("variables"), dict):
            vars_dict = dict(merged.get("variables") or {})
            for k, v in outcome["variables"].items():
                if k not in vars_dict:
                    vars_dict[k] = v
            if vars_dict:
                merged["variables"] = vars_dict

        if isinstance(outcome.get("variables_delta"), dict):
            vdelta_dict = dict(merged.get("variables_delta") or {})
            for k, v in outcome["variables_delta"].items():
                if k not in vdelta_dict:
                    vdelta_dict[k] = v
            if vdelta_dict:
                merged["variables_delta"] = vdelta_dict

        # AG-UI declarative hud_widgets passthrough
        if outcome.get("replace_hud_widgets") and "replace_hud_widgets" not in merged:
            merged["replace_hud_widgets"] = outcome["replace_hud_widgets"]
        if isinstance(outcome.get("hud_widgets"), list):
            existing_hw = list(merged.get("hud_widgets") or [])
            existing_ids = {w.get("id") for w in existing_hw if isinstance(w, dict) and w.get("id")}
            for w in outcome["hud_widgets"]:
                if isinstance(w, dict) and (not w.get("id") or w["id"] not in existing_ids):
                    existing_hw.append(dict(w))
            if existing_hw:
                merged["hud_widgets"] = existing_hw
        if outcome.get("remove_hud_widgets"):
            raw_rem = outcome["remove_hud_widgets"]
            rem_items = [raw_rem] if isinstance(raw_rem, str) else list(raw_rem)
            rem_hw = list(merged.get("remove_hud_widgets") or [])
            for wid in rem_items:
                if wid not in rem_hw:
                    rem_hw.append(wid)
            if rem_hw:
                merged["remove_hud_widgets"] = rem_hw

        if isinstance(outcome.get("visuals"), dict) and "visuals" not in merged:
            merged["visuals"] = dict(outcome["visuals"])

        # Time cost
        if outcome.get("time_cost") and "time_cost" not in merged:
            merged["time_cost"] = outcome["time_cost"]

        return merged

    @staticmethod
    def _format_rule_label(tpl: str, player_state: PlayerState) -> str:
        outfit = player_state.outfit or {}

        def _repl(match: re.Match) -> str:
            parts = match.group(1).split(".")
            if len(parts) == 3 and parts[0] == "outfit":
                piece = outfit.get(parts[1])
                if isinstance(piece, dict):
                    return str(piece.get(parts[2]) or piece.get("id") or "")
            return match.group(0)

        return re.sub(r"\{([a-zA-Z0-9_.]+)\}", _repl, tpl)

    def evaluate_agent_adjudication(
        self,
        skill: str,
        base_dc: int,
        player_state: PlayerState,
        clean_action: str,
        client_roll: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Comprehensively evaluate action check from attributes and scenario adjudication_rules."""
        roll = client_roll if (client_roll is not None and 1 <= client_roll <= 20) else random.randint(1, 20)

        # 1. Attribute modifier
        attr_val = int((player_state.attributes or {}).get(skill, 10) or 10)
        attr_mod = (attr_val - 10) // 2

        # 2. Data-driven scenario adjudication rules
        world = self._resolve_world(getattr(player_state, "_scenario_id", ""))
        rule_mod = 0
        rule_reasons: List[str] = []
        matched_groups: set[str] = set()
        outfit = player_state.outfit or {}

        for rule in (world.adjudication_rules if world else []) or []:
            if not isinstance(rule, dict):
                continue
            grp = rule.get("exclusive_group")
            if grp and grp in matched_groups:
                continue
            skill_in = rule.get("skill_in")
            if skill_in and skill not in skill_in:
                continue
            outfit_slot = rule.get("outfit_slot")
            if outfit_slot and not outfit.get(outfit_slot):
                continue
            act_kws = rule.get("action_keywords")
            if act_kws and not any(str(k) in clean_action for k in act_kws):
                continue
            not_act_kws = rule.get("not_action_keywords")
            if not_act_kws and any(str(k) in clean_action for k in not_act_kws):
                continue
            when_cond = rule.get("when")
            if when_cond and not evaluate_action_condition(when_cond, player_state):
                continue

            mod_val = int(rule.get("mod", 0) or 0)
            rule_mod += mod_val
            if grp:
                matched_groups.add(grp)
            raw_label = str(rule.get("label") or "").strip()
            if raw_label:
                rule_reasons.append(self._format_rule_label(raw_label, player_state))

        total_mod = attr_mod + rule_mod
        total = roll + total_mod

        if total >= base_dc + 5:
            outcome = "critical_success"
            label = "卓越成功"
        elif total >= base_dc:
            outcome = "success"
            label = "顺利达成"
        elif total >= base_dc - 3:
            outcome = "partial_success"
            label = "代价成功"
        else:
            outcome = "failure"
            label = "受挫转折"

        reason_parts = [f"{skill.upper()}属性({attr_mod:+d})"]
        reason_parts.extend(rule_reasons)

        return {
            "skill": skill,
            "difficulty": base_dc,
            "roll": roll,
            "modifier": total_mod,
            "total": total,
            "outcome": outcome,
            "outcome_label": label,
            "isSuccess": outcome != "failure",
            "reason": " · ".join(reason_parts),
        }

    @staticmethod
    def _resolve_declarative_branch(
        spec: Dict[str, Any],
        player_state: PlayerState,
        fmt_vars: Dict[str, str],
    ) -> tuple[str, Dict[str, Any]]:
        """Resolve a declarative fallback recipe or default_fallback block."""
        import copy

        chosen = spec
        for branch in spec.get("branches") or []:
            if not isinstance(branch, dict):
                continue
            when_cond = branch.get("when")
            if not when_cond or evaluate_action_condition(when_cond, player_state):
                chosen = branch
                break

        raw_narration = str(chosen.get("narration") or spec.get("narration") or "")
        narration = raw_narration.format(**fmt_vars) if raw_narration else ""
        delta = copy.deepcopy(chosen.get("delta") if isinstance(chosen.get("delta"), dict) else (spec.get("delta") or {}))
        return narration, delta

    def generate_fallback_turn(
        self,
        session: GameSession,
        user_text: str,
        matched_action: Optional[ActionOption],
        check_passed: Optional[bool],
        current_scene: Optional[SceneNode],
        client_roll: Optional[int] = None,
    ) -> tuple[str, Dict[str, Any]]:
        """Fallback local SLG Director: generates narrative and state delta from scenario YAML when agent is unavailable."""
        import copy

        clean_action = re.sub(r"^【.*?】", "", user_text).strip()
        clean_action = re.sub(r"\[检定数据:.*?\]", "", clean_action).strip()
        delta: Dict[str, Any] = {}
        world = session.world or self._resolve_world(session.scenario_id)

        if matched_action:
            if matched_action.type == "check":
                skill = matched_action.skill or "survival"
                dc = matched_action.difficulty or 10
                eval_res = self.evaluate_agent_adjudication(
                    skill=skill,
                    base_dc=dc,
                    player_state=session.player_state,
                    clean_action=clean_action,
                    client_roll=client_roll,
                )

                succ_msg = ""
                if matched_action.on_success and isinstance(matched_action.on_success, dict):
                    succ_msg = matched_action.on_success.get("message", "")
                if not succ_msg:
                    succ_msg = f"你沉着应对，成功【{matched_action.label}】！"

                fail_msg = ""
                if matched_action.on_failure and isinstance(matched_action.on_failure, dict):
                    fail_msg = matched_action.on_failure.get("message", "")
                if not fail_msg:
                    fail_msg = f"环境恶劣，你这次未能成功【{matched_action.label}】。"

                if eval_res["outcome"] == "critical_success":
                    narration = (
                        f"你屏息凝神，稳稳把控着周遭的每一个细节。凭借【{eval_res['reason']}】，你的动作游刃有余、精妙绝伦！\n\n"
                        f"【DM综合裁决 · 卓越成功】（投骰 {eval_res['roll']} + 修正 {eval_res['modifier']} = {eval_res['total']} vs DC: {eval_res['difficulty']}）\n\n"
                        f"{succ_msg}\n\n"
                        f"完美的预判让你不仅顺利达成了目标，甚至几乎没有消耗额外精力，信心大振！"
                    )
                    delta = copy.deepcopy(matched_action.on_success or {})
                    if "attributes_delta" in delta and isinstance(delta["attributes_delta"], dict):
                        delta["attributes_delta"] = {
                            k: (v // 2 if v < 0 else v)
                            for k, v in delta["attributes_delta"].items()
                        }
                    delta["san_delta"] = int(delta.get("san_delta", 0)) + 3
                elif eval_res["outcome"] == "success":
                    narration = (
                        f"你眼神坚定，沉稳调度全身气力与随身装备。瞅准绝佳时机，你果断出手！\n\n"
                        f"【DM综合裁决 · 顺利达成】（投骰 {eval_res['roll']} + 修正 {eval_res['modifier']} = {eval_res['total']} vs DC: {eval_res['difficulty']}）\n\n"
                        f"判定依据：{eval_res['reason']}。\n\n"
                        f"{succ_msg}"
                    )
                    delta = copy.deepcopy(matched_action.on_success or {})
                elif eval_res["outcome"] == "partial_success":
                    narration = (
                        f"周围环境险恶复杂，阻碍不断侵扰。虽然过程波折重重，但幸得【{eval_res['reason']}】的有力支撑，你咬牙撑过难关，终究在付出额外代价后艰难达成了目标！\n\n"
                        f"【DM综合裁决 · 代价成功】（投骰 {eval_res['roll']} + 修正 {eval_res['modifier']} = {eval_res['total']} vs DC: {eval_res['difficulty']}）\n\n"
                        f"{succ_msg}\n\n"
                        f"主要目标顺利达成，但激烈的应对让你多消耗了些许状态。"
                    )
                    delta = copy.deepcopy(matched_action.on_success or {})
                    if "stamina" in (session.player_state.attributes or {}):
                        if "attributes_delta" not in delta or not isinstance(delta["attributes_delta"], dict):
                            delta["attributes_delta"] = {}
                        delta["attributes_delta"]["stamina"] = int(delta["attributes_delta"].get("stamina", -4)) - 3
                    elif session.player_state.mp is not None:
                        delta["hp_delta"] = int(delta.get("hp_delta", 0)) - 4
                        delta["mp_delta"] = int(delta.get("mp_delta", 0)) - 5
                else:
                    narration = (
                        f"自然与环境的阻碍超乎预料。纵然有【{eval_res['reason']}】的勉力支撑，这次突进依然未能尽如人意。\n\n"
                        f"【DM综合裁决 · 受挫转折】（投骰 {eval_res['roll']} + 修正 {eval_res['modifier']} = {eval_res['total']} vs DC: {eval_res['difficulty']}）\n\n"
                        f"{fail_msg}\n\n"
                        f"你稳住阵脚向后轻撤半步。这次尝试虽未达成，却让你探明了前方的虚实暗礁，为下一次调整策略赢得了情报！"
                    )
                    delta = copy.deepcopy(matched_action.on_failure or {})
                    if "time_cost" not in delta and "time_slot" in (session.player_state.variables or {}):
                        delta["time_cost"] = 1
                    if "attributes_delta" not in delta and "stamina" in (session.player_state.attributes or {}):
                        delta["attributes_delta"] = {"stamina": -3, "hydration": -2}

                delta["check_result"] = eval_res
                if eval_res["isSuccess"]:
                    if "gain_item" in delta:
                        delta["add_inventory"] = [{"id": delta["gain_item"]}]
                    if "equip_outfit" in delta and "outfit" not in delta:
                        delta["outfit"] = delta["equip_outfit"]
                    if "time_cost" not in delta and "time_slot" in (session.player_state.variables or {}):
                        delta["time_cost"] = 1
            elif matched_action.type == "interact":
                succ_msg = ""
                if matched_action.on_success and isinstance(matched_action.on_success, dict):
                    succ_msg = matched_action.on_success.get("message", "")
                if not succ_msg:
                    succ_msg = f"你仔细完成了【{matched_action.label}】。"

                narration = (
                    f"你沉下心来，专注地在四周开展行动。\n\n"
                    f"【行动结果】{succ_msg}\n\n"
                    f"周围的环境因你的努力而悄然改变，为你接下来的行动开辟了新的可能。"
                )
                delta = copy.deepcopy(matched_action.on_success or {})
                if "gain_item" in delta:
                    delta["add_inventory"] = [{"id": delta["gain_item"]}]
                if "equip_outfit" in delta and "outfit" not in delta:
                    delta["outfit"] = delta["equip_outfit"]
                if "time_cost" not in delta and "time_slot" in (session.player_state.variables or {}):
                    delta["time_cost"] = 1
            elif matched_action.type == "transition":
                target_title = matched_action.target_scene or "未知新区域"
                if matched_action.target_scene:
                    target_obj = self.scenario_mgr.get_scene(session.scenario_id, matched_action.target_scene)
                    if target_obj:
                        target_title = target_obj.title
                narration = (
                    f"你收拾好随身行装，迈开脚步朝着新的方向前进。\n\n"
                    f"穿过前方的通路后，你终于抵达了【{target_title}】。\n\n"
                    f"眼前的景象豁然开朗，全新的机遇与潜在的危险正静候着你的探索。"
                )
                delta = {
                    "current_scene": matched_action.target_scene,
                }
                if "time_slot" in (session.player_state.variables or {}):
                    delta["time_cost"] = 1
                if "stamina" in (session.player_state.attributes or {}):
                    delta["attributes_delta"] = {"stamina": -5, "hydration": -4}
            else:
                narration = f"你专注于执行【{matched_action.label}】，谨慎地推动着当前的事态发展。"
                delta = {"time_cost": 1} if "time_slot" in (session.player_state.variables or {}) else {}
        else:
            p_vars = session.player_state.variables or {}
            w_label = str(p_vars.get("weather") or "")
            w_type = str(p_vars.get("weather_type") or "")
            w_slot = str(p_vars.get("time_slot") or "")
            w_cue = get_weather_narrative_cue(w_label, w_type, w_slot) if w_label else ""
            fmt_vars = {"clean_action": clean_action, "weather_cue": w_cue}

            matched_recipe = None
            for recipe in (world.fallback_recipes if world else []) or []:
                if not isinstance(recipe, dict):
                    continue
                if not _matches_keyword_rules(clean_action, recipe):
                    continue
                when_cond = recipe.get("when")
                if when_cond and not evaluate_action_condition(when_cond, session.player_state):
                    continue
                matched_recipe = recipe
                break

            if matched_recipe:
                narration, delta = self._resolve_declarative_branch(
                    matched_recipe, session.player_state, fmt_vars
                )
            elif world and isinstance(world.default_fallback, dict):
                narration, delta = self._resolve_declarative_branch(
                    world.default_fallback, session.player_state, fmt_vars
                )
            else:
                narration = (
                    f"你在当前环境中谨慎地尝试【{clean_action}】。\n\n"
                    f"虽然并未立即触发预设机关或质变，但这番探寻让你对周遭的局势有了更清晰的把握。"
                )
                delta = {"time_cost": 1} if "time_slot" in p_vars else {}

        if (delta.get("time_cost") or 0) > 0:
            w_label = str((session.player_state.variables or {}).get("weather") or "")
            w_type = str((session.player_state.variables or {}).get("weather_type") or "")
            w_slot = str((session.player_state.variables or {}).get("time_slot") or "")
            if w_label and w_label not in narration:
                w_cue = get_weather_narrative_cue(w_label, w_type, w_slot)
                if w_cue not in narration:
                    narration = f"{narration}\n\n【气象实况 · {w_label}】{w_cue}"

        formatted = f"{narration}\n\n```state_delta\n{json.dumps(delta, ensure_ascii=False, indent=2)}\n```\n"
        return formatted, delta

    def _match_freeform_action(
        self,
        scene: Optional[SceneNode],
        user_text: str,
        player_state: PlayerState,
        world: Optional[WorldSpec] = None,
    ) -> tuple[Optional[ActionOption], bool]:
        """Match free-form player text to an eligible scene action via declarative rules and keywords.

        Returns (matched_action, is_exact_label_match).
        """
        if not scene or not scene.actions:
            return None, False

        clean_input = re.sub(r"^【.*?】", "", user_text).strip()
        clean_input = re.sub(r"\[检定数据:.*?\]", "", clean_input).strip()
        if not clean_input:
            return None, False

        eligible_actions = [
            a for a in scene.actions if evaluate_action_condition(a.condition, player_state)
        ]
        if not eligible_actions:
            return None, False

        # 1. Exact or full-label match
        for a in eligible_actions:
            if clean_input == a.label or a.label in clean_input:
                return a, True

        # 2. Scenario declarative freeform disambiguation rules
        resolved_world = world or self._resolve_world(getattr(player_state, "_scenario_id", ""))
        for rule in (resolved_world.freeform_rules if resolved_world else []) or []:
            if not isinstance(rule, dict):
                continue
            if not _matches_keyword_rules(clean_input, rule):
                continue
            when_cond = rule.get("when")
            if when_cond and not evaluate_action_condition(when_cond, player_state):
                continue
            if rule.get("passthrough"):
                return None, False
            target_ids = list(rule.get("target_actions") or [])
            if rule.get("target_action"):
                target_ids.insert(0, rule["target_action"])
            for target_id in target_ids:
                act = next((a for a in eligible_actions if a.id == target_id), None)
                if act:
                    return act, False
            if rule.get("exclusive"):
                return None, False

        # 3. Substring or ActionOption.keywords match across eligible actions
        for a in eligible_actions:
            if len(clean_input) >= 2 and clean_input in a.label:
                return a, False
            if a.keywords and any(kw in clean_input for kw in a.keywords):
                return a, False

        return None, False

    async def stream_play(self, input_data: RunAgentInput) -> AsyncIterator[str]:
        """Stream play mode game turn conforming to AG-UI Protocol."""
        thread_id = input_data.thread_id or str(uuid.uuid4())
        run_id = input_data.run_id or str(uuid.uuid4())
        message_id = str(uuid.uuid4())

        # Extract latest user message
        user_text = ""
        if input_data.messages:
            last_msg = input_data.messages[-1]
            if hasattr(last_msg, "content"):
                user_text = extract_message_text(last_msg.content)
            elif isinstance(last_msg, dict):
                user_text = extract_message_text(last_msg.get("content", ""))
        if not user_text:
            user_text = "[继续行动]"

        # Check forwarded props for scenario_id and optional preset action metadata
        scenario_id = "black_crow_manor"
        action_id: Optional[str] = None
        check_passed: Optional[bool] = None
        client_roll: Optional[int] = None
        client_state: Optional[Dict[str, Any]] = None
        recent_history: Optional[List[Dict[str, str]]] = None
        regenerate = False
        if input_data.forwarded_props and isinstance(input_data.forwarded_props, dict):
            scenario_id = input_data.forwarded_props.get("scenario_id", scenario_id)
            action_id = input_data.forwarded_props.get("action_id")
            client_state = input_data.forwarded_props.get("player_state")
            recent_history = input_data.forwarded_props.get("recent_history")
            regenerate = bool(input_data.forwarded_props.get("regenerate"))
            if "client_roll" in input_data.forwarded_props:
                try:
                    client_roll = int(input_data.forwarded_props.get("client_roll"))
                except (ValueError, TypeError):
                    client_roll = None
            if "check_passed" in input_data.forwarded_props:
                check_passed = bool(input_data.forwarded_props.get("check_passed"))

        if regenerate:
            # Re-run / edited re-run of the previous turn: discard everything the abandoned attempt
            # left on the server (variables, dynamic actions, history, agent conversation) so the
            # session is rebuilt purely from the client's pre-turn snapshot.
            self.sessions.pop(thread_id, None)

        session = self.get_or_create_session(thread_id, scenario_id, client_state=client_state)
        if recent_history and not session.history:
            session.history = [
                h for h in recent_history if isinstance(h, dict) and "role" in h and "content" in h
            ][-8:]
        pre_scene_id = session.player_state.current_scene
        pre_scene = self.scenario_mgr.get_scene(scenario_id, pre_scene_id) if pre_scene_id else None
        matched_action: Optional[ActionOption] = None
        explicit_action = False
        if action_id and pre_scene and pre_scene.actions:
            matched_action = next((a for a in pre_scene.actions if a.id == action_id), None)
            explicit_action = matched_action is not None
        elif not matched_action and pre_scene and pre_scene.actions:
            matched_action, explicit_action = self._match_freeform_action(
                pre_scene, user_text, session.player_state, world=session.world
            )

        eval_res: Optional[Dict[str, Any]] = None
        if matched_action and matched_action.type == "check":
            skill = matched_action.skill or "survival"
            dc = matched_action.difficulty or 10
            clean_input = re.sub(r"^【.*?】", "", user_text).strip()
            clean_input = re.sub(r"\[检定数据:.*?\]", "", clean_input).strip()
            eval_res = self.evaluate_agent_adjudication(
                skill=skill,
                base_dc=dc,
                player_state=session.player_state,
                clean_action=clean_input,
                client_roll=client_roll,
            )
            if check_passed is None:
                check_passed = eval_res["isSuccess"]

        prompt = self.build_play_prompt(session, user_text, check_eval=eval_res)

        # 1. RUN_STARTED
        yield self.encoder.encode(RunStartedEvent(run_id=run_id, thread_id=thread_id))

        # 2. TEXT_MESSAGE_START
        yield self.encoder.encode(TextMessageStartEvent(message_id=message_id, role="assistant"))

        # Stream agent output
        full_text_buffer = ""
        conv_id = session.agent_conversation_id

        async for event in self.driver.run_stream(
            prompt=prompt,
            conversation_id=conv_id,
            cwd=self.scenario_mgr.base_dir.parent,
        ):
            if event.event_type == "text_delta":
                delta = event.data.get("text", "")
                full_text_buffer += delta
                if event.data.get("conversation_id"):
                    session.agent_conversation_id = event.data["conversation_id"]

                # Yield text delta
                yield self.encoder.encode(
                    TextMessageContentEvent(message_id=message_id, delta=delta)
                )

            elif event.event_type == "tool_call_start":
                call_id = event.data.get("call_id", str(uuid.uuid4()))
                tool_name = event.data.get("tool_name", "tool")
                yield self.encoder.encode(
                    ToolCallStartEvent(tool_call_id=call_id, tool_call_name=tool_name)
                )

            elif event.event_type == "tool_call_end":
                call_id = event.data.get("call_id", str(uuid.uuid4()))
                yield self.encoder.encode(
                    ToolCallEndEvent(tool_call_id=call_id)
                )

            elif event.event_type == "done":
                if event.data.get("conversation_id"):
                    session.agent_conversation_id = event.data["conversation_id"]

        delta_dict: Dict[str, Any] = {}
        used_fallback = False

        # If driver emitted empty text (credits 0, rate-limit, offline), activate Fallback SLG Director
        if not full_text_buffer.strip():
            used_fallback = True
            fallback_text, fallback_delta = self.generate_fallback_turn(
                session=session,
                user_text=user_text,
                matched_action=matched_action,
                check_passed=check_passed,
                current_scene=pre_scene,
                client_roll=client_roll,
            )
            delta_dict = fallback_delta
            # Stream fallback narrative chunk by chunk
            chunk_size = 12
            for i in range(0, len(fallback_text), chunk_size):
                chunk = fallback_text[i : i + chunk_size]
                full_text_buffer += chunk
                yield self.encoder.encode(
                    TextMessageContentEvent(message_id=message_id, delta=chunk)
                )
                await asyncio.sleep(0.015)

        # 3. TEXT_MESSAGE_END
        yield self.encoder.encode(TextMessageEndEvent(message_id=message_id))

        # Parse state delta from full text buffer if present
        if not delta_dict:
            state_delta_match = re.search(
                r"```state_delta\s*(\{.*?\})\s*```", full_text_buffer, re.DOTALL
            )
            if state_delta_match:
                try:
                    parsed = json.loads(state_delta_match.group(1))
                    if isinstance(parsed, dict):
                        delta_dict = parsed
                except Exception:
                    delta_dict = {}

        if matched_action is not None and (explicit_action or used_fallback or not delta_dict):
            delta_dict = self._merge_action_effects(
                delta_dict, matched_action, check_passed, session.player_state
            )

        next_scene_id = delta_dict.get("current_scene")
        if next_scene_id and next_scene_id != pre_scene_id:
            target_scene_obj = self.scenario_mgr.get_scene(session.scenario_id, next_scene_id)
            if target_scene_obj and isinstance(delta_dict.get("visuals"), dict):
                pre_bg = (
                    pre_scene.background
                    or (pre_scene.visuals.background if pre_scene.visuals else "")
                ) if pre_scene else ""
                target_bg = target_scene_obj.background or (
                    target_scene_obj.visuals.background if target_scene_obj.visuals else ""
                )
                target_fg = target_scene_obj.foreground or (
                    target_scene_obj.visuals.foreground if target_scene_obj.visuals else ""
                )
                target_hero = target_scene_obj.hero_image or (
                    target_scene_obj.visuals.hero_image if target_scene_obj.visuals else ""
                )
                target_atmo = (
                    target_scene_obj.visuals.atmosphere if target_scene_obj.visuals else ""
                )
                vis = dict(delta_dict["visuals"])
                if not vis.get("background") or (
                    pre_bg and target_bg and vis.get("background") == pre_bg and target_bg != pre_bg
                ):
                    vis["background"] = target_bg
                if "foreground" not in vis:
                    vis["foreground"] = target_fg
                if "hero_image" not in vis:
                    vis["hero_image"] = target_hero
                if "atmosphere" not in vis and target_atmo:
                    vis["atmosphere"] = target_atmo
                vis.pop("decorations", None)
                delta_dict["visuals"] = vis

        if eval_res and "check_result" not in delta_dict:
            delta_dict["check_result"] = eval_res

        clean_narrator_text = re.sub(r"```state_delta[\s\S]*?```", "", full_text_buffer).strip()
        session.history.append({"role": "user", "content": user_text})
        if clean_narrator_text:
            session.history.append({"role": "assistant", "content": clean_narrator_text[:400]})
        if len(session.history) > 12:
            session.history = session.history[-12:]

        patches: List[Dict[str, Any]] = []
        if delta_dict:
            patches = session.apply_delta(delta_dict)
        elif getattr(session, "inventory_synced", False) or getattr(session, "skills_synced", False):
            patches = session.apply_delta({})

        if _hydrate_class_skills(self.scenario_mgr, session.scenario_id, session.player_state):
            session.skills_synced = True

        if getattr(session, "inventory_synced", False):
            session.inventory_synced = False
            if not any(p.get("path") == "/inventory" for p in patches):
                patches.append({
                    "op": "replace",
                    "path": "/inventory",
                    "value": list(session.player_state.inventory),
                })

        if getattr(session, "skills_synced", False):
            session.skills_synced = False
            if not any(p.get("path") == "/skills" for p in patches):
                patches.append({
                    "op": "replace",
                    "path": "/skills",
                    "value": list(session.player_state.skills),
                })

        if patches:
            curr_scene_after = self.scenario_mgr.get_scene(
                session.scenario_id, session.player_state.current_scene
            )
            if any(p.get("path") == "/variables/weather" for p in patches) and not any(
                p.get("path") == "/visuals" for p in patches
            ):
                base_atmo = (
                    curr_scene_after.visuals.atmosphere
                    if (curr_scene_after and curr_scene_after.visuals and curr_scene_after.visuals.atmosphere)
                    else ""
                )
                w_label = str(session.player_state.variables.get("weather") or "")
                w_type = str(session.player_state.variables.get("weather_type") or "")
                w_slot = str(session.player_state.variables.get("time_slot") or "")
                w_atmo = get_weather_atmosphere(w_label, w_type, w_slot)
                live_atmo = f"{base_atmo} · {w_atmo}" if base_atmo else w_atmo
                patches.append(
                    {
                        "op": "replace",
                        "path": "/visuals",
                        "value": {"atmosphere": live_atmo},
                    }
                )
            resolved_actions = resolve_scene_actions(
                curr_scene_after, session.player_state, session.dynamic_actions
            )
            patches.append(
                {
                    "op": "replace",
                    "path": "/available_actions",
                    "value": [a.model_dump() for a in resolved_actions],
                }
            )
            yield self.encoder.encode(StateDeltaEvent(delta=patches))

        # 4. RUN_FINISHED
        yield self.encoder.encode(RunFinishedEvent(run_id=run_id, thread_id=thread_id))

    async def stream_studio(self, input_data: RunAgentInput) -> AsyncIterator[str]:
        """Stream studio mode co-pilot turn conforming to AG-UI Protocol."""
        thread_id = input_data.thread_id or str(uuid.uuid4())
        run_id = input_data.run_id or str(uuid.uuid4())
        message_id = str(uuid.uuid4())

        user_text = ""
        if input_data.messages:
            last_msg = input_data.messages[-1]
            if hasattr(last_msg, "content"):
                user_text = extract_message_text(last_msg.content)
            elif isinstance(last_msg, dict):
                user_text = extract_message_text(last_msg.get("content", ""))

        full_studio_response = ""
        scenario_id = "black_crow_manor"
        if input_data.forwarded_props and isinstance(input_data.forwarded_props, dict):
            scenario_id = input_data.forwarded_props.get("scenario_id", scenario_id)

        prompt = f"""你是一名专业的游戏剧本设计与视觉导演协作者（AG-SLG Studio Co-pilot，遵循 ag-slg-director 视觉分层规范）。
当前剧本资产目录位于当前工作区的 scripts/{scenario_id}/ 下。
用户创作需求：{user_text}

【核心红线约束 — 严禁修改框架代码】：
1. 你的工作范围**仅限**当前剧本目录 `scripts/{scenario_id}/`（包括 `world.yaml`、`scenes/*.yaml`）及对应静态美术资源。
2. **绝对禁止**修改、覆盖或重构任何框架引擎代码（包括但不限于 `server/`、`web/`、`tests/`、`run_services.py`、`pyproject.toml`），除非用户在本次对话中明确要求你排查并修复框架本身的 Bug！
3. 如果剧本需要专属状态栏、Boss/遭遇面板、阶段追踪器、专属数值上下限、战斗公式、检定修正或物品目录：
   - 请通过 `scripts/{scenario_id}/world.yaml` 的声明式字段（`dm_rules`、`item_catalog`、`attribute_bounds`、`variable_bounds`、`adjudication_rules`、`initial_player_state.hud_widgets`）配置，或直接在场景动作 `on_success`/`on_failure` 中配置 `hud_widgets` / `remove_hud_widgets`；
   - 或在游玩期引导 DM Agent 通过 AG-UI ```state_delta``` 的 `hud_widgets`（支持 `metrics` / `tracker` / `panel`）与 `remove_hud_widgets` 动态渲染与撤除界面，绝不要为了迎合单个剧本而改动引擎源码。

你可以直接输出剧本构思与建议。如果你构思了一个完整的场景节点或更新了场景，请在回复中包含如下格式的代码块，以便系统自动将其写盘生效。请务必配置完整的多图层视觉资源（background, foreground, hero_image, visuals.atmosphere）：
```scene_yaml:场景ID
id: "场景ID"
title: "场景标题"
background: "/assets/scenes/xxx.png"
hero_image: "/assets/illustrations/xxx.png"
music: "/assets/bgm/xxx.mp3"
description: |
  场景描述文本...
visuals:
  background: "/assets/scenes/xxx.png"
  foreground: ""
  hero_image: ""
  atmosphere: "幽暗密闭、阴冷"
  decorations:
    - id: "built_shelter"
      name: "防风窝棚"
      image: "/assets/props/shelter.png"
      side: "left"
      category: "structure"
      tag: "已建成"
      caption: "树枝窝棚"
      tooltip: "已建成的耐用防风庇护所"
      condition:
        variables:
          shelter_level:
            gte: 1
npcs:
  - id: "npc_id"
    name: "NPC名字"
    avatar: "/assets/characters/xxx.png"
    greeting: "开场问候语..."
actions:
  - id: "action_1"
    label: "行动名称"
    type: "transition"
    target_scene: "manor_entrance"
```
"""

        yield self.encoder.encode(RunStartedEvent(run_id=run_id, thread_id=thread_id))
        yield self.encoder.encode(TextMessageStartEvent(message_id=message_id, role="assistant"))

        event_queue: asyncio.Queue[Optional[AgentEvent]] = asyncio.Queue()

        studio_conv_id = self.studio_conversations.get(thread_id)

        async def _pump_driver() -> None:
            try:
                async for ev in self.driver.run_stream(
                    prompt=prompt,
                    conversation_id=studio_conv_id,
                    cwd=self.scenario_mgr.base_dir.parent,
                ):
                    await event_queue.put(ev)
            except Exception as exc:
                await event_queue.put(AgentEvent(event_type="error", data={"error": str(exc)}))
            finally:
                await event_queue.put(None)

        pump_task = asyncio.create_task(_pump_driver())
        driver_error: Optional[str] = None

        try:
            while True:
                try:
                    event = await asyncio.wait_for(event_queue.get(), timeout=10.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue

                if event is None:
                    break

                if event.data.get("conversation_id"):
                    self.studio_conversations[thread_id] = event.data["conversation_id"]

                if event.event_type == "text_delta":
                    delta = event.data.get("text", "")
                    full_studio_response += delta
                    yield self.encoder.encode(
                        TextMessageContentEvent(message_id=message_id, delta=delta)
                    )
                elif event.event_type == "tool_call_start":
                    call_id = event.data.get("call_id", str(uuid.uuid4()))
                    tool_name = event.data.get("tool_name", "tool")
                    yield self.encoder.encode(
                        ToolCallStartEvent(tool_call_id=call_id, tool_call_name=tool_name)
                    )
                elif event.event_type == "tool_call_end":
                    call_id = event.data.get("call_id", str(uuid.uuid4()))
                    yield self.encoder.encode(
                        ToolCallEndEvent(tool_call_id=call_id)
                    )
                elif event.event_type == "error":
                    driver_error = str(event.data.get("error") or "Studio Agent 执行异常")
        finally:
            if not pump_task.done():
                pump_task.cancel()
                try:
                    await pump_task
                except asyncio.CancelledError:
                    pass

        if not full_studio_response.strip() and driver_error:
            err_msg = f"⚠️ 编剧 Agent 执行异常：{driver_error}\n\n请检查本地 Agent 服务状态后重试。"
            full_studio_response = err_msg
            yield self.encoder.encode(
                TextMessageContentEvent(message_id=message_id, delta=err_msg)
            )

        if not full_studio_response.strip():
            fallback_response = (
                f"### AG-SLG Studio Co-pilot 编剧建议\n\n"
                f"针对您的创作需求：“{user_text}”，已自动构思并格式化对应场景节点：\n\n"
                f"```scene_yaml:secret_chamber\n"
                f"id: \"secret_chamber\"\n"
                f"title: \"隐秘密室\"\n"
                f"background: \"/assets/scenes/manor_hall.png\"\n"
                f"hero_image: \"/assets/illustrations/corridor_shadow.png\"\n"
                f"music: \"/assets/bgm/manor_ambient.mp3\"\n"
                f"description: |\n"
                f"  地窖暗门后隐藏着一间尘封已久的密室，空气中积聚着旧纸页与蜡油的气味。\n"
                f"  正中央的书桌上赫然摆放着一本摊开的泛黄日记，记录着尘封多年的家族真相。\n"
                f"visuals:\n"
                f"  background: \"/assets/scenes/manor_hall.png\"\n"
                f"  foreground: \"\"\n"
                f"  hero_image: \"/assets/illustrations/corridor_shadow.png\"\n"
                f"  atmosphere: \"压抑、隐秘、疑云密布\"\n"
                f"npcs: []\n"
                f"actions:\n"
                f"  - id: \"read_diary\"\n"
                f"    label: \"翻阅书桌上的泛黄日记\"\n"
                f"    type: \"check\"\n"
                f"    skill: \"perception\"\n"
                f"    difficulty: 9\n"
                f"```\n"
            )
            for i in range(0, len(fallback_response), 16):
                c = fallback_response[i : i + 16]
                full_studio_response += c
                yield self.encoder.encode(
                    TextMessageContentEvent(message_id=message_id, delta=c)
                )
                await asyncio.sleep(0.01)

        yield self.encoder.encode(TextMessageEndEvent(message_id=message_id))

        # 检查是否包含可以直接落盘的 scene_yaml
        import yaml
        yaml_matches = re.findall(
            r"```scene_yaml:([a-zA-Z0-9_\-]+)\s*\n([\s\S]*?)```", full_studio_response
        )
        for s_id, s_content in yaml_matches:
            try:
                data = yaml.safe_load(s_content) or {}
                if "id" not in data:
                    data["id"] = s_id
                node = SceneNode(**data)
                self.scenario_mgr.save_scene(scenario_id, node)
            except Exception:
                pass

        yield self.encoder.encode(RunFinishedEvent(run_id=run_id, thread_id=thread_id))

