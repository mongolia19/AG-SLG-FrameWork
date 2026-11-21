import { useState } from 'react';
import { Play, RotateCcw, AlertTriangle, ChevronRight, Terminal } from 'lucide-react';

import { ScenarioSpec } from '../../types';

interface PlaytestLog {
  step: number;
  sceneId: string;
  actionTaken: string;
  result: string;
}

interface PlaytestRunnerProps {
  scenario: ScenarioSpec;
}

export default function PlaytestRunner({ scenario }: PlaytestRunnerProps) {
  const [isRunning, setIsRunning] = useState(false);
  const [logs, setLogs] = useState<PlaytestLog[]>([]);
  const [warningMessage, setWarningMessage] = useState<string | null>(null);

  const startPlaytest = async () => {
    setIsRunning(true);
    setLogs([]);
    setWarningMessage(null);

    let currentSceneId = scenario.world.initial_scene;
    const testLogs: PlaytestLog[] = [];

    // 虚拟玩家模拟 5 步推演
    for (let step = 1; step <= 5; step++) {
      const scene = scenario.scenes[currentSceneId];
      if (!scene) {
        setWarningMessage(`推演在第 ${step} 步中断：无法找到场景 ID '${currentSceneId}'（悬空死锁）`);
        break;
      }

      if (!scene.actions || scene.actions.length === 0) {
        testLogs.push({
          step,
          sceneId: currentSceneId,
          actionTaken: '无可用动作',
          result: '到达死胡同场景，推演顺利收敛。',
        });
        break;
      }

      // 模拟玩家选择第一个可用动作
      const chosenAction = scene.actions[0];
      let nextSceneId = currentSceneId;

      if (chosenAction.type === 'transition' && chosenAction.target_scene) {
        nextSceneId = chosenAction.target_scene;
      } else if (chosenAction.type === 'check' && chosenAction.on_success?.transition_scene) {
        nextSceneId = chosenAction.on_success.transition_scene;
      }

      testLogs.push({
        step,
        sceneId: currentSceneId,
        actionTaken: chosenAction.label,
        result: `执行 [${chosenAction.type}] 行动，推进至场景: ${nextSceneId}`,
      });

      setLogs([...testLogs]);
      currentSceneId = nextSceneId;
      await new Promise((r) => setTimeout(r, 600));
    }

    setIsRunning(false);
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between pb-2 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-emerald-400" />
          <span className="text-xs font-bold text-slate-200 uppercase tracking-wide">
            Agent 自动试玩推演 (Automated Playtest)
          </span>
        </div>

        <button
          onClick={startPlaytest}
          disabled={isRunning}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 disabled:opacity-50 text-white rounded-lg text-xs font-medium transition shadow"
        >
          {isRunning ? (
            <>
              <RotateCcw className="w-3.5 h-3.5 animate-spin" />
              <span>推演中...</span>
            </>
          ) : (
            <>
              <Play className="w-3.5 h-3.5" />
              <span>启动 5 步自动推演</span>
            </>
          )}
        </button>
      </div>

      {warningMessage && (
        <div className="p-2.5 bg-rose-950/60 border border-rose-800/80 rounded-lg text-xs text-rose-300 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
          <span>{warningMessage}</span>
        </div>
      )}

      {logs.length > 0 ? (
        <div className="space-y-1.5 max-h-48 overflow-y-auto">
          {logs.map((log) => (
            <div
              key={log.step}
              className="p-2 bg-slate-950 border border-slate-800/80 rounded-md text-[11px] font-mono flex items-center justify-between"
            >
              <div className="flex items-center gap-2">
                <span className="text-emerald-400 font-bold">Step {log.step}:</span>
                <span className="text-slate-400">[{log.sceneId}]</span>
                <span className="text-slate-200">{log.actionTaken}</span>
              </div>
              <ChevronRight className="w-3.5 h-3.5 text-slate-600" />
              <span className="text-slate-400">{log.result}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-[11px] text-slate-500 italic py-2">
          点击上方按钮，后台将模拟虚拟探索者自动推进剧情分支，以排查剧本卡点与悬空跳转。
        </div>
      )}
    </div>
  );
}
