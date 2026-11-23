import { useState, useEffect, useRef } from 'react';
import {
  PlayerState,
  ScenarioSpec,
  SceneNode,
  StoryMessage,
  ActionOption,
  DiceCheckEvent,
  VisualLayer,
} from '../../types';
import GameHUD from './GameHUD';
import StoryStream from './StoryStream';
import ActionPanel from './ActionPanel';

interface PlayViewProps {
  scenarioId?: string;
}

export default function PlayView({ scenarioId = 'black_crow_manor' }: PlayViewProps) {
  const [scenario, setScenario] = useState<ScenarioSpec | null>(null);
  const [playerState, setPlayerState] = useState<PlayerState | null>(null);
  const [messages, setMessages] = useState<StoryMessage[]>([]);
  const [streamingText, setStreamingText] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [diceEvent, setDiceEvent] = useState<DiceCheckEvent | null>(null);
  const [activeVisuals, setActiveVisuals] = useState<VisualLayer | null>(null);
  const [dynamicActions, setDynamicActions] = useState<ActionOption[] | null>(null);

  // 会话与运行 ID
  const threadIdRef = useRef<string>(`session-${scenarioId}-${Date.now()}`);

  // 重置游戏为初始状态
  const handleResetGame = (currentScenario?: ScenarioSpec | null) => {
    const sc = currentScenario || scenario;
    if (!sc) return;
    try {
      localStorage.removeItem(`ag_slg_save_${scenarioId}`);
    } catch (e) {
      console.error(e);
    }

    const initPlayer = sc.world.initial_player_state;
    setPlayerState({
      ...initPlayer,
      current_scene: initPlayer.current_scene || sc.world.initial_scene,
    });

    const openingText =
      scenarioId === 'island_survival'
        ? `海浪轰鸣，烈日高悬。你在一阵剧烈的咳嗽中清醒过来，口鼻中满是咸涩的海水与细沙。\n你作为一名空难幸存者漂流到了未知的荒岛沙滩上，眼前是一望无际的汪洋与茂密的未涉密林……\n体力正在流失，必须尽快搜查散落物资、寻找纯净淡水，并准备生火度过危机重重的夜晚！`
        : `暴风雨笼罩着荒凉的群山，古老的${sc.world.title}如同一头黑色的巨兽盘踞在悬崖之上。\n你作为${initPlayer.name}，踏上了通往公馆大门的石阶……`;

    threadIdRef.current = `session-${scenarioId}-${Date.now()}`;
    setActiveVisuals(null);
    setDynamicActions(null);
    setMessages([
      {
        id: `init-msg-${Date.now()}`,
        kind: 'narrator',
        content: openingText,
        timestamp: Date.now(),
      },
    ]);
  };

  // 1. 加载剧本与本地持久化存档
  useEffect(() => {
    fetch(`/api/scenarios/${scenarioId}`)
      .then((res) => {
        if (!res.ok) throw new Error('Failed to load scenario');
        return res.json();
      })
      .then((data: ScenarioSpec) => {
        setScenario(data);

        // 尝试恢复本地已保存的游戏进度
        try {
          const rawSaved = localStorage.getItem(`ag_slg_save_${scenarioId}`);
          if (rawSaved) {
            const saved = JSON.parse(rawSaved);
            if (saved && saved.playerState && Array.isArray(saved.messages) && saved.messages.length > 0) {
              setPlayerState(saved.playerState);
              setMessages(saved.messages);
              setActiveVisuals(saved.activeVisuals || null);
              setDynamicActions(saved.dynamicActions || null);
              threadIdRef.current = saved.threadId || `session-${scenarioId}-${Date.now()}`;
              return;
            }
          }
        } catch (err) {
          console.warn('Failed to restore saved game session, resetting:', err);
        }

        // 无存档时初始化新游戏
        handleResetGame(data);
      })
      .catch((err) => {
        console.error(err);
      });
  }, [scenarioId]);

  // 自动将进度写回 LocalStorage，确保切换模式或刷新页面绝不丢状态
  useEffect(() => {
    if (!scenario || !playerState || messages.length === 0) return;
    try {
      const payload = {
        scenarioId,
        threadId: threadIdRef.current,
        playerState,
        messages,
        activeVisuals,
        dynamicActions,
        savedAt: Date.now(),
      };
      localStorage.setItem(`ag_slg_save_${scenarioId}`, JSON.stringify(payload));
    } catch (e) {
      console.warn('LocalStorage save failed:', e);
    }
  }, [scenarioId, scenario, playerState, messages, activeVisuals, dynamicActions]);

  const currentSceneId = playerState?.current_scene || scenario?.world.initial_scene || '';
  const currentScene: SceneNode | undefined = scenario?.scenes[currentSceneId];

  // 根据玩家当前状态（背包、变量、属性、时间）评估预设行动的可见性
  const compareConditionValue = (actual: any, expected: any): boolean => {
    if (expected && typeof expected === 'object' && !Array.isArray(expected)) {
      const numActual = typeof actual === 'number' ? actual : 0;
      if ('lt' in expected && !(numActual < expected.lt)) return false;
      if ('lte' in expected && !(numActual <= expected.lte)) return false;
      if ('gt' in expected && !(numActual > expected.gt)) return false;
      if ('gte' in expected && !(numActual >= expected.gte)) return false;
      if ('ne' in expected && !(actual !== expected.ne)) return false;
      if ('in' in expected && !expected.in.includes(actual)) return false;
      if ('not_in' in expected && expected.not_in.includes(actual)) return false;
      return true;
    }
    return actual === expected;
  };

  const evaluateActionCondition = (
    condition: Record<string, any> | undefined,
    state: PlayerState | null
  ): boolean => {
    if (!condition || !state) return true;
    const invIds = new Set((state.inventory || []).map((item) => item.id));

    if ('has_item' in condition) {
      const reqs = Array.isArray(condition.has_item) ? condition.has_item : [condition.has_item];
      if (!reqs.every((id: string) => invIds.has(id))) return false;
    }
    if ('has_any_item' in condition) {
      const anyReqs: string[] = condition.has_any_item || [];
      if (!anyReqs.some((id: string) => invIds.has(id))) return false;
    }
    if ('not_has_item' in condition) {
      const forbs = Array.isArray(condition.not_has_item)
        ? condition.not_has_item
        : [condition.not_has_item];
      if (forbs.some((id: string) => invIds.has(id))) return false;
    }
    if (condition.variables && typeof condition.variables === 'object') {
      for (const [k, expected] of Object.entries(condition.variables)) {
        if (!compareConditionValue(state.variables?.[k], expected)) return false;
      }
    }
    if (condition.attributes && typeof condition.attributes === 'object') {
      for (const [k, expected] of Object.entries(condition.attributes)) {
        if (!compareConditionValue(state.attributes?.[k], expected)) return false;
      }
    }
    const timeSlot = state.variables?.time_slot;
    if ('time_slot_in' in condition && !condition.time_slot_in.includes(timeSlot)) {
      return false;
    }
    if ('time_slot_not_in' in condition && condition.time_slot_not_in.includes(timeSlot)) {
      return false;
    }
    if ('min_day' in condition) {
      const day = Number(state.variables?.day ?? 1);
      if (day < Number(condition.min_day)) return false;
    }
    return true;
  };

  const effectiveActions: ActionOption[] =
    dynamicActions !== null
      ? dynamicActions
      : (currentScene?.actions || []).filter((act) =>
          evaluateActionCondition(act.condition, playerState)
        );

  // 动态合成视觉图层（剧本静态配置 + Agent 在线调度）
  const effectiveScene: SceneNode | undefined = currentScene
    ? {
        ...currentScene,
        visuals: {
          ...(currentScene.visuals || {}),
          ...(activeVisuals || {}),
        },
        background: activeVisuals?.background || currentScene.visuals?.background || currentScene.background,
        foreground: activeVisuals?.foreground !== undefined ? activeVisuals.foreground : (currentScene.visuals?.foreground || currentScene.foreground),
        hero_image: activeVisuals?.hero_image !== undefined ? activeVisuals.hero_image : (currentScene.visuals?.hero_image || currentScene.hero_image),
        decorations: activeVisuals?.decorations || currentScene.visuals?.decorations || currentScene.decorations || [],
      }
    : undefined;

  // 辅助函数：应用 JSON-Patch 状态变化
  const applyStateDeltas = (patches: Array<{ op: string; path: string; value: any }>) => {
    let sceneSwitched = false;
    let nextVisualsPatch: VisualLayer | null = null;
    let nextDynamicActions: ActionOption[] | null | undefined = undefined;

    for (const patch of patches) {
      if (patch.path === '/current_scene') {
        sceneSwitched = true;
      } else if (patch.path === '/visuals') {
        nextVisualsPatch = patch.value;
      } else if (patch.path === '/available_actions') {
        nextDynamicActions = Array.isArray(patch.value) ? patch.value : null;
      }
    }

    if (sceneSwitched && !nextVisualsPatch) {
      setActiveVisuals(null);
    } else if (nextVisualsPatch) {
      setActiveVisuals((prev) => ({ ...(sceneSwitched ? {} : prev || {}), ...nextVisualsPatch }));
    }

    if (nextDynamicActions !== undefined) {
      setDynamicActions(nextDynamicActions);
    } else if (sceneSwitched) {
      setDynamicActions(null);
    }

    setPlayerState((prev) => {
      if (!prev) return prev;
      const next: PlayerState = {
        ...prev,
        attributes: { ...(prev.attributes || {}) },
        variables: { ...(prev.variables || {}) },
        inventory: [...(prev.inventory || [])],
      };
      for (const patch of patches) {
        if (patch.path === '/current_scene') {
          next.current_scene = patch.value;
        } else if (patch.path === '/hp') {
          next.hp = patch.value;
        } else if (patch.path === '/san') {
          next.san = patch.value;
        } else if (patch.path === '/gold') {
          next.gold = patch.value;
        } else if (patch.path.startsWith('/attributes/')) {
          const attrKey = patch.path.replace('/attributes/', '');
          next.attributes = { ...next.attributes, [attrKey]: patch.value };
        } else if (patch.path === '/attributes') {
          next.attributes = { ...(patch.value || {}) };
        } else if (patch.path.startsWith('/variables/')) {
          const varKey = patch.path.replace('/variables/', '');
          next.variables = { ...next.variables, [varKey]: patch.value };
        } else if (patch.path === '/inventory') {
          next.inventory = Array.isArray(patch.value) ? patch.value : [];
        } else if (patch.path === '/inventory/-') {
          next.inventory = [...next.inventory, patch.value];
        }
      }
      return next;
    });
  };

  // 2. 发起游戏回合执行 (AG-UI SSE 协议通信)
  const executeTurn = async (
    userPrompt: string,
    checkContext?: DiceCheckEvent,
    actionMeta?: { action_id?: string; check_passed?: boolean }
  ) => {
    if (!playerState || isStreaming) return;

    // 记录玩家操作到消息流
    const userMsgId = `user-${Date.now()}`;
    const newMessages: StoryMessage[] = [
      ...messages,
      {
        id: userMsgId,
        kind: 'user',
        content: checkContext
          ? `${userPrompt} (掷骰 D20: ${checkContext.roll} -> ${checkContext.isSuccess ? '成功' : '失败'})`
          : userPrompt,
        timestamp: Date.now(),
      },
    ];
    setMessages(newMessages);

    setIsStreaming(true);
    setStreamingText('');

    const runId = `run-${Date.now()}`;
    const payload = {
      thread_id: threadIdRef.current,
      run_id: runId,
      messages: [
        {
          id: `msg-${Date.now()}`,
          role: 'user',
          content: [
            {
              type: 'text',
              text: checkContext
                ? `${userPrompt}\n[检定数据: ${checkContext.skill} 检定，投出 D20 = ${checkContext.roll}，难度 DC = ${checkContext.difficulty}，判定为 ${checkContext.isSuccess ? '成功' : '失败'}]`
                : userPrompt,
            },
          ],
        },
      ],
      forwarded_props: {
        scenario_id: scenarioId,
        ...(actionMeta || {}),
      },
    };

    try {
      const response = await fetch('/api/play/run', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok || !response.body) {
        throw new Error(`HTTP error ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      let accumulatedText = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('data: ')) continue;
          const jsonStr = trimmed.slice(6);
          try {
            const event = JSON.parse(jsonStr);

            if (event.type === 'TEXT_MESSAGE_CONTENT' && event.delta) {
              accumulatedText += event.delta;
              setStreamingText(accumulatedText);
            } else if (event.type === 'STATE_DELTA' && event.delta) {
              applyStateDeltas(event.delta);
            }
          } catch {
            // ignore non-json chunk
          }
        }
      }

      // 提取过滤 state_delta 代码块后的干净文本
      const cleanText = accumulatedText
        .replace(/```state_delta[\s\S]*?```/g, '')
        .trim();

      const displayText =
        cleanText ||
        '你环顾四周，海浪持续拍打着岩滩。当前行动已由地下城主完成记录并推演，世界状态已更新。';

      // 判断是否以 NPC 对话为主
      const isDialogue = displayText.includes('“') && displayText.includes('”');
      setMessages((prev) => [
        ...prev,
        {
          id: `assistant-${Date.now()}`,
          kind: isDialogue ? 'dialogue' : 'narrator',
          speaker: isDialogue ? currentScene?.npcs?.[0]?.name : undefined,
          content: displayText,
          timestamp: Date.now(),
        },
      ]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: `error-${Date.now()}`,
          kind: 'system',
          content: `通信异常: ${err.message || '未知错误'}`,
          timestamp: Date.now(),
        },
      ]);
    } finally {
      setIsStreaming(false);
      setStreamingText('');
    }
  };

  // 处理预设场景行动
  const handleSelectAction = (action: ActionOption) => {
    if (action.type === 'check' && action.skill && action.difficulty) {
      // 掷骰 D20
      const roll = Math.floor(Math.random() * 20) + 1;
      const isSuccess = roll >= action.difficulty;
      const event: DiceCheckEvent = {
        skill: action.skill,
        difficulty: action.difficulty,
        roll,
        total: roll,
        isSuccess,
        message: isSuccess
          ? (action.on_success?.message as string) || '你成功发现了关键线索！'
          : (action.on_failure?.message as string) || '未发现异常。',
      };
      setDiceEvent(event);

      // 若成功且伴随场景切换，提前切换背景；数值/背包/时间/动态选项由后端 STATE_DELTA 权威下发
      if (isSuccess && action.on_success?.transition_scene) {
        applyStateDeltas([
          {
            op: 'replace',
            path: '/current_scene',
            value: action.on_success.transition_scene,
          },
        ]);
      }

      executeTurn(`【执行检定】${action.label}`, event, {
        action_id: action.id,
        check_passed: isSuccess,
      });
    } else if (action.type === 'interact') {
      executeTurn(`【收集/互动】${action.label}`, undefined, {
        action_id: action.id,
        check_passed: true,
      });
    } else if (action.type === 'transition' && action.target_scene) {
      // 场景转换
      applyStateDeltas([
        { op: 'replace', path: '/current_scene', value: action.target_scene },
      ]);
      executeTurn(`【转移场景】${action.label}`, undefined, {
        action_id: action.id,
      });
    } else {
      executeTurn(`【行动】${action.label}`, undefined, {
        action_id: action.id,
      });
    }
  };

  if (!playerState || !scenario) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-slate-400">
        <div className="w-8 h-8 border-2 border-amber-500 border-t-transparent rounded-full animate-spin mb-3" />
        <span className="text-sm font-medium">正在载入剧本与世界状态...</span>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-slate-950">
      {/* 顶部 HUD */}
      <GameHUD
        playerState={playerState}
        currentSceneTitle={currentScene?.title || currentSceneId}
        onResetGame={() => handleResetGame()}
      />

      {/* 剧情主视窗与立绘图层 */}
      <StoryStream
        messages={messages}
        currentScene={effectiveScene}
        streamingText={streamingText}
        isStreaming={isStreaming}
      />

      {/* 底部行动与决策面板 */}
      <ActionPanel
        actions={effectiveActions}
        onSelectAction={handleSelectAction}
        onSubmitCustomAction={(text) => executeTurn(text)}
        isStreaming={isStreaming}
        diceEvent={diceEvent}
        onDismissDice={() => setDiceEvent(null)}
      />
    </div>
  );
}
