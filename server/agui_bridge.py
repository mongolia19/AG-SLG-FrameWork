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
    evaluate_action_condition,
    resolve_scene_actions,
    resolve_scene_decorations,
)


TIME_SLOTS = ["清晨", "上午", "下午", "黄昏", "夜晚", "深夜"]
SURVIVAL_CLAMP_100 = {"stamina", "hydration", "fullness"}
SCENE_SCOPED_STRUCT_DEFAULTS: Dict[str, Any] = {
    "fire_started": False,
    "shelter_level": 0,
    "water_collector_built": False,
}

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
        "atmosphere": "晴空炙烤、海天一色",
        "night_atmosphere": "星光微寒、海浪低吟",
        "cue": "日光穿透云隙洒下，海天交界处一片澄明，空气中带着干爽的温热。",
        "night_cue": "夜空清澈无云，微冷的星月光洒在沙地与树梢之间。",
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
        "cue": "厚重的铅灰色云层遮住了天日，海面褪去亮色，空气潮湿闷沉，似有风雨酝酿。",
        "night_cue": "浓重的阴云遮蔽了星月，四周陷入比往常更加深沉的黑暗与闷潮。",
    },
    "windy": {
        "labels_by_slot": {
            "清晨": "海风微急",
            "上午": "海风呼啸",
            "下午": "狂风劲吹",
            "黄昏": "海风骤起",
            "夜晚": "夜风呼啸",
            "深夜": "凛冽狂风",
        },
        "atmosphere": "狂风呼啸、林叶翻飞",
        "night_atmosphere": "夜风凛冽、涛声怒吼",
        "cue": "劲急的海风卷着咸涩水汽迎面刮来，椰林与灌木剧烈摇晃，沙尘与落叶随风翻飞。",
        "night_cue": "凛冽的夜风在林间与礁石缝隙中呜咽穿行，气温随之明显下降。",
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
        "cue": "细密的雨点敲打着阔叶与沙面，带来久违的清凉水汽，也让人衣衫渐湿。",
        "night_cue": "冰凉的夜雨淅沥落下，周围草木湿滑，空气中寒意加重。",
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
        "night_atmosphere": "雷暴交加、黑浪翻涌",
        "cue": "狂风裹挟着豆大的雨点倾盆而下，远处海面雷声滚滚，能见度骤降，寒意透骨。",
        "night_cue": "电闪雷鸣撕裂夜幕，狂风暴雨猛烈拍打着岛屿，露天火源与体温都面临严峻考验。",
    },
    "foggy": {
        "labels_by_slot": {
            "清晨": "海雾微凉",
            "上午": "薄雾未散",
            "下午": "海雾弥漫",
            "黄昏": "暮雾沉沉",
            "夜晚": "夜雾笼罩",
            "深夜": "浓雾深重",
        },
        "atmosphere": "海雾弥漫、视野朦胧",
        "night_atmosphere": "浓雾锁岛、幽暗迷离",
        "cue": "乳白色的潮湿海雾贴着地面与海面缓缓流淌，十步之外的轮廓都变得朦胧。",
        "night_cue": "浓重的夜雾吞没了远处的海岸与密林，水汽凝结在衣领与眉梢。",
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

    # Prevent getting stuck in the exact same weather type for too many consecutive turns
    if duration >= 2:
        filtered = [(w, p) for w, p in candidates if w != cur_type]
        if filtered:
            candidates = filtered

    # Fog is most common around dawn/deep night
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


def _clamp_attr(key: str, value: int) -> int:
    if key in SURVIVAL_CLAMP_100:
        return max(0, min(100, value))
    if key == "temperature":
        return max(30, min(42, value))
    return value


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


ITEM_META = {
    "metal_box": {
        "name": "防水金属盒",
        "icon": "",
        "desc": "从沙滩拾获并洗净的航空铝合金防水盒，密封严密，既可收纳物资也可充当容器盛水烧水。",
    },
    "lighter": {
        "name": "防风打火机",
        "icon": "/assets/items/lighter.png",
        "desc": "军用级防水防风打火机，火花稳定，求生核心火源。",
    },
    "rope": {
        "name": "坚韧纤维绳",
        "icon": "/assets/items/rope.png",
        "desc": "坚韧老藤与树皮编织的耐磨绳索，可用于捆绑、攀爬与搭建。",
    },
    "glass_bottle": {
        "name": "厚壁玻璃瓶",
        "icon": "/assets/items/glass_bottle.png",
        "desc": "透明厚壁玻璃瓶，配有密封塞，可用于储水与煮水。",
    },
    "branches": {
        "name": "干燥树枝浮木",
        "icon": "/assets/items/branches.png",
        "desc": "经日晒干燥的坚硬树枝，是生火引火与制作工具的素材。",
    },
    "fresh_water_bottle": {
        "name": "装满甘泉的玻璃瓶",
        "icon": "/assets/items/glass_bottle.png",
        "desc": "装满了来自丛林深处的纯净泉水，饮用可补充大量水分。",
    },
    "wild_food": {
        "name": "野生热带坚果",
        "icon": "/assets/items/branches.png",
        "desc": "富含油脂与热量的饱满坚果与棕榈芯，可直接食用或烤熟充饥。",
    },
    "raw_crab": {
        "name": "鲜活礁石海蟹",
        "icon": "/assets/props/crab.png",
        "desc": "刚抓获的肥硕海蟹，生吃有腹泻风险，在篝火上烤熟味道极佳。",
    },
    "seashell": {
        "name": "坚硬海螺与贝壳",
        "icon": "/assets/props/seashell.png",
        "desc": "在沙滩拾取的厚壳海螺，边缘锋利，螺肉可食用，外壳可用于挖掘与盛水。",
    },
    "vines": {
        "name": "野生韧皮藤蔓",
        "icon": "/assets/props/vines.png",
        "desc": "从丛林灌木中割取的柔韧藤蔓，是编织绳索与固定遮蔽所的基础耗材。",
    },
    "driftwood": {
        "name": "干燥海滩浮木",
        "icon": "/assets/items/branches.png",
        "desc": "被海浪冲上岸经太阳炙烤干燥的浮木枝干，是极好的引火木料与营地建材。",
    },
    "coconut": {
        "name": "新鲜青椰",
        "icon": "/assets/props/palmtree.png",
        "desc": "沉甸甸的热带青椰，同时富含清甜椰汁与饱腹椰肉。",
    },
    "cooked_food": {
        "name": "炭烤海鲜与坚果拼盘",
        "icon": "/assets/items/branches.png",
        "desc": "散发出诱人焦香的熟食，能大幅恢复饱食度与体力。",
    },
    "torn_linen_shirt": {
        "name": "撕裂的白色亚麻衬衫",
        "desc": "迫降时被海水浸湿又在烈日下微干的机舱休闲衬衫，袖口略有撕裂。",
        "tag": "微湿 · 轻便",
    },
    "khaki_cargo_pants": {
        "name": "卡其色速干长裤",
        "desc": "耐磨的多口袋工装长裤，裤脚沾满细沙，能阻挡灌木枝刺刮伤。",
        "tag": "耐磨 · 下装",
    },
    "sandy_sneakers": {
        "name": "沾沙的运动跑鞋",
        "desc": "鞋底厚实防滑，能保护双脚不在尖锐礁石与碎珊瑚上割伤。",
        "tag": "防滑 · 鞋履",
    },
    "broken_watch": {
        "name": "停摆的机械腕表",
        "desc": "表盘玻璃在撞击时裂开了一道细纹，指针停在凌晨 3:14，金属表壳可反射阳光求救。",
        "tag": "腕饰 · 可反光",
    },
    "pilot_windbreaker": {
        "name": "失事机长防风夹克",
        "desc": "在残骸附近搜获的橙灰拼色高可视度防风外套，防风防泼水，夜间保暖极佳。",
        "tag": "防风保暖 · 外套",
    },
    "palm_sunhat": {
        "name": "椰叶编织遮阳帽",
        "desc": "宽大椰叶与韧藤编织而成的轻便草帽，有效遮挡毒辣烈日，减缓水分流失。",
        "tag": "遮阳防晒 · 头饰",
    },
    "shell_necklace": {
        "name": "潮汐贝壳挂坠",
        "desc": "用坚硬五彩海贝与韧皮细绳串起的颈间护符，海风吹过时发出清脆声响，令人心神宁静。",
        "tag": "安神 · 颈饰",
    },
    # 艾泽拉斯传说（wow_elwynn_rpg）常用物品与掉落
    "炉石": {
        "name": "炉石（北郡修道院）",
        "icon": "/assets/items/hearthstone.png",
        "desc": "刻有温暖蓝白符文的魔法石，将灵魂绑定在北郡修道院的旅店炉火旁。",
    },
    "初级治疗药水": {
        "name": "初级治疗药水",
        "icon": "/assets/items/minor_healing_potion.png",
        "desc": "暴风城炼金师配制的红色恢复药瓶，紧急时刻饮下可快速愈合伤势。",
    },
    "北郡军令状": {
        "name": "北郡军令状",
        "icon": "/assets/items/northshire_order.png",
        "desc": "盖有暴风城赤红雄狮火漆印的军务羊皮卷轴，委任你清剿法戈第矿洞蛛灾。",
    },
    "狗头人蜡烛碎块": {
        "name": "狗头人蜡烛碎块",
        "icon": "/assets/items/kobold_candle.png",
        "desc": "从北郡外围狗头人斥候身上缴获的融蜡残烛，隐约散发着微弱暖光。",
    },
    "照明信号箭": {
        "name": "照明信号箭",
        "icon": "/assets/items/flare_arrow.png",
        "desc": "巡林者艾莲娜特制的炼金信号箭，射出后能瞬间点燃并照亮幽暗矿洞。",
    },
    "优质狼皮": {
        "name": "优质狼皮",
        "icon": "/assets/items/wolf_pelt.png",
        "desc": "厚实完整的艾尔文森林灰狼毛皮，可作护具内衬或交由工匠换取金币。",
    },
    "银叶解毒草": {
        "name": "银叶解毒草",
        "icon": "/assets/items/silverleaf_herb.png",
        "desc": "在艾尔文林间采摘的银边解毒药草，是调配矿洞抗毒合剂的核心原料。",
    },
    "抗毒合剂": {
        "name": "抗毒合剂",
        "icon": "/assets/items/antidote_elixir.png",
        "desc": "以银叶草熬制的碧绿澄澈合剂，饮用后可抵御法戈第矿洞中的腐败蛛毒。",
    },
    "幽暗蛛王丝": {
        "name": "幽暗蛛王丝",
        "icon": "/assets/items/spider_silk.png",
        "desc": "闪烁着紫银微光的蜘蛛领主珍稀丝线，刀剑难断，乃编织英雄披风的上等材料。",
    },
    "纯净毒囊结晶": {
        "name": "纯净毒囊结晶",
        "icon": "/assets/items/venom_crystal.png",
        "desc": "从蜘蛛领主·阿拉克诺斯毒腺中提取的高纯度结晶，蕴含冰蓝与紫曜魔力。",
    },
    "暗牙护符": {
        "name": "阿拉克诺斯暗牙护符",
        "icon": "/assets/items/fang_charm.png",
        "desc": "用蜘蛛领主最坚硬的一对主螯牙雕琢而成的稀有颈饰，隐隐散发威压。",
        "tag": "Boss 稀有掉落 · 颈饰",
    },
    "arachnos_fang_charm": {
        "name": "阿拉克诺斯暗牙护符",
        "icon": "/assets/items/fang_charm.png",
        "desc": "用蜘蛛领主最坚硬的一对主螯牙雕琢而成的稀有颈饰，隐隐散发威压。",
        "tag": "Boss 稀有掉落 · 颈饰",
    },
}


def _enrich_item_meta(raw_item: Any) -> Dict[str, Any]:
    """Normalize an inventory or outfit item dict and enrich missing fields from ITEM_META."""
    item = dict(raw_item) if isinstance(raw_item, dict) else {"id": str(raw_item), "name": str(raw_item)}
    item_id = item.get("id", "")
    if item_id in ITEM_META:
        meta = ITEM_META[item_id]
        if not item.get("name") or item["name"] == item_id:
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


class GameSession:
    """In-memory game session tracking player state and Agent conversation ID."""

    def __init__(self, session_id: str, scenario_id: str, initial_state: PlayerState):
        self.session_id = session_id
        self.scenario_id = scenario_id
        self.player_state = initial_state
        self.agent_conversation_id: Optional[str] = None
        self.history: List[Dict[str, str]] = []
        self.dynamic_actions: List[Dict[str, Any]] = []
        self.inventory_synced: bool = False
        self.skills_synced: bool = False

    def apply_delta(self, delta: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Apply state delta and return standard JSON-patch like delta list."""
        patches: List[Dict[str, Any]] = []
        prev_scene = self.player_state.current_scene

        if "current_scene" in delta and delta["current_scene"]:
            new_scene = delta["current_scene"]
            self.player_state.current_scene = new_scene
            if new_scene != prev_scene and "available_actions" not in delta:
                self.dynamic_actions = []
            patches.append({"op": "replace", "path": "/current_scene", "value": new_scene})
            if new_scene != prev_scene:
                for base_key, default_val in SCENE_SCOPED_STRUCT_DEFAULTS.items():
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

        if "hp" in delta:
            self.player_state.hp = max(0, min(100, int(delta["hp"])))
            patches.append({"op": "replace", "path": "/hp", "value": self.player_state.hp})
        elif "hp_delta" in delta:
            self.player_state.hp = max(0, min(100, self.player_state.hp + int(delta["hp_delta"])))
            patches.append({"op": "replace", "path": "/hp", "value": self.player_state.hp})

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
                if active_scene and k in SCENE_SCOPED_STRUCT_DEFAULTS:
                    scoped_key = f"{active_scene}_{k}"
                    if scoped_key not in delta_vars:
                        self.player_state.variables[scoped_key] = v
                        patches.append({"op": "add", "path": f"/variables/{scoped_key}", "value": v})
                elif active_scene:
                    for base_key in SCENE_SCOPED_STRUCT_DEFAULTS:
                        if k == f"{active_scene}_{base_key}" and base_key not in delta_vars:
                            self.player_state.variables[base_key] = v
                            patches.append({"op": "add", "path": f"/variables/{base_key}", "value": v})
            if "weather" in delta_vars and "weather_type" not in delta_vars:
                inferred_type = classify_weather_type(str(delta_vars["weather"]))
                self.player_state.variables["weather_type"] = inferred_type
                self.player_state.variables["weather_duration"] = 1
                patches.append({"op": "add", "path": "/variables/weather_type", "value": inferred_type})
                patches.append({"op": "add", "path": "/variables/weather_duration", "value": 1})

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

                # Dynamically advance weather (clear / cloudy / windy / rain / storm / foggy)
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
                new_val = _clamp_attr(k, curr_val + int(v))
                self.player_state.attributes[k] = new_val
                attr_updates[k] = new_val

        if "attributes" in delta and isinstance(delta["attributes"], dict):
            for k, v in delta["attributes"].items():
                new_val = _clamp_attr(k, int(v))
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
            unique_tools = {"lighter", "metal_box", "stone_blade", "rope"}
            for raw_item in delta["add_inventory"]:
                item = _enrich_item_meta(raw_item)
                item_id = item.get("id")
                if item_id in unique_tools and item_id in existing_ids:
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
                    self.player_state.outfit[slot] = _enrich_item_meta(raw_piece)
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

    @staticmethod
    def _sync_player_state(target: PlayerState, source: Dict[str, Any]) -> bool:
        """Sync runtime player state from client to prevent server restart desync.

        Returns True if inventory was deduplicated or updated.
        """
        if not isinstance(source, dict):
            return False

        if "current_scene" in source and source["current_scene"]:
            target.current_scene = source["current_scene"]
        if "hp" in source and isinstance(source["hp"], (int, float)):
            target.hp = int(source["hp"])
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
                k: _enrich_item_meta(v)
                for k, v in source["outfit"].items()
                if isinstance(v, dict)
            }
        if "skills" in source and isinstance(source["skills"], list):
            target.skills = [
                _enrich_skill_meta(s)
                for s in source["skills"]
                if isinstance(s, (dict, str))
            ]

        inv_changed = False
        if "inventory" in source and isinstance(source["inventory"], list):
            deduped_inv = []
            seen_unique = set()
            unique_tools = {"lighter", "metal_box", "stone_blade", "rope"}
            for raw_item in source["inventory"]:
                if isinstance(raw_item, dict):
                    item = _enrich_item_meta(raw_item)
                    item_id = item.get("id")
                    if item_id in unique_tools:
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
            if client_state:
                if self._sync_player_state(session.player_state, client_state):
                    session.inventory_synced = True
            if _hydrate_class_skills(self.scenario_mgr, session.scenario_id, session.player_state):
                session.skills_synced = True
            return session

        spec = self.scenario_mgr.load_scenario(scenario_id)
        # Deep copy initial player state
        init_state = PlayerState(**spec.world.initial_player_state.model_dump())
        inv_synced = False
        if client_state:
            inv_synced = self._sync_player_state(init_state, client_state)
        skills_synced = _hydrate_class_skills(self.scenario_mgr, scenario_id, init_state)

        session = GameSession(thread_id, scenario_id, init_state)
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

        prompt = f"""你是一款高沉浸感文字跑团（TRPG / SLG）的地下城主（DM / Game Master）兼视觉导演（遵循 ag-slg-director 规范）。
当前世界观：{scenario.world.title} (ID: {scenario.world.id})
玩家当前状态：
- 角色名：{session.player_state.name}
- HP：{session.player_state.hp} / SAN：{session.player_state.san} / 金币：{session.player_state.gold}
- 生存与角色属性：{session.player_state.attributes}
- 背包物品：{inv_desc or '空'}
- 当前穿着与配饰：{outfit_desc or '常规随身衣物'}
- 技能栏：{skills_desc or '尚未习得特殊技能'}
- 剧本变量（含时间/昼夜/气象/进度）：{session.player_state.variables}
- 当前气象与环境基调：{cur_weather or '未设定'}（氛围：{scene_atmo}）
- 当前所在场景：{curr_scene.title if curr_scene else curr_scene_id} ({curr_scene_id})

当前场景预设视觉资源：
- 场景底图 (Background): {scene_bg or '默认空间背景'}
- 焦点插图 (Hero Image): {scene_hero or '无'}
- 前景立绘 (Foreground): {scene_fg or '无'}
- 环境氛围 (Atmosphere): {scene_atmo}
- 左右侧图像区已建成耐用设施 (Built Camp Structures): {built_structs or '暂无'}

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
   - 仔细分辨玩家输入的具体动词与目标，严格按玩家当前行动的字面意图推进，切勿强行套用无关的预设选项结局！
   - 例如：若玩家自由输入“捡起防水金属盒，洗干净带走”，其目的是**获得并随身携带金属盒本身**，必须如实描写捡起并清洗金属盒，并在 `add_inventory` 中加入 `metal_box`（防水金属盒），绝不要在玩家未要求打开/搜查盒内物品时擅自改为“在盒里翻找打火机”。
   - 凡玩家明确拾取、清洗带走、制作或获得的实体物品，都必须在 `state_delta.add_inventory` 中准确写入物品（包含 `id`、`name`、`desc`），确保背包栏真实同步。
   - **打火机与生火/烹饪的真实意图响应（绝对红线）**：若玩家明确输入使用打火机（lighter）点火、生火、引燃甘草或枯枝、搭建火堆或进行烹饪煮食，且玩家背包中已拥有打火机（id: lighter）：
     ① 必须承认打火机是现成的核心火源！严禁无视玩家背包内的打火机，严禁谎称“没有火源”或无端判定点火失败！
     ② 必须成功点燃火焰：在 state_delta.variables 中明确写入 `"fire_started": true`，并在 visuals.hero_image 给出篝火特写插图 `/assets/illustrations/campfire.png`。
     ③ 若玩家同时进行了煮食物/烤食物：只要背包中有可烹饪物品（如 raw_crab、wild_food、coconut、fresh_water 等），必须在叙述中生动描绘火烤烹饪与熟食香气，在 state_delta.remove_inventory 中扣除对应食材，并通过 attributes_delta 大幅增加饱食度（fullness: +30~+40）与体力（stamina: +15~+25）！
2. DM 综合裁决与灵活判定法则（代入感与策略性核心）：
   - 杜绝生硬机械的二元通过/失败，全面综合玩家的【属性点】+【穿戴装备与衣物】+【随身工具道具】+【生理体能状况】给出多维裁决修正；
   - 采用 TRPG 四阶递进式裁决深度演化剧情：
     · 卓越成功 (Critical Success, Total >= DC + 5 或 Nat 20)：游刃有余、精妙达成，不仅达成全部目标，还可节省精力或获得额外顿悟；
     · 顺利达成 (Success, DC <= Total < DC + 5)：稳扎稳打达成目标，消耗标准资源；
     · 代价成功 (Partial Success, DC - 3 <= Total < DC)：虽遇险阻但凭借装备支撑或顽强毅力达成了核心目标，付出额外体力或产生次要代价；
     · 受挫转折 (Failure with Momentum, Total < DC - 3 或 Nat 1)：环境险恶行动受阻，但绝不卡死故事，转化为新的局势信息或避险转折，引导玩家调整策略。
   - 若本次行动包含检定，请在回复末尾的 ```state_delta``` 中附带 `check_result` 字段记录裁决明细。
3. 叙事文本与对话分明：生动叙述环境与行动结果，NPC 发言请以 角色名: “对话内容” 格式清晰表达。严禁在叙述文本中直接泄漏具体图片文件路径。
4. 视觉舞台导演原则（ag-slg-director）：
   - 背景稳定性：不要在普通的对话轮换背景；仅在发生场景转移或环境巨变时更新 visuals.background。
   - 角色立绘调度：与具体 NPC 对话时，设置 visuals.foreground 为其立绘；玩家独处检定或离开时置空。
   - 焦点特写镜头：当玩家成功发现关键线索、拾获或搜查物品、或遭遇高潮事件时，在 visuals.hero_image 给出特写插图路径或语义描述（如“【物品特写】洗净泥沙的防水金属盒”）。
   - 左右侧耐用设施展示：当玩家在生存中建成耐用物品（如窝棚、篝火火堆、雨水收集器），务必在 `state_delta.variables` 中设置当前场景对应的状态标识（或 `shelter_level` / `fire_started` / `water_collector_built`）；若建成了额外自定义耐用设施，可通过 `state_delta.add_structures`（含 `id`, `name`, `image`, `side: "left"|"right"`, `caption`, `tooltip`, `scene_id`）使其展示在当前场景的左右两侧图像区。
   - **场景隔离原则（严禁跨场景带出）**：当玩家离开当前场景前往新场景（`current_scene` 变更）时，必须同步更新 `visuals.background` 为目标场景底图，清空原场景的临时立绘与特写（将 `visuals.foreground` 与 `visuals.hero_image` 置空 `""` 或设为新场景自身资源），且**绝不可**将原场景建成的设施（如原场景的窝棚、篝火、雨水收集器等）带入新场景！每个场景的已建设施仅归属其建造所在场景。
5. 数值与动态选项演算（非常重要）：
   - 若玩家进食、饮水、休息、劳作或受环境影响，务必在 state_delta 中通过 `attributes_delta` 真实更新对应属性（如 `fullness` 饱食度、`hydration` 水分、`stamina` 体力、`temperature` 体温），消耗掉的食材/饮水通过 `remove_inventory` 列出道具 id 移除。
   - 行动耗时可通过 `time_cost`（整数，如 1 表示推进一个时段：清晨→上午→下午→黄昏→夜晚→深夜）推进时间；系统也会随时间推进自然演替阴天、晴朗、刮风、阵雨、暴雨、海雾等天气变化，你也可根据剧情在 `variables.weather` 主动触发天气转折（如骤起狂风或突降暴雨），并在叙述与 `visuals.atmosphere` 中生动展现风雨冷暖与防风夹克/遮阳帽/窝棚/岩洞带来的真实影响。
   - 如因剧情变化衍生出新的临时行动选项，可通过 `available_actions` 提供动态选项列表；预设场景选项也会随状态、时间与天气自动刷新。
6. 若产生场景转移、数值变化、道具增减、时间推进或视觉变更，在回复最末尾附带一个 ```state_delta 代码块：
```state_delta
{{
  "current_scene": "目标场景ID（若发生转移）",
  "hp_delta": 0,
  "san_delta": 0,
  "attributes_delta": {{"fullness": 25, "stamina": 10}},
  "time_cost": 1,
  "add_inventory": [{{"id": "item_id", "name": "道具名", "desc": "描述"}}],
  "remove_inventory": ["consumed_item_id"],
  "outfit": {{"outer": {{"id": "jacket_id", "name": "穿戴服装名", "desc": "描述", "tag": "状态/加成"}}}},
  "learn_skills": [{{"id": "skill_id", "name": "技能名称", "desc": "技能简介", "effect": "具体作用说明与效果", "cost": "消耗", "cooldown": "冷却", "level": 1, "tag": "类型"}}],
  "variables": {{"variable_key": "variable_value"}},
  "check_result": {{
    "skill": "survival",
    "difficulty": 10,
    "roll": 12,
    "modifier": 3,
    "total": 15,
    "isSuccess": true,
    "outcome": "success",
    "outcome_label": "顺利达成",
    "reason": "基础属性(+1)、防风外套(+2)",
    "message": "成功克服恶劣海风影响"
  }},
  "available_actions": [
    {{"id": "dynamic_act_1", "label": "新的情境行动", "type": "interact"}}
  ],
  "visuals": {{
    "background": "{scene_bg}",
    "foreground": "/assets/characters/xxx.png",
    "hero_image": "/assets/illustrations/xxx.png 或 语义特写标签",
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

        # HP / SAN delta
        if "hp_delta" in outcome and "hp" not in merged and "hp_delta" not in merged:
            merged["hp_delta"] = outcome["hp_delta"]
        if "san_delta" in outcome and "san" not in merged and "san_delta" not in merged:
            merged["san_delta"] = outcome["san_delta"]

        # Variables
        if isinstance(outcome.get("variables"), dict):
            vars_dict = dict(merged.get("variables") or {})
            for k, v in outcome["variables"].items():
                if k not in vars_dict:
                    vars_dict[k] = v
            if vars_dict:
                merged["variables"] = vars_dict

        # Time cost
        if outcome.get("time_cost") and "time_cost" not in merged:
            merged["time_cost"] = outcome["time_cost"]

        return merged

    @staticmethod
    def evaluate_agent_adjudication(
        skill: str,
        base_dc: int,
        player_state: PlayerState,
        clean_action: str,
        client_roll: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Comprehensively evaluate action check based on player attributes, outfit, tools, and stamina."""
        import random
        roll = client_roll if (client_roll is not None and 1 <= client_roll <= 20) else random.randint(1, 20)

        # 1. Attribute modifier
        attr_val = int(player_state.attributes.get(skill, 10) or 10)
        attr_mod = (attr_val - 10) // 2

        # 2. Outfit & clothing bonuses
        outfit_mod = 0
        outfit_reasons = []
        outfit = player_state.outfit or {}
        if outfit.get("outer"):
            outfit_mod += 2
            outfit_reasons.append(f"{outfit['outer'].get('name', '防风外套')}(+2)")
        if outfit.get("shoes") and skill in ("agility", "survival"):
            outfit_mod += 1
            outfit_reasons.append(f"{outfit['shoes'].get('name', '防滑跑鞋')}(+1)")
        if outfit.get("wrist") and skill in ("perception", "survival"):
            outfit_mod += 1
            outfit_reasons.append(f"{outfit['wrist'].get('name', '反光腕表')}(+1)")
        if outfit.get("neck"):
            outfit_mod += 1
            outfit_reasons.append(f"{outfit['neck'].get('name', '潮汐护符')}(+1)")

        # 3. Tool bonuses
        tool_mod = 0
        tool_reasons = []
        inv_ids = {
            item.get("id", "") for item in (player_state.inventory or []) if isinstance(item, dict)
        }
        if "stone_blade" in inv_ids and any(k in clean_action for k in ("割", "切", "削", "剥", "撬", "磨", "修")):
            tool_mod += 2
            tool_reasons.append("石刀精制(+2)")
        if "lighter" in inv_ids and any(k in clean_action for k in ("火", "点", "燃", "烧")):
            tool_mod += 3
            tool_reasons.append("防风打火机(+3)")
        if "rope" in inv_ids and any(k in clean_action for k in ("捆", "扎", "绑", "绳", "编", "爬", "攀")):
            tool_mod += 2
            tool_reasons.append("坚韧绳索(+2)")
        if "metal_box" in inv_ids and any(k in clean_action for k in ("水", "煮", "装", "存", "盒")):
            tool_mod += 1
            tool_reasons.append("防水金属盒(+1)")
        variables = player_state.variables or {}
        curr_scene = player_state.current_scene or ""
        shelter_val = variables.get(f"{curr_scene}_shelter_level") if curr_scene and f"{curr_scene}_shelter_level" in variables else variables.get("shelter_level", 0)
        fire_val = variables.get(f"{curr_scene}_fire_started") if curr_scene and f"{curr_scene}_fire_started" in variables else variables.get("fire_started")

        if (shelter_val or 0) >= 1 and any(
            k in clean_action for k in ("休息", "睡", "过夜", "庇护", "窝棚", "躲", "避雨")
        ):
            tool_mod += 2
            tool_reasons.append("稳固防风窝棚(+2)")
        if fire_val and any(
            k in clean_action for k in ("夜", "寒", "烤", "煮", "火", "守夜")
        ):
            tool_mod += 1
            tool_reasons.append("温暖营地篝火(+1)")

        # 4. Physical condition penalties/bonuses
        cond_mod = 0
        cond_reasons = []
        stamina = int(player_state.attributes.get("stamina", 50) or 50)
        hydration = int(player_state.attributes.get("hydration", 50) or 50)
        fullness = int(player_state.attributes.get("fullness", 50) or 50)

        if stamina >= 75 and hydration >= 60 and fullness >= 50:
            cond_mod += 1
            cond_reasons.append("体能充沛(+1)")
        elif stamina < 30:
            cond_mod -= 2
            cond_reasons.append("体力透支(-2)")
        if hydration < 25:
            cond_mod -= 2
            cond_reasons.append("严重口渴(-2)")
        if fullness < 25:
            cond_mod -= 2
            cond_reasons.append("饥肠辘辘(-2)")

        # 5. Dynamic weather modifiers
        weather_mod = 0
        weather_reasons = []
        weather_label = str(variables.get("weather") or "")
        weather_type = classify_weather_type(weather_label, str(variables.get("weather_type") or ""))
        if weather_type in ("windy", "storm"):
            if any(k in clean_action for k in ("火", "点", "燃", "烧")) and (shelter_val or 0) == 0 and "lighter" not in inv_ids:
                weather_mod -= 2
                weather_reasons.append("狂风干扰生火(-2)")
        if weather_type == "storm" and (shelter_val or 0) == 0 and not outfit.get("outer"):
            weather_mod -= 1
            weather_reasons.append("暴雨湿滑受阻(-1)")
        if weather_type in ("windy", "rain", "storm") and outfit.get("outer"):
            weather_mod += 1
            weather_reasons.append("防风防水护佑(+1)")
        if weather_type == "clear" and outfit.get("head") and any(
            k in clean_action for k in ("采", "摘", "捡", "抓", "搜", "寻", "攀", "挖")
        ):
            weather_mod += 1
            weather_reasons.append("遮阳防晒护佑(+1)")
        if weather_type == "foggy" and skill == "perception":
            weather_mod -= 1
            weather_reasons.append("海雾遮蔽视线(-1)")

        total_mod = attr_mod + outfit_mod + tool_mod + cond_mod + weather_mod
        total = roll + total_mod

        # Graded evaluation
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
        if outfit_reasons:
            reason_parts.extend(outfit_reasons)
        if tool_reasons:
            reason_parts.extend(tool_reasons)
        if cond_reasons:
            reason_parts.extend(cond_reasons)
        if weather_reasons:
            reason_parts.extend(weather_reasons)

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

    def generate_fallback_turn(
        self,
        session: GameSession,
        user_text: str,
        matched_action: Optional[ActionOption],
        check_passed: Optional[bool],
        current_scene: Optional[SceneNode],
        client_roll: Optional[int] = None,
    ) -> tuple[str, Dict[str, Any]]:
        """Fallback local SLG Director: generates vivid narrative and state delta when external agent is unavailable."""
        clean_action = re.sub(r"^【.*?】", "", user_text).strip()
        clean_action = re.sub(r"\[检定数据:.*?\]", "", clean_action).strip()
        delta: Dict[str, Any] = {}

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
                    delta = dict(matched_action.on_success or {})
                    if "attributes_delta" in delta and isinstance(delta["attributes_delta"], dict):
                        delta["attributes_delta"] = {
                            k: (v // 2 if k == "stamina" and v < 0 else v)
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
                    delta = dict(matched_action.on_success or {})
                elif eval_res["outcome"] == "partial_success":
                    narration = (
                        f"周围环境险恶复杂，潮气与海风不断侵扰。虽然过程波折重重，但幸得【{eval_res['reason']}】的有力支撑，你咬牙撑过难关，终究在付出额外汗水后艰难达成了目标！\n\n"
                        f"【DM综合裁决 · 代价成功】（投骰 {eval_res['roll']} + 修正 {eval_res['modifier']} = {eval_res['total']} vs DC: {eval_res['difficulty']}）\n\n"
                        f"{succ_msg}\n\n"
                        f"主要目标顺利达成，但激烈的应对让你多消耗了些许体能。"
                    )
                    delta = dict(matched_action.on_success or {})
                    if "attributes_delta" not in delta or not isinstance(delta["attributes_delta"], dict):
                        delta["attributes_delta"] = {}
                    delta["attributes_delta"]["stamina"] = int(delta["attributes_delta"].get("stamina", -4)) - 3
                else:
                    narration = (
                        f"自然与环境的阻碍超乎预料。纵然有【{eval_res['reason']}】的勉力支撑，这次突进依然未能尽如人意。\n\n"
                        f"【DM综合裁决 · 受挫转折】（投骰 {eval_res['roll']} + 修正 {eval_res['modifier']} = {eval_res['total']} vs DC: {eval_res['difficulty']}）\n\n"
                        f"{fail_msg}\n\n"
                        f"你稳住阵脚向后轻撤半步。这次尝试虽未达成，却让你彻底探明了前方的虚实暗礁，为你下一次策略调整赢得了关键的情报！"
                    )
                    delta = dict(matched_action.on_failure or {})
                    if "time_cost" not in delta:
                        delta["time_cost"] = 1
                    if "attributes_delta" not in delta:
                        delta["attributes_delta"] = {"stamina": -3, "hydration": -2}

                delta["check_result"] = eval_res
                if eval_res["isSuccess"]:
                    if "gain_item" in delta:
                        delta["add_inventory"] = [{"id": delta["gain_item"]}]
                    if "equip_outfit" in delta and "outfit" not in delta:
                        delta["outfit"] = delta["equip_outfit"]
                    if "variables" not in delta and matched_action.id == "scavenge_bottle":
                        delta["variables"] = {"found_bottle": True}
                    if "time_cost" not in delta:
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
                    f"周围的环境因你的努力而悄然改变，为你接下来的求生开辟了新的可能。"
                )
                delta = dict(matched_action.on_success or {})
                if "gain_item" in delta:
                    delta["add_inventory"] = [{"id": delta["gain_item"]}]
                if "equip_outfit" in delta and "outfit" not in delta:
                    delta["outfit"] = delta["equip_outfit"]
                if matched_action.id == "pickup_metal_box" and "visuals" not in delta:
                    delta["visuals"] = {"hero_image": "【物品特写】洗净泥沙的防水金属盒"}
                if "time_cost" not in delta:
                    delta["time_cost"] = 1
            elif matched_action.type == "transition":
                target_title = matched_action.target_scene or "未知新区域"
                if matched_action.target_scene:
                    target_obj = self.scenario_mgr.get_scene(session.scenario_id, matched_action.target_scene)
                    if target_obj:
                        target_title = target_obj.title
                narration = (
                    f"你收拾起为数不多的物资，迈开脚步朝着新的方向前进。\n\n"
                    f"狂风吹拂着你的衣角，你穿过狭窄陡峭的路径，终于抵达了【{target_title}】。\n\n"
                    f"眼前的景象豁然开朗，全新的机遇与潜在的危险正静候着你的探索。"
                )
                delta = {
                    "current_scene": matched_action.target_scene,
                    "time_cost": 1,
                    "attributes_delta": {"stamina": -5, "hydration": -4},
                }
            else:
                narration = f"你专注于执行【{matched_action.label}】，谨慎地推动着当前的事态发展。"
                delta = {"time_cost": 1}
        else:
            # Open-ended scenario resolution
            if session.scenario_id == "island_survival":
                has_lighter = any(
                    (isinstance(i, dict) and i.get("id") == "lighter")
                    for i in (session.player_state.inventory or [])
                )
                fire_terms = ("打火机", "火机", "点火", "生火", "引燃", "点燃", "火堆", "篝火", "甘草", "枯草", "升火", "烧火")
                cook_terms = ("煮", "烤", "吃", "食", "饭", "烹", "蟹", "肉")
                wants_fire = any(k in clean_action for k in fire_terms)
                wants_cook = any(k in clean_action for k in cook_terms)

                if wants_fire and has_lighter:
                    delta["variables"] = {"fire_started": True}
                    delta["visuals"] = {"hero_image": "/assets/illustrations/campfire.png"}
                    inv_ids = [
                        (i.get("id") if isinstance(i, dict) else str(i))
                        for i in (session.player_state.inventory or [])
                    ]
                    if wants_cook and ("raw_crab" in inv_ids or "wild_food" in inv_ids or "coconut" in inv_ids):
                        target_food = "raw_crab" if "raw_crab" in inv_ids else ("wild_food" if "wild_food" in inv_ids else "coconut")
                        delta["remove_inventory"] = [target_food]
                        delta["attributes_delta"] = {"fullness": 35, "stamina": 16, "temperature": 1}
                        delta["san_delta"] = 6
                        delta["time_cost"] = 1
                        food_desc = "新鲜海蟹" if target_food == "raw_crab" else ("采摘坚果" if target_food == "wild_food" else "烤椰肉")
                        narration = (
                            f"你从背包中稳稳取出防风打火机。咔哒一声脆响，强劲的橙蓝色防风火苗猛烈喷吐，迅速引燃了收集堆叠的干燥甘草与枯枝！\n\n"
                            f"【行动成功】火舌飞快舔舐木柴，一堆明亮温暖的篝火在身前熊熊燃烧起来，彻底驱散了周遭的湿冷海风与野兽威胁！\n\n"
                            f"紧接着，你将背包中的{food_desc}架在篝火上炙烤。火焰将食物烤得滋滋作响、通红滚烫，诱人的焦香海鲜肉气在四周弥漫！\n\n"
                            f"你大快朵颐吃下温热熟透的食物，空虚的胃部被彻底充实，体温与体力大幅回升，精神为之一振！"
                        )
                    else:
                        delta["attributes_delta"] = {"stamina": -4, "temperature": 1}
                        delta["san_delta"] = 5
                        delta["time_cost"] = 1
                        narration = (
                            f"你从背包中取出可靠的防风打火机，拇指一擦打火轮，稳定的火苗立刻喷吐而出！\n\n"
                            f"【行动成功】防风打火机精准引燃了干燥的甘草与引火碎木，火焰腾空而起，生起了一堆明亮温暖的篝火！周围的湿冷瞬间消散。\n\n"
                            f"稳定的火源已经就绪，接下来可以随时在篝火上烧水、煮熟食材或安然过夜。"
                        )
                elif wants_fire and not has_lighter:
                    delta["time_cost"] = 1
                    narration = (
                        f"你试图在四周寻找火源生火，但你在随身背包中仔细翻找后发现并没有携带打火机。\n\n"
                        f"海风呼啸而过，未处理的干柴无法凭空引燃。或许可以在沙滩散落的客机残骸或防水金属盒中搜寻生火工具。"
                    )
                else:
                    inv_ids = [
                        (i.get("id") if isinstance(i, dict) else str(i))
                        for i in (session.player_state.inventory or [])
                    ]
                    shelter_terms = ("窝棚", "庇护所", "遮蔽所", "木棚", "搭棚", "搭建营地")
                    collector_terms = ("集水器", "雨水收集", "接水", "集水装置")
                    wants_shelter = any(k in clean_action for k in shelter_terms)
                    wants_collector = any(k in clean_action for k in collector_terms)

                    if wants_shelter:
                        if "branches" in inv_ids and "rope" in inv_ids:
                            delta["remove_inventory"] = ["branches", "rope"]
                            delta["variables"] = {"shelter_level": 1}
                            delta["visuals"] = {"hero_image": "/assets/props/shelter.png"}
                            delta["attributes_delta"] = {"stamina": -14, "hydration": -8, "fullness": -6, "temperature": 1}
                            delta["san_delta"] = 8
                            delta["time_cost"] = 1
                            narration = (
                                "你将干燥硬木枝干斜靠在背风处，用坚韧的纤维绳反复绞紧主梁，再铺上宽大椰叶封顶。\n\n"
                                "【建造成功】一座结实耐用的防风窝棚拔地而起，已稳稳立在营地边缘的视觉区！从此你拥有了遮风挡雨、安心休整的稳固据点。"
                            )
                        else:
                            missing = []
                            if "branches" not in inv_ids:
                                missing.append("干燥树枝浮木")
                            if "rope" not in inv_ids:
                                missing.append("坚韧纤维绳")
                            delta["time_cost"] = 1
                            narration = (
                                f"你选好了搭建防风窝棚的背风平地，但翻找背包后发现还缺少关键建材：{'、'.join(missing)}。\n\n"
                                "收集齐树枝与纤维绳后，即可随时搭起这座耐用的荒岛庇护所。"
                            )
                    elif wants_collector:
                        if "glass_bottle" in inv_ids and "rope" in inv_ids:
                            delta["remove_inventory"] = ["glass_bottle", "rope"]
                            delta["variables"] = {"water_collector_built": True}
                            delta["visuals"] = {"hero_image": "/assets/props/water_collector.png"}
                            delta["attributes_delta"] = {"stamina": -10, "hydration": -4}
                            delta["san_delta"] = 5
                            delta["time_cost"] = 1
                            narration = (
                                "你用木架支起漏斗状的大片热带阔叶，以纤维绳扎实固定，再将厚壁玻璃瓶安放在导流叶尖下方。\n\n"
                                "【建造成功】简易雨水收集器已搭建完毕并展示在营地侧栏！露水与雨水正沿着叶脉一滴滴汇入瓶中。"
                            )
                        else:
                            missing = []
                            if "glass_bottle" not in inv_ids:
                                missing.append("厚壁玻璃瓶")
                            if "rope" not in inv_ids:
                                missing.append("坚韧纤维绳")
                            delta["time_cost"] = 1
                            narration = (
                                f"你想架设一套持续蓄水的雨水收集器，但目前缺少关键构件：{'、'.join(missing)}。"
                            )
                    else:
                        w_label = str((session.player_state.variables or {}).get("weather") or "")
                        w_type = str((session.player_state.variables or {}).get("weather_type") or "")
                        w_slot = str((session.player_state.variables or {}).get("time_slot") or "")
                        w_cue = get_weather_narrative_cue(w_label, w_type, w_slot)
                        narration = (
                            f"你在险恶的孤岛环境中尝试【{clean_action}】。{w_cue}\n\n"
                            f"沙滩与灌木间回荡着你的脚步声，潮水在不远处涨落起伏。虽然并未立即触发某种机关或质变，"
                            f"但这番探寻让你对周遭的地形与动静有了更深入的把握。体力略有消耗，但你的求生意志愈加坚定。"
                        )
                        delta = {
                            "time_cost": 1,
                            "attributes_delta": {"stamina": -3, "hydration": -2},
                        }
            else:
                narration = (
                    f"幽暗的公馆大厅中蜡烛影影绰绰，窗外寒鸦惊啼。你谨慎地尝试【{clean_action}】。\n\n"
                    f"沉闷的脚步声在石质地板间激起微弱的回响。空气中弥漫着旧羊皮纸与蜡油的味道，"
                    f"整座宅邸的压迫感似乎无处不在，随时可能揭开更深层的谜团。"
                )
                delta = {
                    "time_cost": 1,
                    "san_delta": -1,
                }

        if session.scenario_id == "island_survival" and (delta.get("time_cost") or 0) > 0:
            w_label = str((session.player_state.variables or {}).get("weather") or "")
            w_type = str((session.player_state.variables or {}).get("weather_type") or "")
            w_slot = str((session.player_state.variables or {}).get("time_slot") or "")
            if w_label and w_label not in narration:
                w_cue = get_weather_narrative_cue(w_label, w_type, w_slot)
                if w_cue not in narration:
                    narration = f"{narration}\n\n【气象实况 · {w_label}】{w_cue}"

        formatted = f"{narration}\n\n```state_delta\n{json.dumps(delta, ensure_ascii=False, indent=2)}\n```\n"
        return formatted, delta

    @staticmethod
    def _match_freeform_action(
        scene: Optional[SceneNode],
        user_text: str,
        player_state: PlayerState,
    ) -> tuple[Optional[ActionOption], bool]:
        """Match free-form player text to an eligible scene action without hijacking distinct intents.

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

        # 2. Intent-aware disambiguation for metal box / luggage actions
        box_nouns = ("金属盒", "铁盒", "铝盒", "防水盒", "盒子")
        if any(noun in clean_input for noun in box_nouns):
            search_verbs = ("搜", "翻", "找", "撬", "打开", "拆开", "里面", "内里", "夹层", "打火机")
            pickup_verbs = ("捡", "拾", "拿", "洗", "冲", "擦", "带走", "收", "装")
            wants_search = any(v in clean_input for v in search_verbs)
            wants_pickup = any(v in clean_input for v in pickup_verbs)
            if wants_search:
                for target_id in ("search_luggage", "open_metal_box_coastal", "open_metal_box_in_jungle"):
                    act = next((a for a in eligible_actions if a.id == target_id), None)
                    if act:
                        return act, False
                return None, False
            if wants_pickup:
                act = next((a for a in eligible_actions if a.id == "pickup_metal_box"), None)
                if act:
                    return act, False
                return None, False
            # Ambiguous reference to the box (e.g. "把金属盒当锅烧水"): let LLM handle freely
            if "烧水" in clean_input or "煮水" in clean_input:
                act = next((a for a in eligible_actions if a.id == "boil_water_in_metal_box"), None)
                if act:
                    return act, False
            return None, False

        # 3. Fire-making & cooking intent-aware resolution
        fire_terms = ("点火", "生火", "升火", "引燃", "点燃", "篝火", "火堆", "烧火", "甘草", "枯草")
        cook_terms = ("煮", "烤", "热食", "烹饪", "做饭", "煮食", "烤食", "熟食")
        wants_fire = any(v in clean_input for v in fire_terms)
        wants_cook = any(v in clean_input for v in cook_terms)
        has_lighter = any(
            (isinstance(i, dict) and i.get("id") == "lighter")
            for i in (player_state.inventory or [])
        )

        # Composite action: player wants to both light fire AND cook/eat food
        # Do not collapse to a single-step preset action; let the open-ended handler fulfill both
        if wants_fire and wants_cook:
            return None, False

        if wants_fire and has_lighter:
            for act_id in ("beach_campfire", "coastal_campfire", "light_campfire", "craft_campfire"):
                act = next((a for a in eligible_actions if a.id == act_id), None)
                if act:
                    return act, False

        if wants_cook:
            for act_id in ("beach_cook_food", "coastal_cook_food", "cook_food_on_fire", "cook_meal"):
                act = next((a for a in eligible_actions if a.id == act_id), None)
                if act:
                    return act, False

        # 4. Substring or domain keyword match across eligible actions
        kw_map = {
            "scavenge_bottle": ["玻璃瓶", "瓶子", "漂流瓶"],
            "search_luggage": ["行李", "打火机"],
            "pick_seashell": ["贝壳", "海螺", "螺"],
            "catch_shore_crab": ["螃蟹", "海蟹", "抓蟹", "红蟹"],
            "gather_driftwood": ["干柴", "树枝", "浮木", "捡柴"],
            "cut_vines": ["藤蔓", "老藤", "割藤"],
            "collect_fresh_water": ["泉水", "甘泉", "装水", "打水"],
            "gather_coconuts": ["椰子", "采摘椰子", "摘椰子"],
            "beach_campfire": ["生火", "点火", "篝火", "火堆", "引燃", "点燃", "升火"],
            "coastal_campfire": ["生火", "点火", "篝火", "火堆", "引燃", "点燃", "升火"],
            "light_campfire": ["生火", "点火", "篝火", "火堆", "引燃", "点燃", "升火"],
            "craft_campfire": ["生火", "点火", "篝火", "火堆", "引燃", "点燃", "升火"],
            "beach_cook_food": ["烤蟹", "烤肉", "煮食", "烤食物", "煮食物", "做饭", "烹饪"],
            "coastal_cook_food": ["烤肉", "烤蟹", "烤椰子", "煮食", "烤食物", "煮食物", "做饭", "烹饪"],
            "cook_food_on_fire": ["烤肉", "烤蟹", "煮食", "烤食物", "煮食物", "做饭", "热食"],
            "cook_meal": ["烤肉", "烤蟹", "做饭", "烹饪"],
            "craft_rope": ["搓绳", "编织绳索", "做绳子", "编绳"],
            "build_beach_shelter": ["窝棚", "庇护所", "搭棚", "遮蔽所"],
            "build_jungle_shelter": ["窝棚", "庇护所", "搭棚", "遮蔽所"],
            "build_deep_shelter": ["窝棚", "庇护所", "搭棚", "遮蔽所"],
            "build_water_collector_beach": ["集水器", "雨水收集", "接水装置"],
            "build_water_collector_coastal": ["集水器", "雨水收集", "接水装置"],
            "build_water_collector_deep": ["集水器", "雨水收集", "接水装置"],
            "collect_water_beach": ["接水喝", "喝集水器", "取集水"],
            "collect_water_coastal": ["接水喝", "喝集水器", "取集水"],
            "collect_water_deep": ["接水喝", "喝集水器", "取集水"],
            "rest_in_shelter_beach": ["窝棚休息", "进窝棚", "庇护所休息"],
            "rest_in_shelter_coastal": ["窝棚休息", "进窝棚", "庇护所休息"],
            "rest_in_shelter_deep": ["窝棚休息", "进窝棚", "庇护所休息"],
            "rest_by_fire": ["休息", "睡觉", "过夜"],
            "rest_by_campfire": ["休息", "睡觉", "过夜"],
        }
        for a in eligible_actions:
            if len(clean_input) >= 2 and clean_input in a.label:
                return a, False
            kws = kw_map.get(a.id, [])
            if any(kw in clean_input for kw in kws):
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
        if input_data.forwarded_props and isinstance(input_data.forwarded_props, dict):
            scenario_id = input_data.forwarded_props.get("scenario_id", scenario_id)
            action_id = input_data.forwarded_props.get("action_id")
            client_state = input_data.forwarded_props.get("player_state")
            recent_history = input_data.forwarded_props.get("recent_history")
            if "client_roll" in input_data.forwarded_props:
                try:
                    client_roll = int(input_data.forwarded_props.get("client_roll"))
                except (ValueError, TypeError):
                    client_roll = None
            if "check_passed" in input_data.forwarded_props:
                check_passed = bool(input_data.forwarded_props.get("check_passed"))

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
                pre_scene, user_text, session.player_state
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
                    ToolCallStartEvent(call_id=call_id, tool_name=tool_name)
                )

            elif event.event_type == "tool_call_end":
                call_id = event.data.get("call_id", str(uuid.uuid4()))
                yield self.encoder.encode(
                    ToolCallEndEvent(call_id=call_id)
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

        prompt = f"""你是一名专业的游戏剧本设计与代码协作者（AG-SLG Studio Co-pilot，遵循 ag-slg-director 视觉分层规范）。
当前剧本资产目录位于当前工作区的 scripts/{scenario_id}/ 下。
用户创作需求：{user_text}

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

