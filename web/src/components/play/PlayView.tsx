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
import { evaluateActionCondition } from '../../utils/conditions';

interface PlayViewProps {
  scenarioId?: string;
  isActive?: boolean;
}

export default function PlayView({
  scenarioId = 'black_crow_manor',
  isActive = true,
}: PlayViewProps) {
  const [scenario, setScenario] = useState<ScenarioSpec | null>(null);
  const [playerState, setPlayerState] = useState<PlayerState | null>(null);
  const [messages, setMessages] = useState<StoryMessage[]>([]);
  const [streamingText, setStreamingText] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [diceEvent, setDiceEvent] = useState<DiceCheckEvent | null>(null);
  const [activeVisuals, setActiveVisuals] = useState<VisualLayer | null>(null);
  const [dynamicActions, setDynamicActions] = useState<ActionOption[] | null>(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncFeedback, setSyncFeedback] = useState<string | null>(null);

  // 会话与运行 ID
  const threadIdRef = useRef<string>(`session-${scenarioId}-${Date.now()}`);
  const latestSceneIdRef = useRef<string>('');

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
      outfit: initPlayer.outfit ? { ...initPlayer.outfit } : {},
      skills: Array.isArray(initPlayer.skills) ? [...initPlayer.skills] : [],
      hud_widgets: Array.isArray(initPlayer.hud_widgets)
        ? initPlayer.hud_widgets.map((w) => ({ ...w }))
        : [],
      current_scene: initPlayer.current_scene || sc.world.initial_scene,
    });

    const initialSceneNode = sc.scenes[initPlayer.current_scene || sc.world.initial_scene];
    const openingText =
      sc.world.opening_narration?.trim() ||
      initialSceneNode?.description?.trim() ||
      `欢迎来到【${sc.world.title}】，你作为 ${initPlayer.name} 开始了这段旅程。`;

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

  // 根据已选职业回填技能卡片（兼容旧存档或同步剧本后立即展示技能栏卡片）
  const hydrateMissingSkills = (
    state: PlayerState,
    spec: ScenarioSpec
  ): PlayerState['skills'] => {
    if (Array.isArray(state.skills) && state.skills.length > 0) {
      return state.skills;
    }
    const vars = state.variables || {};
    if (!vars.class_selected || !vars.class_id) {
      return state.skills || [];
    }
    const classId = String(vars.class_id);
    for (const scene of Object.values(spec.scenes || {})) {
      for (const act of scene.actions || []) {
        const onSuccess = act.on_success as Record<string, any> | undefined;
        if (
          onSuccess?.variables?.class_id === classId &&
          Array.isArray(onSuccess.skills) &&
          onSuccess.skills.length > 0
        ) {
          const rank = Number(vars.skill_rank || vars.level || 1);
          return onSuccess.skills.map((sk: any) => ({
            ...sk,
            level: rank > 1 ? rank : sk.level ?? 1,
            tag:
              rank > 1 && typeof sk.tag === 'string'
                ? sk.tag.replace(/Lv\.\d+/g, `Lv.${rank}`)
                : sk.tag,
          }));
        }
      }
    }
    return state.skills || [];
  };

  // 兼容旧存档与 Studio 同步：补齐新增的血量上限、魔法槽位及剧本初始变量
  const hydrateMissingStateDefaults = (
    state: PlayerState,
    spec: ScenarioSpec
  ): PlayerState => {
    const init = spec.world.initial_player_state;
    const mergedVars: Record<string, any> = {
      ...(init.variables || {}),
      ...(state.variables || {}),
    };
    const nextMaxHp =
      state.max_hp && state.max_hp > 0
        ? state.max_hp
        : init.max_hp && init.max_hp > 0
          ? init.max_hp
          : 100;
    const hasInitMp = init.mp !== undefined && init.mp !== null;
    const nextMaxMp =
      state.max_mp !== undefined && state.max_mp !== null
        ? state.max_mp
        : hasInitMp
          ? init.max_mp ?? 100
          : state.max_mp;
    const nextMp =
      state.mp !== undefined && state.mp !== null
        ? state.mp
        : hasInitMp
          ? init.mp
          : state.mp;

    const hydrated: PlayerState = {
      ...state,
      max_hp: nextMaxHp,
      mp: nextMp,
      max_mp: nextMaxMp,
      outfit: state.outfit ?? init.outfit ?? {},
      skills: state.skills ?? init.skills ?? [],
      hud_widgets: state.hud_widgets ?? init.hud_widgets ?? [],
      variables: mergedVars,
    };
    hydrated.skills = hydrateMissingSkills(hydrated, spec);
    return hydrated;
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
            const isValidScenarioMatch =
              saved &&
              (!saved.scenarioId || saved.scenarioId === scenarioId) &&
              saved.playerState &&
              data.scenes[saved.playerState.current_scene] &&
              Array.isArray(saved.messages) &&
              saved.messages.length > 0;

            if (isValidScenarioMatch) {
              const restoredState = hydrateMissingStateDefaults(saved.playerState, data);
              setPlayerState(restoredState);
              setMessages(saved.messages);
              setActiveVisuals(saved.activeVisuals || null);
              setDynamicActions(saved.dynamicActions || null);
              threadIdRef.current = saved.threadId || `session-${scenarioId}-${Date.now()}`;
              return;
            } else {
              console.warn(`Saved state for ${scenarioId} is invalid or from another scenario, reinitializing.`);
              localStorage.removeItem(`ag_slg_save_${scenarioId}`);
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

  // 静默同步 Studio 最新的剧本与场景修改，保持玩家已有背包、属性与剧情历史
  const refreshScenario = async (showNotice = false) => {
    setIsSyncing(true);
    try {
      const res = await fetch(`/api/scenarios/${scenarioId}`);
      if (res.ok) {
        const data: ScenarioSpec = await res.json();
        setScenario(data);
        setPlayerState((prev) => {
          if (!prev) return prev;
          return hydrateMissingStateDefaults(prev, data);
        });
        if (showNotice) {
          setSyncFeedback('已同步 Studio 最新修改');
          setTimeout(() => setSyncFeedback(null), 2500);
        }
      }
    } catch (e) {
      console.warn('Live sync scenario failed:', e);
    } finally {
      setIsSyncing(false);
    }
  };

  // 1.1 当从 Studio 切换到 Play 模式时，立即静默拉取最新剧本
  const isFirstRender = useRef(true);
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    if (isActive) {
      refreshScenario(true);
    }
  }, [isActive]);

  // 1.2 监听 Studio 场景保存或导入的广播事件，即时同步
  useEffect(() => {
    const handleUpdate = (e: any) => {
      if (!e.detail?.scenarioId || e.detail.scenarioId === scenarioId) {
        refreshScenario(true);
      }
    };
    window.addEventListener('ag_slg_scenario_updated', handleUpdate);
    return () => window.removeEventListener('ag_slg_scenario_updated', handleUpdate);
  }, [scenarioId]);

  // 自动将进度写回 LocalStorage，确保切换模式或刷新页面绝不丢状态
  useEffect(() => {
    if (!scenario || !playerState || messages.length === 0) return;
    // 关键防御：如果当前在内存中的剧本世界 ID 与当前 scenarioId 不一致，严禁串写存档
    if (scenario.world.id !== scenarioId) return;
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
  latestSceneIdRef.current = currentSceneId;
  const currentScene: SceneNode | undefined = scenario?.scenes[currentSceneId];

  const effectiveActions: ActionOption[] =
    dynamicActions !== null
      ? dynamicActions
      : (currentScene?.actions || []).filter((act) =>
          evaluateActionCondition(act.condition, playerState)
        );

  // 动态合成视觉图层（剧本静态配置 + 条件建造设施 + Agent 在线调度）
  const rawSceneDecorations =
    activeVisuals?.decorations ||
    currentScene?.visuals?.decorations ||
    currentScene?.decorations ||
    [];

  const filteredSceneDecorations = rawSceneDecorations.filter((dec) =>
    evaluateActionCondition(dec.condition, playerState)
  );

  const dynamicBuiltStructures = Array.isArray(playerState?.variables?.built_structures)
    ? playerState!.variables.built_structures
        .filter(
          (item: any) =>
            item &&
            typeof item === 'object' &&
            item.id &&
            item.image &&
            item.scene_id === currentScene?.id &&
            !filteredSceneDecorations.some((d) => d.id === item.id)
        )
        .map((item: any) => ({
          id: String(item.id),
          name: String(item.name || item.id),
          image: String(item.image),
          side: (item.side === 'right' ? 'right' : 'left') as 'left' | 'right',
          caption: item.caption ? String(item.caption) : String(item.name || item.id),
          tooltip: item.tooltip ? String(item.tooltip) : '',
          category: String(item.category || 'structure'),
          tag: String(item.tag || '已建成'),
        }))
    : [];

  const mergedDecorations = [...dynamicBuiltStructures, ...filteredSceneDecorations];

  const effectiveScene: SceneNode | undefined = currentScene
    ? {
        ...currentScene,
        visuals: {
          ...(currentScene.visuals || {}),
          ...(activeVisuals || {}),
          decorations: mergedDecorations,
        },
        background: activeVisuals?.background || currentScene.visuals?.background || currentScene.background,
        foreground: activeVisuals?.foreground !== undefined ? activeVisuals.foreground : (currentScene.visuals?.foreground || currentScene.foreground),
        hero_image: activeVisuals?.hero_image !== undefined ? activeVisuals.hero_image : (currentScene.visuals?.hero_image || currentScene.hero_image),
        decorations: mergedDecorations,
      }
    : undefined;

  // 辅助函数：应用 JSON-Patch 状态变化
  const applyStateDeltas = (patches: Array<{ op: string; path: string; value: any }>) => {
    let sceneSwitched = false;
    let hasCheckResult = false;
    let nextVisualsPatch: VisualLayer | null = null;
    let nextDynamicActions: ActionOption[] | null | undefined = undefined;

    for (const patch of patches) {
      if (patch.path === '/current_scene') {
        sceneSwitched = true;
        if (typeof patch.value === 'string' && patch.value) {
          latestSceneIdRef.current = patch.value;
        }
      } else if (patch.path === '/visuals') {
        nextVisualsPatch = patch.value;
      } else if (patch.path === '/available_actions') {
        nextDynamicActions = Array.isArray(patch.value) ? patch.value : null;
      } else if (patch.path === '/check_result' && patch.value) {
        hasCheckResult = true;
        setDiceEvent(patch.value);
      }
    }

    if (sceneSwitched && !hasCheckResult) {
      setDiceEvent(null);
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
        outfit: { ...(prev.outfit || {}) },
        skills: [...(prev.skills || [])],
        hud_widgets: [...(prev.hud_widgets || [])],
      };
      for (const patch of patches) {
        if (patch.path === '/current_scene') {
          next.current_scene = patch.value;
        } else if (patch.path === '/hp') {
          next.hp = patch.value;
        } else if (patch.path === '/max_hp') {
          next.max_hp = patch.value;
        } else if (patch.path === '/mp') {
          next.mp = patch.value;
        } else if (patch.path === '/max_mp') {
          next.max_mp = patch.value;
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
        } else if (patch.path === '/outfit') {
          next.outfit = patch.value && typeof patch.value === 'object' ? { ...patch.value } : {};
        } else if (patch.path.startsWith('/outfit/')) {
          const slotKey = patch.path.replace('/outfit/', '');
          const nextOutfit = { ...(next.outfit || {}) };
          if (patch.op === 'remove' || !patch.value) {
            delete nextOutfit[slotKey];
          } else {
            nextOutfit[slotKey] = patch.value;
          }
          next.outfit = nextOutfit;
        } else if (patch.path === '/skills') {
          next.skills = Array.isArray(patch.value) ? patch.value : [];
        } else if (patch.path === '/skills/-') {
          next.skills = [...(next.skills || []), patch.value];
        } else if (patch.path === '/hud_widgets') {
          next.hud_widgets = Array.isArray(patch.value) ? patch.value : [];
        }
      }
      return next;
    });
  };

  // 2. 发起游戏回合执行 (AG-UI SSE 协议通信)
  const executeTurn = async (
    userPrompt: string,
    checkContext?: DiceCheckEvent,
    actionMeta?: { action_id?: string; check_passed?: boolean; client_roll?: number }
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
          ? `${userPrompt} (掷骰 D20: ${checkContext.roll})`
          : userPrompt,
        timestamp: Date.now(),
      },
    ];
    setMessages(newMessages);

    setIsStreaming(true);
    setStreamingText('');

    const recentHistory = messages.slice(-8).map((m) => ({
      role: m.kind === 'user' ? 'user' : 'assistant',
      content: m.content,
    }));

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
                ? `${userPrompt}\n[检定数据: ${checkContext.skill} 检定，投出 D20 = ${checkContext.roll}，难度 DC = ${checkContext.difficulty}，请DM综合当前玩家状态、着装、道具与剧情做出裁决]`
                : userPrompt,
            },
          ],
        },
      ],
      forwarded_props: {
        scenario_id: scenarioId,
        player_state: playerState,
        recent_history: recentHistory,
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
        '你仔细察看着周遭的动静。当前行动已由地下城主完成记录并推演，世界状态已更新。';

      // 判断是否以 NPC 对话为主
      const isDialogue = displayText.includes('“') && displayText.includes('”');
      const resolvedScene = scenario?.scenes[latestSceneIdRef.current] || currentScene;
      setMessages((prev) => [
        ...prev,
        {
          id: `assistant-${Date.now()}`,
          kind: isDialogue ? 'dialogue' : 'narrator',
          speaker: isDialogue ? resolvedScene?.npcs?.[0]?.name : undefined,
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
      const initialEvent: DiceCheckEvent = {
        skill: action.skill,
        difficulty: action.difficulty,
        roll,
        total: roll,
        isSuccess: roll >= action.difficulty,
        outcome_label: '裁决中...',
        reason: '计算中...',
        message: '已投出 D20 骰子，地下城主正综合当前角色生理状态、随身装备与环境给出综合裁决...',
      };
      setDiceEvent(initialEvent);

      executeTurn(`【执行检定】${action.label}`, initialEvent, {
        action_id: action.id,
        client_roll: roll,
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
        world={scenario.world}
        currentSceneTitle={currentScene?.title || currentSceneId}
        onResetGame={() => handleResetGame()}
        onSyncScenario={() => refreshScenario(true)}
        isSyncing={isSyncing}
        syncFeedback={syncFeedback}
      />

      {/* 剧情主视窗与立绘图层 */}
      <StoryStream
        messages={messages}
        currentScene={effectiveScene}
        streamingText={streamingText}
        isStreaming={isStreaming}
        weather={playerState.variables?.weather}
        weatherType={playerState.variables?.weather_type}
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
