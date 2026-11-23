"""AG-UI Protocol Bridge for AG-SLG-FrameWork.

Translates game interactions and Agent CLI output to standard AG-UI SSE streams:
RunStarted -> TextMessage* -> StateDelta / ToolCall -> RunFinished.
"""

import asyncio
import json
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
    resolve_scene_actions,
)


TIME_SLOTS = ["清晨", "上午", "下午", "黄昏", "夜晚", "深夜"]
SURVIVAL_CLAMP_100 = {"stamina", "hydration", "fullness"}


def _clamp_attr(key: str, value: int) -> int:
    if key in SURVIVAL_CLAMP_100:
        return max(0, min(100, value))
    if key == "temperature":
        return max(30, min(42, value))
    return value


ITEM_META = {
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
        "icon": "",
        "desc": "刚抓获的肥硕海蟹，生吃有腹泻风险，在篝火上烤熟味道极佳。",
    },
    "coconut": {
        "name": "新鲜青椰",
        "icon": "",
        "desc": "沉甸甸的热带青椰，同时富含清甜椰汁与饱腹椰肉。",
    },
    "cooked_food": {
        "name": "炭烤海鲜与坚果拼盘",
        "icon": "",
        "desc": "散发出诱人焦香的熟食，能大幅恢复饱食度与体力。",
    },
}


class GameSession:
    """In-memory game session tracking player state and Agent conversation ID."""

    def __init__(self, session_id: str, scenario_id: str, initial_state: PlayerState):
        self.session_id = session_id
        self.scenario_id = scenario_id
        self.player_state = initial_state
        self.agent_conversation_id: Optional[str] = None
        self.history: List[Dict[str, str]] = []
        self.dynamic_actions: List[Dict[str, Any]] = []

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
            for k, v in delta["variables"].items():
                self.player_state.variables[k] = v
                patches.append({"op": "add", "path": f"/variables/{k}", "value": v})

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

                # Adjust weather label to match time of day
                weather_by_slot = {
                    "清晨": "海雾微凉",
                    "上午": "晴朗炎热",
                    "下午": "烈日酷热",
                    "黄昏": "海风渐起",
                    "夜晚": "夜寒星沉",
                    "深夜": "凛冽夜风",
                }
                if "weather" in self.player_state.variables:
                    w = weather_by_slot.get(new_slot, self.player_state.variables["weather"])
                    self.player_state.variables["weather"] = w
                    patches.append({"op": "add", "path": "/variables/weather", "value": w})

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
            for raw_item in delta["add_inventory"]:
                item = dict(raw_item) if isinstance(raw_item, dict) else {"id": str(raw_item), "name": str(raw_item)}
                item_id = item.get("id", "")
                if item_id in ITEM_META:
                    meta = ITEM_META[item_id]
                    if not item.get("name") or item["name"] == item_id:
                        item["name"] = meta["name"]
                    if not item.get("icon"):
                        item["icon"] = meta["icon"]
                    if not item.get("desc"):
                        item["desc"] = meta["desc"]
                self.player_state.inventory.append(item)
                added_items.append(item)

        if removed_any:
            patches.append({"op": "replace", "path": "/inventory", "value": list(self.player_state.inventory)})
        else:
            for item in added_items:
                patches.append({"op": "add", "path": "/inventory/-", "value": item})

        if "available_actions" in delta and isinstance(delta["available_actions"], list):
            self.dynamic_actions = [a for a in delta["available_actions"] if isinstance(a, dict)]

        if "visuals" in delta and isinstance(delta["visuals"], dict):
            patches.append({"op": "replace", "path": "/visuals", "value": delta["visuals"]})

        return patches



