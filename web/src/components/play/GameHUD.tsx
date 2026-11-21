import { useState } from 'react';
import { PlayerState, InventoryItem } from '../../types';
import { Heart, Brain, Coins, Backpack, MapPin, X, ShieldAlert } from 'lucide-react';

interface GameHUDProps {
  playerState: PlayerState;
  currentSceneTitle: string;
}

export default function GameHUD({ playerState, currentSceneTitle }: GameHUDProps) {
  const [showInventory, setShowInventory] = useState(false);
  const [hoveredItem, setHoveredItem] = useState<InventoryItem | null>(null);

  const hpPercent = Math.max(0, Math.min(100, playerState.hp));
  const sanPercent = Math.max(0, Math.min(100, playerState.san));

  return (
    <>
      <header className="flex flex-wrap items-center justify-between px-6 py-2.5 bg-slate-900/90 border-b border-slate-800 text-slate-100 shadow-md backdrop-blur z-20">
        {/* 左侧：角色信息与当前场景 */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-amber-400 text-sm">{playerState.name}</span>
            <span className="text-xs text-slate-500 font-mono">
              [STR:{playerState.attributes?.strength || 10} AGI:{playerState.attributes?.agility || 10} INT:{playerState.attributes?.intelligence || 10}]
            </span>
          </div>

          <div className="h-4 w-px bg-slate-700" />

          <div className="flex items-center gap-1.5 text-xs text-slate-300 bg-slate-800/80 px-2.5 py-1 rounded-md border border-slate-700/60">
            <MapPin className="w-3.5 h-3.5 text-rose-400" />
            <span className="font-medium text-slate-200">{currentSceneTitle || playerState.current_scene}</span>
          </div>
        </div>

        {/* 中间：HP 与 SAN 条 */}
        <div className="flex items-center gap-6 my-1 sm:my-0">
          {/* HP */}
          <div className="flex items-center gap-2">
            <Heart className="w-4 h-4 text-red-500 animate-pulse" />
            <div className="w-24 sm:w-32 bg-slate-800 rounded-full h-2.5 overflow-hidden border border-red-950">
              <div
                className="bg-gradient-to-r from-red-600 to-rose-400 h-full rounded-full transition-all duration-500"
                style={{ width: `${hpPercent}%` }}
              />
            </div>
            <span className="text-xs font-mono font-medium text-red-300 w-12">
              {playerState.hp}/100
            </span>
          </div>

          {/* SAN */}
          <div className="flex items-center gap-2">
            <Brain className="w-4 h-4 text-cyan-400" />
            <div className="w-24 sm:w-32 bg-slate-800 rounded-full h-2.5 overflow-hidden border border-cyan-950">
              <div
                className="bg-gradient-to-r from-cyan-600 to-teal-400 h-full rounded-full transition-all duration-500"
                style={{ width: `${sanPercent}%` }}
              />
            </div>
            <span className="text-xs font-mono font-medium text-cyan-300 w-12">
              {playerState.san}/100
            </span>
          </div>
        </div>

        {/* 右侧：金币与道具背包按钮 */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1 text-xs font-medium text-amber-300 bg-amber-950/40 border border-amber-800/50 px-2.5 py-1 rounded-md">
            <Coins className="w-3.5 h-3.5 text-amber-400" />
            <span>{playerState.gold}</span>
          </div>

          <button
            onClick={() => setShowInventory(true)}
            className="flex items-center gap-1.5 px-3 py-1 text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-md border border-slate-700 transition relative"
            title="查看背包道具"
          >
            <Backpack className="w-3.5 h-3.5 text-amber-400" />
            <span>背包</span>
            {playerState.inventory?.length > 0 && (
              <span className="bg-amber-500 text-slate-950 font-bold rounded-full w-4 h-4 flex items-center justify-center text-[10px]">
                {playerState.inventory.length}
              </span>
            )}
          </button>
        </div>
      </header>

      {/* 背包弹窗 */}
      {showInventory && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#181b24] border border-slate-700 rounded-xl max-w-md w-full p-5 shadow-2xl relative animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Backpack className="w-5 h-5 text-amber-400" />
                <h3 className="font-semibold text-slate-100">随身物品背包</h3>
                <span className="text-xs text-slate-500 font-mono">({playerState.inventory?.length || 0} 件)</span>
              </div>
              <button
                onClick={() => setShowInventory(false)}
                className="p-1 text-slate-400 hover:text-slate-100 rounded-lg hover:bg-slate-800 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="py-4 min-h-[160px] max-h-[300px] overflow-y-auto space-y-2">
              {!playerState.inventory || playerState.inventory.length === 0 ? (
                <div className="h-32 flex flex-col items-center justify-center text-slate-500 text-sm">
                  <ShieldAlert className="w-8 h-8 mb-2 opacity-40" />
                  <span>背包空空如也，尚未探索获得道具</span>
                </div>
              ) : (
                playerState.inventory.map((item, idx) => (
                  <div
                    key={`${item.id}-${idx}`}
                    onMouseEnter={() => setHoveredItem(item)}
                    onMouseLeave={() => setHoveredItem(null)}
                    className="p-2.5 bg-slate-850/80 hover:bg-slate-800 border border-slate-700/70 rounded-lg flex items-center justify-between cursor-pointer transition group"
                  >
                    <div>
                      <div className="text-sm font-medium text-amber-300 group-hover:text-amber-200">
                        {item.name || item.id}
                      </div>
                      <div className="text-xs text-slate-400 mt-0.5 line-clamp-1">
                        {item.desc || '一件神秘的随身物品'}
                      </div>
                    </div>
                    <span className="text-[10px] text-slate-500 font-mono uppercase bg-slate-900 px-1.5 py-0.5 rounded border border-slate-800">
                      道具
                    </span>
                  </div>
                ))
              )}
            </div>

            {/* 道具悬浮提示详情栏 */}
            {hoveredItem && (
              <div className="p-2.5 bg-slate-900 border border-amber-900/40 rounded-lg text-xs text-slate-300 animate-in fade-in duration-100">
                <span className="text-amber-400 font-semibold">{hoveredItem.name}: </span>
                {hoveredItem.desc || '没有更多详细描述。'}
              </div>
            )}

            <div className="pt-3 border-t border-slate-800 text-right">
              <button
                onClick={() => setShowInventory(false)}
                className="px-4 py-1.5 text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-md transition"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
