import { useState, useEffect } from 'react';
import { ScenarioSpec, SceneNode, LintReport } from '../../types';
import ScenarioTree from './ScenarioTree';
import AuthoringChat from './AuthoringChat';
import PlaytestRunner from './PlaytestRunner';
import { AlertCircle, CheckCircle, RefreshCw, ShieldCheck } from 'lucide-react';

interface StudioViewProps {
  scenarioId?: string;
}

export default function StudioView({ scenarioId = 'black_crow_manor' }: StudioViewProps) {
  const [scenario, setScenario] = useState<ScenarioSpec | null>(null);
  const [selectedSceneId, setSelectedSceneId] = useState<string>('');
  const [lintReport, setLintReport] = useState<LintReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // 加载剧本数据与 Lint 报告
  const loadScenarioData = async () => {
    setIsLoading(true);
    try {
      const res = await fetch(`/api/scenarios/${scenarioId}`);
      if (!res.ok) throw new Error('Failed to load scenario');
      const data: ScenarioSpec = await res.json();
      setScenario(data);
      if (!selectedSceneId && data.world.initial_scene) {
        setSelectedSceneId(data.world.initial_scene);
      }

      // 请求 Lint 报告
      const lintRes = await fetch(`/api/scenarios/${scenarioId}/lint`);
      if (lintRes.ok) {
        const report: LintReport = await lintRes.json();
        setLintReport(report);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadScenarioData();
  }, [scenarioId]);

  // 保存场景修改
  const handleSaveScene = async (scene: SceneNode) => {
    try {
      const res = await fetch(`/api/scenarios/${scenarioId}/scenes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(scene),
      });
      if (res.ok) {
        await loadScenarioData();
      }
    } catch (err) {
      console.error(err);
    }
  };

  if (isLoading || !scenario) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-slate-400">
        <RefreshCw className="w-6 h-6 animate-spin text-indigo-500 mb-2" />
        <span className="text-xs">正在载入 Studio 剧本工作台...</span>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      {/* 顶部体检状态条 (Lint Status Banner) */}
      <div className="bg-[#141824] border-b border-slate-800 px-6 py-2 flex items-center justify-between text-xs">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 font-medium text-slate-300">
            <ShieldCheck className="w-4 h-4 text-indigo-400" />
            <span>剧本逻辑体检:</span>
          </div>

          {lintReport ? (
            lintReport.valid ? (
              <span className="flex items-center gap-1 text-emerald-400 font-medium bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-800/40">
                <CheckCircle className="w-3.5 h-3.5" />
                <span>所有场景跳转连通无死锁 (0 致命错误)</span>
              </span>
            ) : (
              <span className="flex items-center gap-1 text-rose-400 font-medium bg-rose-950/40 px-2 py-0.5 rounded border border-rose-800/40">
                <AlertCircle className="w-3.5 h-3.5" />
                <span>发现 {lintReport.errors} 个跳转死锁或未定义场景</span>
              </span>
            )
          ) : (
            <span className="text-slate-500">检测中...</span>
          )}

          {lintReport && lintReport.warnings > 0 && (
            <span className="text-amber-400/90 text-[11px]">
              ({lintReport.warnings} 条建议优化)
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={loadScenarioData}
            className="flex items-center gap-1 text-slate-400 hover:text-slate-200 text-xs px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 transition"
          >
            <RefreshCw className="w-3 h-3" />
            <span>热重载剧本</span>
          </button>
        </div>
      </div>

      {/* 工作区主体：左/中为场景树与详情，右为 Agent 协创 */}
      <div className="flex-1 flex overflow-hidden">
        {/* 左侧场景管理与中央编辑区 */}
        <div className="flex-1 flex flex-col h-full overflow-hidden">
          <div className="flex-1 flex overflow-hidden">
            <ScenarioTree
              scenario={scenario}
              selectedSceneId={selectedSceneId}
              onSelectScene={(id) => setSelectedSceneId(id)}
              onSaveScene={handleSaveScene}
              onRefresh={loadScenarioData}
            />
          </div>

          {/* 底部自动推演抽屉 */}
          <div className="p-4 bg-[#0d1017] border-t border-slate-800">
            <PlaytestRunner scenario={scenario} />
          </div>
        </div>

        {/* 右侧：Studio Co-pilot 编剧助手 */}
        <AuthoringChat
          scenarioId={scenarioId}
          onScenarioUpdated={loadScenarioData}
        />
      </div>
    </div>
  );
}
