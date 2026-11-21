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
from server.scenario_manager import ScenarioManager, PlayerState, SceneNode


class GameSession:
    """In-memory game session tracking player state and Agent conversation ID."""

    def __init__(self, session_id: str, scenario_id: str, initial_state: PlayerState):
        self.session_id = session_id
        self.scenario_id = scenario_id
        self.player_state = initial_state
        self.agent_conversation_id: Optional[str] = None
        self.history: List[Dict[str, str]] = []

    def apply_delta(self, delta: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Apply state delta and return standard JSON-patch like delta list."""
        patches = []
        if "current_scene" in delta and delta["current_scene"]:
            self.player_state.current_scene = delta["current_scene"]
            patches.append({"op": "replace", "path": "/current_scene", "value": self.player_state.current_scene})

        if "hp" in delta:
            self.player_state.hp = int(delta["hp"])
            patches.append({"op": "replace", "path": "/hp", "value": self.player_state.hp})
        elif "hp_delta" in delta:
            self.player_state.hp = max(0, self.player_state.hp + int(delta["hp_delta"]))
            patches.append({"op": "replace", "path": "/hp", "value": self.player_state.hp})

        if "san" in delta:
            self.player_state.san = int(delta["san"])
            patches.append({"op": "replace", "path": "/san", "value": self.player_state.san})
        elif "san_delta" in delta:
            self.player_state.san = max(0, self.player_state.san + int(delta["san_delta"]))
            patches.append({"op": "replace", "path": "/san", "value": self.player_state.san})

        if "gold" in delta:
            self.player_state.gold = int(delta["gold"])
            patches.append({"op": "replace", "path": "/gold", "value": self.player_state.gold})

        if "variables" in delta and isinstance(delta["variables"], dict):
            for k, v in delta["variables"].items():
                self.player_state.variables[k] = v
                patches.append({"op": "add", "path": f"/variables/{k}", "value": v})

        if "add_inventory" in delta and isinstance(delta["add_inventory"], list):
            for item in delta["add_inventory"]:
                self.player_state.inventory.append(item)
                patches.append({"op": "add", "path": "/inventory/-", "value": item})

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
        scene_npcs = [f"{npc.name} ({npc.greeting})" for npc in (curr_scene.npcs if curr_scene else [])]
        scene_actions = [f"[{act.id}] {act.label}" for act in (curr_scene.actions if curr_scene else [])]

        prompt = f"""你是一款高沉浸感文字跑团（TRPG / SLG）的地下城主（DM / Game Master）。
当前世界观：{scenario.world.title} (ID: {scenario.world.id})
玩家当前状态：
- 角色名：{session.player_state.name}
- HP：{session.player_state.hp} / SAN：{session.player_state.san} / 金币：{session.player_state.gold}
- 属性：{session.player_state.attributes}
- 背包物品：{[item.get('name', item.get('id', '')) for item in session.player_state.inventory]}
- 剧本变量：{session.player_state.variables}
- 当前所在场景：{curr_scene.title if curr_scene else curr_scene_id} ({curr_scene_id})

当前场景环境描述：
{scene_desc}

场景中存在的人物：
{scene_npcs or '无'}

场景预设可选行动：
{scene_actions or '无'}

玩家执行了以下行动：
"{user_input}"

请作为 DM 进行剧情演绎并返回：
1. 生动而具沉浸感的叙事文本，推进剧情，如有 NPC 对话则以符合角色性格的方式回复。
2. 如涉及属性检定或骰子投掷，请合理进行判断并叙述。
3. 若玩家行为导致场景转移、数值变化、获得物品、剧情变量变更，或者你想为玩家呈现特定情境插图/立绘/背景切换（视觉组织），请在回复的最末尾附带一个且仅一个 ```state_delta 代码块，格式如下：
```state_delta
{{
  "current_scene": "目标场景ID（若发生转移）",
  "hp_delta": -5,
  "san_delta": 0,
  "add_inventory": [{{"id": "item_id", "name": "道具名", "desc": "描述"}}],
  "variables": {{"variable_key": "variable_value"}},
  "visuals": {{
    "hero_image": "/assets/illustrations/xxx.png 或 视觉描述标签（如'雨夜古宅特写'）",
    "foreground": "/assets/characters/xxx.png",
    "background": "/assets/scenes/xxx.png"
  }}
}}
```
注意：如果状态与画面没有任何变化，无需输出 state_delta 代码块。
"""

        return prompt

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

        # Check forwarded props for scenario_id if provided
        scenario_id = "black_crow_manor"
        if input_data.forwarded_props and isinstance(input_data.forwarded_props, dict):
            scenario_id = input_data.forwarded_props.get("scenario_id", scenario_id)

        session = self.get_or_create_session(thread_id, scenario_id)
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
        state_delta_match = re.search(
            r"```state_delta\s*(\{.*?\})\s*```", full_text_buffer, re.DOTALL
        )
        if state_delta_match:
            try:
                delta_dict = json.loads(state_delta_match.group(1))
                patches = session.apply_delta(delta_dict)
                if patches:
                    yield self.encoder.encode(StateDeltaEvent(delta=patches))
            except Exception:
                # shortcut: ignore json parse failure gracefully on malformed LLM delta block
                pass

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

        prompt = f"""你是一名专业的游戏剧本设计与代码协作者（AG-SLG Studio Co-pilot）。
当前剧本资产目录位于当前工作区的 scripts/{scenario_id}/ 下。
用户创作需求：{user_text}

你可以直接输出剧本构思与建议。如果你构思了一个完整的场景节点或更新了场景，请在回复中包含如下格式的代码块，以便系统自动将其写盘生效：
```scene_yaml:场景ID
id: "场景ID"
title: "场景标题"
background: "/assets/scenes/xxx.png"
music: "/assets/bgm/xxx.mp3"
description: |
  场景描述文本...
npcs: []
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