class AGUIBridge:
    """Bridges game events and CLI agent output to AG-UI SSE protocol."""

    def __init__(self, scenario_mgr: ScenarioManager, driver: BaseAgentDriver):
        self.scenario_mgr = scenario_mgr
        self.driver = driver
        self.encoder = EventEncoder()
        self.sessions: Dict[str, GameSession] = {}

    def get_or_create_session(self, thread_id: str, scenario_id: str = "black_crow_manor") -> GameSession:
        if thread_id in self.sessions:
            return self.sessions[thread_id]

        spec = self.scenario_mgr.load_scenario(scenario_id)
        # Deep copy initial player state
        init_state = PlayerState(**spec.world.initial_player_state.model_dump())
        session = GameSession(thread_id, scenario_id, init_state)
        self.sessions[thread_id] = session
        return session

    def build_play_prompt(self, session: GameSession, user_input: str) -> str:
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
        inv_desc = [
            f"{item.get('name', item.get('id', ''))} (id: {item.get('id', '')})"
            for item in session.player_state.inventory
        ]

        prompt = f"""你是一款高沉浸感文字跑团（TRPG / SLG）的地下城主（DM / Game Master）兼视觉导演（遵循 ag-slg-director 规范）。
当前世界观：{scenario.world.title} (ID: {scenario.world.id})
玩家当前状态：
- 角色名：{session.player_state.name}
- HP：{session.player_state.hp} / SAN：{session.player_state.san} / 金币：{session.player_state.gold}
- 生存与角色属性：{session.player_state.attributes}
- 背包物品：{inv_desc or '空'}
- 剧本变量（含时间/昼夜/进度）：{session.player_state.variables}
- 当前所在场景：{curr_scene.title if curr_scene else curr_scene_id} ({curr_scene_id})

当前场景预设视觉资源：
- 场景底图 (Background): {scene_bg or '默认空间背景'}
- 焦点插图 (Hero Image): {scene_hero or '无'}
- 前景立绘 (Foreground): {scene_fg or '无'}
- 环境氛围 (Atmosphere): {scene_atmo}

当前场景环境描述：
{scene_desc}

场景中存在的人物：
{scene_npcs or '无'}

当前可用行动选项：
{scene_actions or '无'}

玩家执行了以下行动：
"{user_input}"

请作为 DM 进行剧情演绎与多图层视觉编排：
1. 叙事文本与对话分明：生动叙述环境与行动结果，NPC 发言请以 角色名: “对话内容” 格式清晰表达。严禁在叙述文本中直接泄漏具体图片文件路径。
2. 视觉舞台导演原则（ag-slg-director）：
   - 背景稳定性：不要在普通的对话轮换背景；仅在发生场景转移或环境巨变时更新 visuals.background。
   - 角色立绘调度：与具体 NPC 对话时，设置 visuals.foreground 为其立绘；玩家独处检定或离开时置空。
   - 焦点特写镜头：当玩家成功发现关键线索、搜查物品或遭遇高潮事件时，在 visuals.hero_image 给出特写插图路径或语义描述（如“【证物特写】雕花银钥匙”）。
3. 数值与动态选项演算（非常重要）：
   - 若玩家进食、饮水、休息、劳作或受环境影响，务必在 state_delta 中通过 `attributes_delta` 真实更新对应属性（如 `fullness` 饱食度、`hydration` 水分、`stamina` 体力、`temperature` 体温），消耗掉的食材/饮水通过 `remove_inventory` 列出道具 id 移除。
   - 行动耗时可通过 `time_cost`（整数，如 1 表示推进一个时段：清晨→上午→下午→黄昏→夜晚→深夜）推进时间。
   - 如因剧情变化衍生出新的临时行动选项，可通过 `available_actions` 提供动态选项列表；预设场景选项也会随状态与时间自动刷新。
4. 若产生场景转移、数值变化、道具增减、时间推进或视觉变更，在回复最末尾附带一个 ```state_delta 代码块：
```state_delta
{{
  "current_scene": "目标场景ID（若发生转移）",
  "hp_delta": 0,
  "san_delta": 0,
  "attributes_delta": {{"fullness": 25, "stamina": 10}},
  "time_cost": 1,
  "add_inventory": [{{"id": "item_id", "name": "道具名", "desc": "描述"}}],
  "remove_inventory": ["consumed_item_id"],
  "variables": {{"variable_key": "variable_value"}},
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
                user_text = str(last_msg.content)
            elif isinstance(last_msg, dict):
                user_text = str(last_msg.get("content", ""))
        if not user_text:
            user_text = "[继续行动]"

        # Check forwarded props for scenario_id and optional preset action metadata
        scenario_id = "black_crow_manor"
        action_id: Optional[str] = None
        check_passed: Optional[bool] = None
        if input_data.forwarded_props and isinstance(input_data.forwarded_props, dict):
            scenario_id = input_data.forwarded_props.get("scenario_id", scenario_id)
            action_id = input_data.forwarded_props.get("action_id")
            if "check_passed" in input_data.forwarded_props:
                check_passed = bool(input_data.forwarded_props.get("check_passed"))

        session = self.get_or_create_session(thread_id, scenario_id)
        pre_scene_id = session.player_state.current_scene
        pre_scene = self.scenario_mgr.get_scene(scenario_id, pre_scene_id) if pre_scene_id else None
        matched_action: Optional[ActionOption] = None
        if action_id and pre_scene and pre_scene.actions:
            matched_action = next((a for a in pre_scene.actions if a.id == action_id), None)

        prompt = self.build_play_prompt(session, user_text)

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

        # 3. TEXT_MESSAGE_END
        yield self.encoder.encode(TextMessageEndEvent(message_id=message_id))

        # Parse state delta from full text buffer if present
        delta_dict: Dict[str, Any] = {}
        state_delta_match = re.search(
            r"```state_delta\s*(\{.*?\})\s*```", full_text_buffer, re.DOTALL
        )
        if state_delta_match:
            try:
                parsed = json.loads(state_delta_match.group(1))
                if isinstance(parsed, dict):
                    delta_dict = parsed
            except Exception:
                # shortcut: ignore json parse failure gracefully on malformed LLM delta block
                delta_dict = {}

        if matched_action is not None:
            delta_dict = self._merge_action_effects(
                delta_dict, matched_action, check_passed, session.player_state
            )

        if delta_dict:
            patches = session.apply_delta(delta_dict)
            if patches:
                curr_scene_after = self.scenario_mgr.get_scene(
                    session.scenario_id, session.player_state.current_scene
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
                user_text = str(last_msg.content)
            elif isinstance(last_msg, dict):
                user_text = str(last_msg.get("content", ""))

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

        async for event in self.driver.run_stream(
            prompt=prompt,
            conversation_id=None,
            cwd=self.scenario_mgr.base_dir.parent,
        ):
            if event.event_type == "text_delta":
                delta = event.data.get("text", "")
                full_studio_response += delta
                yield self.encoder.encode(
                    TextMessageContentEvent(message_id=message_id, delta=delta)
                )

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

