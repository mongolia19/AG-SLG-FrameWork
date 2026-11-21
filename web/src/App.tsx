import { useState } from 'react';
import PlayView from './components/play/PlayView';

export default function App() {
  const [mode, setMode] = useState<'play' | 'studio'>('play');
  const [selectedScenario] = useState('black_crow_manor');

  return (
    <div className="flex flex-col h-screen bg-[#0f1117] text-slate-100 select-none">
      <header className="flex items-center justify-between px-6 py-2.5 border-b border-slate-800 bg-[#141720] z-30">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xl font-black tracking-wider text-amber-500 font-serif">
              AG-SLG
            </span>
            <span className="text-[10px] font-mono tracking-tight uppercase bg-amber-500/10 text-amber-400 px-2 py-0.5 rounded border border-amber-500/30">
              AG-UI Protocol
            </span>
          </div>
        </div>

        {/* 模式切换 */}
        <div className="flex items-center gap-1 bg-slate-900/90 p-1 rounded-lg border border-slate-800">
          <button
            onClick={() => setMode('play')}
            className={`px-3.5 py-1 text-xs rounded-md font-medium transition ${
              mode === 'play'
                ? 'bg-amber-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            🎮 运行端 (Play)
          </button>
          <button
            onClick={() => setMode('studio')}
            className={`px-3.5 py-1 text-xs rounded-md font-medium transition ${
              mode === 'studio'
                ? 'bg-indigo-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            ✍️ 工作台 (Studio)
          </button>
        </div>
      </header>

      <main className="flex-1 flex overflow-hidden">
        {mode === 'play' ? (
          <PlayView scenarioId={selectedScenario} />
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center p-6 text-slate-400">
            <div className="text-5xl mb-3">✍️</div>
            <div className="text-base font-semibold text-slate-200">Studio Mode 剧本编排调试端</div>
            <p className="text-xs text-slate-500 mt-1 max-w-sm text-center">
              支持可视化剧本节点树与 Studio Co-pilot 本地 Agent 协创编辑（将于阶段三开放）。
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
