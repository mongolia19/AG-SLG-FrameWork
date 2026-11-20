import { useState } from 'react'

export default function App() {
  const [mode, setMode] = useState<'play' | 'studio'>('play')

  return (
    <div className="flex flex-col h-screen bg-[#0f1117] text-slate-100">
      <header className="flex items-center justify-between px-6 py-3 border-b border-slate-800 bg-[#161922]">
        <div className="flex items-center gap-3">
          <span className="text-xl font-bold tracking-wide text-amber-500">AG-SLG</span>
          <span className="text-xs uppercase bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded border border-amber-500/30">
            AG-UI Protocol
          </span>
        </div>
        <div className="flex items-center gap-2 bg-slate-900/80 p-1 rounded-lg border border-slate-800">
          <button
            onClick={() => setMode('play')}
            className={`px-4 py-1.5 text-sm rounded font-medium transition ${
              mode === 'play'
                ? 'bg-amber-600 text-white shadow'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            🎮 Play Mode
          </button>
          <button
            onClick={() => setMode('studio')}
            className={`px-4 py-1.5 text-sm rounded font-medium transition ${
              mode === 'studio'
                ? 'bg-indigo-600 text-white shadow'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            ✍️ Studio Mode
          </button>
        </div>
      </header>

      <main className="flex-1 flex overflow-hidden">
        {mode === 'play' ? (
          <div className="flex-1 flex items-center justify-center p-6 text-slate-400">
            Play Mode Ready - Core AG-UI Bridge connected.
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center p-6 text-slate-400">
            Studio Mode Ready - Authoring Co-pilot connected.
          </div>
        )}
      </main>
    </div>
  )
}
