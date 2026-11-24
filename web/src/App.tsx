import { useState, useEffect } from 'react';
import PlayView from './components/play/PlayView';
import StudioView from './components/studio/StudioView';
import { BookOpen } from 'lucide-react';

interface ScenarioItem {
  id: string;
  title: string;
}

export default function App() {
  const [mode, setMode] = useState<'play' | 'studio'>('play');
  const [selectedScenario, setSelectedScenario] = useState('island_survival');
  const [scenarioItems, setScenarioItems] = useState<ScenarioItem[]>([
    { id: 'island_survival', title: '🏝️ 荒岛余生' },
    { id: 'wow_elwynn_rpg', title: '⚔️ 艾泽拉斯传说：法戈第矿洞之影' },
    { id: 'black_crow_manor', title: '🏰 黑鸦公馆之夜' },
  ]);

  const fetchScenarios = () => {
    fetch('/api/scenarios')
      .then((res) => res.json())
      .then((data) => {
        if (data.items && Array.isArray(data.items) && data.items.length > 0) {
          const formatted: ScenarioItem[] = data.items.map((it: any) => {
            let prefix = '📜 ';
            if (it.id === 'island_survival') prefix = '🏝️ ';
            else if (it.id === 'wow_elwynn_rpg') prefix = '⚔️ ';
            else if (it.id === 'black_crow_manor') prefix = '🏰 ';
            return {
              id: it.id,
              title: it.title.startsWith('🏝️') || it.title.startsWith('⚔️') || it.title.startsWith('🏰') || it.title.startsWith('📜')
                ? it.title
                : `${prefix}${it.title}`,
            };
          });
          setScenarioItems(formatted);
          if (formatted.some((s) => s.id === selectedScenario)) {
            // keep current
          } else if (formatted.some((s) => s.id === 'island_survival')) {
            setSelectedScenario('island_survival');
          } else {
            setSelectedScenario(formatted[0].id);
          }
        } else if (data.scenarios && Array.isArray(data.scenarios)) {
          const list: ScenarioItem[] = data.scenarios.map((id: string) => ({
            id,
            title: id === 'island_survival' ? '🏝️ 荒岛余生' : id === 'wow_elwynn_rpg' ? '⚔️ 艾泽拉斯传说：法戈第矿洞之影' : id === 'black_crow_manor' ? '🏰 黑鸦公馆之夜' : `📜 ${id}`,
          }));
          setScenarioItems(list);
        }
      })
      .catch((e) => console.error(e));
  };

  useEffect(() => {
    fetchScenarios();

    // 监听外部或 Studio 新建/导入剧本事件，自动刷新剧本下拉列表
    const handleUpdate = () => fetchScenarios();
    window.addEventListener('ag_slg_scenario_updated', handleUpdate);
    return () => window.removeEventListener('ag_slg_scenario_updated', handleUpdate);
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
          <div className="flex items-center gap-1.5 text-xs text-slate-300 bg-slate-900/90 px-2.5 py-1 rounded-md border border-slate-700/60 shadow-sm">
            <BookOpen className="w-3.5 h-3.5 text-amber-400 shrink-0" />
            <select
              value={selectedScenario}
              onChange={(e) => setSelectedScenario(e.target.value)}
              className="bg-transparent text-amber-300 font-medium text-xs focus:outline-none cursor-pointer pr-1"
            >
              {scenarioItems.map((s) => (
                <option key={s.id} value={s.id} className="bg-slate-900 text-slate-200">
                  {s.title}
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
          <PlayView key={selectedScenario} scenarioId={selectedScenario} isActive={mode === 'play'} />
        </div>
        <div className={`flex-1 flex flex-col h-full w-full ${mode === 'studio' ? '' : 'hidden'}`}>
          <StudioView key={selectedScenario} scenarioId={selectedScenario} />
        </div>
      </main>

    </div>
  );
}
