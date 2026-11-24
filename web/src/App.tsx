import { useState, useEffect } from 'react';
import PlayView from './components/play/PlayView';
import StudioView from './components/studio/StudioView';
import { BookOpen } from 'lucide-react';

export default function App() {
  const [mode, setMode] = useState<'play' | 'studio'>('play');
  const [selectedScenario, setSelectedScenario] = useState('island_survival');
  const [scenarios, setScenarios] = useState<string[]>(['island_survival', 'black_crow_manor']);

  useEffect(() => {
    fetch('/api/scenarios')
      .then((res) => res.json())
      .then((data) => {
        if (data.scenarios && Array.isArray(data.scenarios)) {
          setScenarios(data.scenarios);
          if (data.scenarios.includes('island_survival')) {
            setSelectedScenario('island_survival');
          }
        }
      })
      .catch((e) => console.error(e));
  }, []);

  return (
    <div className="flex flex-col h-screen bg-[#0f1117] text-slate-100">
      <header className="flex items-center justify-between px-6 py-2.5 border-b border-slate-800 bg-[#141720] z-30 select-none">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="text-xl font-black tracking-wider text-amber-500 font-serif">
              AG-SLG
            </span>
            <span className="text-[10px] font-mono tracking-tight uppercase bg-amber-500/10 text-amber-400 px-2 py-0.5 rounded border border-amber-500/30">
              AG-UI Protocol
            </span>
          </div>

          <div className="h-4 w-px bg-slate-800 hidden sm:block" />

          {/* 剧本选择器 */}
          <div className="flex items-center gap-1.5 text-xs text-slate-300 bg-slate-900/90 px-2.5 py-1 rounded-md border border-slate-700/60">
            <BookOpen className="w-3.5 h-3.5 text-amber-400" />
            <select
              value={selectedScenario}
              onChange={(e) => setSelectedScenario(e.target.value)}
              className="bg-transparent text-amber-300 font-medium text-xs focus:outline-none cursor-pointer"
            >
              {scenarios.map((s) => (
                <option key={s} value={s} className="bg-slate-900 text-slate-200">
                  {s === 'island_survival' ? '🏝️ 荒岛余生' : s === 'black_crow_manor' ? '🏰 黑鸦公馆之夜' : s}
                </option>
              ))}
            </select>
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

      <main className="flex-1 flex overflow-hidden relative">
        <div className={`flex-1 flex flex-col h-full w-full ${mode === 'play' ? '' : 'hidden'}`}>
          <PlayView scenarioId={selectedScenario} isActive={mode === 'play'} />
        </div>
        <div className={`flex-1 flex flex-col h-full w-full ${mode === 'studio' ? '' : 'hidden'}`}>
          <StudioView scenarioId={selectedScenario} />
        </div>
      </main>

    </div>
  );
}
