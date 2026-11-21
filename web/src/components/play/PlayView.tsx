import { useState, useEffect, useRef } from 'react';
import {
  PlayerState,
  ScenarioSpec,
  SceneNode,
  StoryMessage,
  ActionOption,
  DiceCheckEvent,
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

  // 会话与运行 ID
  const threadIdRef = useRef<string>(`session-${Date.now()}`);

  // 1. 加载剧本
  useEffect(() => {
    fetch(`/api/scenarios/${scenarioId}`)
      .then((res) => {
        if (!res.ok) throw new Error('Failed to load scenario');
        return res.json();
      })
      .then((data: ScenarioSpec) => {
        setScenario(data);
        const initPlayer = data.world.initial_player_state;
        setPlayerState({
          ...initPlayer,
          current_scene: initPlayer.current_scene || data.world.initial_scene,
        });

        // 初始开场白消息
        setMessages([
          {
            id: 'init-msg',
            kind: 'narrator',
            content: `暴风雨笼罩着荒凉的群山，古老的${data.world.title}如同一头黑色的巨兽盘踞在悬崖之上。\n你作为${initPlayer.name}，踏上了通往公馆大门的石阶……`,
            timestamp: Date.now(),
          },
        ]);
      })
      .catch((err) => {
        console.error(err);
      });
  }, [scenarioId]);

  const currentSceneId = playerState?.current_scene || scenario?.world.initial_scene || '';
  const currentScene: SceneNode | undefined = scenario?.scenes[currentSceneId];

  // 辅助函数：应用 JSON-Patch 状态变化
  const applyStateDeltas = (patches: Array<{ op: string; path: string; value: any }>) => {
    setPlayerState((prev) => {
      if (!prev) return prev;
      const next = { ...prev };
      for (const patch of patches) {
        if (patch.path === '/current_scene') {
          next.current_scene = patch.value;
        } else if (patch.path === '/hp') {
          next.hp = patch.value;
        } else if (patch.path === '/san') {
          next.san = patch.value;
        } else if (patch.path === '/gold') {
          next.gold = patch.value;
        } else if (patch.path.startsWith('/variables/')) {
          const varKey = patch.path.replace('/variables/', '');
          next.variables = { ...next.variables, [varKey]: patch.value };
        } else if (patch.path === '/inventory/-') {
          next.inventory = [...(next.inventory || []), patch.value];
        }
      }
      return next;
    });
  };

  // 2. 发起游戏回合执行 (AG-UI SSE 协议通信)
  const executeTurn = async (userPrompt: string, checkContext?: DiceCheckEvent) => {
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
      forwarded_props: { scenario_id: scenarioId },
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

      if (cleanText) {
        // 判断是否以 NPC 对话为主
        const isDialogue = cleanText.includes('“') && cleanText.includes('”');
        setMessages((prev) => [
          ...prev,
          {
            id: `assistant-${Date.now()}`,
            kind: isDialogue ? 'dialogue' : 'narrator',
            speaker: isDialogue ? currentScene?.npcs?.[0]?.name : undefined,
            content: cleanText,
            timestamp: Date.now(),
          },
        ]);
      }
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

      // 如果有即时动作奖励或场景转换，先在前端触发乐观更新
      if (isSuccess && action.on_success) {
        const patches: any[] = [];
        if (action.on_success.transition_scene) {
          patches.push({
            op: 'replace',
            path: '/current_scene',
            value: action.on_success.transition_scene,
          });
        }
        if (action.on_success.gain_item) {
          patches.push({
            op: 'add',
            path: '/inventory/-',
            value: {
              id: action.on_success.gain_item,
              name: action.on_success.gain_item,
            },
          });
        }
        if (patches.length > 0) {
          applyStateDeltas(patches);
        }
      }

      executeTurn(`【执行检定】${action.label}`, event);
    } else if (action.type === 'transition' && action.target_scene) {
      // 场景转换
      applyStateDeltas([
        { op: 'replace', path: '/current_scene', value: action.target_scene },
      ]);
      executeTurn(`【转移场景】${action.label}`);
    } else {
      executeTurn(`【行动】${action.label}`);
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
      />

      {/* 剧情主视窗与立绘图层 */}
      <StoryStream
        messages={messages}
        currentScene={currentScene}
        streamingText={streamingText}
        isStreaming={isStreaming}
      />

      {/* 底部行动与决策面板 */}
      <ActionPanel
        actions={currentScene?.actions || []}
        onSelectAction={handleSelectAction}
        onSubmitCustomAction={(text) => executeTurn(text)}
        isStreaming={isStreaming}
        diceEvent={diceEvent}
        onDismissDice={() => setDiceEvent(null)}
      />
    </div>
  );
}
