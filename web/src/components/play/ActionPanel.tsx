import { useState } from 'react';
import { ActionOption, DiceCheckEvent } from '../../types';
import { Send, Compass, Eye, Dices, ArrowRight, Loader2, Sparkles } from 'lucide-react';

interface ActionPanelProps {
  actions: ActionOption[];
  onSelectAction: (action: ActionOption) => void;
  onSubmitCustomAction: (text: string) => void;
  isStreaming: boolean;
  diceEvent?: DiceCheckEvent | null;
  onDismissDice?: () => void;
}

export default function ActionPanel({
  actions,
  onSelectAction,
  onSubmitCustomAction,
  isStreaming,
  diceEvent,
  onDismissDice,
}: ActionPanelProps) {
  const [customText, setCustomText] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = customText.trim();
    if (!trimmed || isStreaming) return;
    onSubmitCustomAction(trimmed);
    setCustomText('');
  };

  const getActionIcon = (type: string) => {
    switch (type) {
      case 'check':
        return <Dices className="w-3.5 h-3.5 text-rose-400" />;
      case 'transition':
        return <Compass className="w-3.5 h-3.5 text-cyan-400" />;
      case 'interact':
      default:
        return <Eye className="w-3.5 h-3.5 text-amber-400" />;
    }
  };

  return (
    <div className="bg-[#13161f] border-t border-slate-800 p-4 z-20 shadow-lg">
      <div className="max-w-4xl mx-auto space-y-3">
        {/* D20 检定反馈卡片（若发生检定判定） */}
        {diceEvent && (
          <div className="bg-slate-900 border-2 border-amber-500/70 rounded-xl p-3 shadow-xl animate-in fade-in slide-in-from-bottom-2 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-amber-500/20 border border-amber-500/50 flex items-center justify-center font-bold text-lg text-amber-300">
                {diceEvent.roll}
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-slate-200">
                    {diceEvent.skill.toUpperCase()} 属性检定
                  </span>
                  <span
                    className={`text-[10px] px-2 py-0.5 rounded font-bold uppercase ${
                      diceEvent.isSuccess
                        ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                        : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                    }`}
                  >
                    {diceEvent.isSuccess ? '检定成功 SUCCESS' : '检定失败 FAILURE'}
                  </span>
                </div>
                <div className="text-xs text-slate-400 mt-0.5">
                  投骰值 {diceEvent.roll} (难度 DC: {diceEvent.difficulty}) · {diceEvent.message || ''}
                </div>
              </div>
            </div>
            {onDismissDice && (
              <button
                onClick={onDismissDice}
                className="text-xs text-slate-400 hover:text-slate-200 px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 transition"
              >
                收起
              </button>
            )}
          </div>
        )}

        {/* 预设快捷动作组 */}
        <div>
          <div className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold mb-2 flex items-center gap-1.5">
            <Sparkles className="w-3 h-3 text-amber-400" />
            <span>当前场景可选行动：</span>
          </div>

          <div className="flex flex-wrap gap-2">
            {actions.length === 0 ? (
              <div className="text-xs text-slate-500 italic py-1">当前没有预设行动，可在下方输入自由行动</div>
            ) : (
              actions.map((act) => (
                <button
                  key={act.id}
                  disabled={isStreaming}
                  onClick={() => onSelectAction(act)}
                  className="flex items-center gap-2 px-3.5 py-2 text-xs font-medium bg-slate-800/90 hover:bg-slate-700/90 active:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed text-slate-200 rounded-lg border border-slate-700 hover:border-amber-500/50 shadow-sm transition group"
                >
                  {getActionIcon(act.type)}
                  <span className="group-hover:text-amber-200 transition-colors">{act.label}</span>
                  {act.type === 'check' && act.difficulty && (
                    <span className="text-[10px] text-slate-400 font-mono bg-slate-900 px-1 rounded">
                      DC {act.difficulty}
                    </span>
                  )}
                  <ArrowRight className="w-3 h-3 text-slate-500 group-hover:text-amber-400 transition" />
                </button>
              ))
            )}
          </div>
        </div>

        {/* 自由动作输入栏 */}
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            type="text"
            disabled={isStreaming}
            value={customText}
            onChange={(e) => setCustomText(e.target.value)}
            placeholder={
              isStreaming
                ? 'DM 正在推演中，请稍候...'
                : '输入任意行动（例如：“仔细检查地毯边缘”或“向管家出示调查员徽章”）...'
            }
            className="flex-1 bg-slate-900 border border-slate-700/80 rounded-lg px-4 py-2.5 text-xs sm:text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-amber-500 transition disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={isStreaming || !customText.trim()}
            className="flex items-center gap-2 px-5 py-2.5 bg-amber-600 hover:bg-amber-500 active:bg-amber-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium text-xs sm:text-sm rounded-lg shadow-md transition"
          >
            {isStreaming ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <>
                <span>执行</span>
                <Send className="w-3.5 h-3.5" />
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
