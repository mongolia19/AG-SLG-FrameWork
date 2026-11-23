import { useState } from 'react';
import { PlayerState, InventoryItem } from '../../types';
import { Heart, Brain, Coins, Backpack, MapPin, X, ShieldAlert, Droplets, Utensils, Zap, Thermometer, Sun, Moon, Clock, RotateCcw } from 'lucide-react';

interface GameHUDProps {
  playerState: PlayerState;
  currentSceneTitle: string;
  onResetGame?: () => void;
}

export default function GameHUD({ playerState, currentSceneTitle, onResetGame }: GameHUDProps) {
  const [showInventory, setShowInventory] = useState(false);
  const [hoveredItem, setHoveredItem] = useState<InventoryItem | null>(null);

  const hpPercent = Math.max(0, Math.min(100, playerState.hp));
  const sanPercent = Math.max(0, Math.min(100, playerState.san));

  // 检查是否具备人体生存属性 (荒岛生存模式)
  const isSurvivalMode =
    playerState.attributes?.stamina !== undefined ||
    playerState.attributes?.hydration !== undefined ||
    playerState.attributes?.fullness !== undefined;

  const stamina = playerState.attributes?.stamina ?? 100;
  const hydration = playerState.attributes?.hydration ?? 100;
  const fullness = playerState.attributes?.fullness ?? 100;
  const temperature = playerState.attributes?.temperature ?? 37;

  const day = playerState.variables?.day;
  const timeSlot = playerState.variables?.time_slot as string | undefined;
  const weather = playerState.variables?.weather as string | undefined;
  const isNight = timeSlot === '夜晚' || timeSlot === '深夜';

  return (
    <>
      <header className="flex flex-wrap items-center justify-between px-6 py-2 bg-slate-900/90 border-b border-slate-800 text-slate-100 shadow-md backdrop-blur z-20 gap-y-2">
        {/* 左侧：角色信息与当前场景 */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-amber-400 text-sm">{playerState.name}</span>
            {!isSurvivalMode ? (
              <span className="text-xs text-slate-500 font-mono">
                [STR:{playerState.attributes?.strength || 10} AGI:{playerState.attributes?.agility || 10} INT:{playerState.attributes?.intelligence || 10}]
              </span>
            ) : (
              <span className="text-[11px] text-amber-300/80 font-mono bg-amber-950/40 px-2 py-0.5 rounded border border-amber-800/40">
                生存状态 · SUR:{playerState.attributes?.survival || 10}
              </span>
            )}
          </div>

          <div className="h-4 w-px bg-slate-700" />

          <div className="flex items-center gap-1.5 text-xs text-slate-300 bg-slate-800/80 px-2.5 py-1 rounded-md border border-slate-700/60">
            <MapPin className="w-3.5 h-3.5 text-rose-400" />
            <span className="font-medium text-slate-200">{currentSceneTitle || playerState.current_scene}</span>
          </div>

          {(day !== undefined || timeSlot) && (
            <div
              className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-md border ${
                isNight
                  ? 'bg-indigo-950/60 border-indigo-700/50 text-indigo-200'
                  : 'bg-amber-950/40 border-amber-700/40 text-amber-200'
              }`}
              title="当前游戏时间与天气"
            >
              {isNight ? (
                <Moon className="w-3.5 h-3.5 text-indigo-300" />
              ) : timeSlot ? (
                <Sun className="w-3.5 h-3.5 text-amber-400" />
              ) : (
                <Clock className="w-3.5 h-3.5 text-slate-400" />
              )}
              <span className="font-medium">
                {day !== undefined ? `第${day}天` : ''}
                {timeSlot ? ` · ${timeSlot}` : ''}
                {weather ? ` · ${weather}` : ''}
              </span>
            </div>
          )}
        </div>

        {/* 中间：HP, SAN 与 人体生存属性 */}
        <div className="flex flex-wrap items-center gap-4 sm:gap-6 my-0.5">
          {/* HP */}
          <div className="flex items-center gap-1.5" title="生命值">
            <Heart className="w-3.5 h-3.5 text-red-500 animate-pulse" />
            <div className="w-20 sm:w-24 bg-slate-800 rounded-full h-2 overflow-hidden border border-red-950">
              <div
                className="bg-gradient-to-r from-red-600 to-rose-400 h-full rounded-full transition-all duration-500"
                style={{ width: `${hpPercent}%` }}
              />
            </div>
            <span className="text-[11px] font-mono text-red-300">
              {playerState.hp}
            </span>
          </div>

          {/* SAN */}
          <div className="flex items-center gap-1.5" title="理智/心理状态">
            <Brain className="w-3.5 h-3.5 text-cyan-400" />
            <div className="w-20 sm:w-24 bg-slate-800 rounded-full h-2 overflow-hidden border border-cyan-950">
              <div
                className="bg-gradient-to-r from-cyan-600 to-teal-400 h-full rounded-full transition-all duration-500"
                style={{ width: `${sanPercent}%` }}
              />
            </div>
            <span className="text-[11px] font-mono text-cyan-300">
              {playerState.san}
            </span>
          </div>

          {/* 人体生存属性 (荒岛专属) */}
          {isSurvivalMode && (
            <div className="flex items-center gap-3 border-l border-slate-800 pl-4">
              {/* 体力 */}
              <div className="flex items-center gap-1 text-[11px] text-amber-300 font-mono" title="体能 / 体力">
                <Zap className="w-3.5 h-3.5 text-amber-400" />
                <span>{stamina}%</span>
              </div>

              {/* 水分 */}
              <div className="flex items-center gap-1 text-[11px] text-blue-300 font-mono" title="水分 / 口渴度">
                <Droplets className="w-3.5 h-3.5 text-blue-400" />
                <span>{hydration}%</span>
              </div>

              {/* 饱食度 */}
              <div className="flex items-center gap-1 text-[11px] text-emerald-300 font-mono" title="饱食度 / 饥饿度">
                <Utensils className="w-3.5 h-3.5 text-emerald-400" />
                <span>{fullness}%</span>
              </div>

              {/* 体温 */}
              <div className="flex items-center gap-1 text-[11px] text-rose-300 font-mono" title="体温状态">
                <Thermometer className="w-3.5 h-3.5 text-rose-400" />
                <span>{temperature}°C</span>
              </div>
            </div>
          )}
        </div>

        {/* 右侧：金币与道具背包按钮 */}
        <div className="flex items-center gap-3">
          {playerState.gold > 0 && (
            <div className="flex items-center gap-1 text-xs font-medium text-amber-300 bg-amber-950/40 border border-amber-800/50 px-2.5 py-1 rounded-md">
              <Coins className="w-3.5 h-3.5 text-amber-400" />
              <span>{playerState.gold}</span>
            </div>
          )}

          <button
            onClick={() => setShowInventory(true)}
            className="flex items-center gap-1.5 px-3 py-1 text-xs font-medium bg-amber-600/20 hover:bg-amber-600/30 text-amber-300 rounded-md border border-amber-500/40 transition relative shadow-sm"
            title="查看背包道具"
          >
            <Backpack className="w-3.5 h-3.5 text-amber-400" />
            <span>生存背包</span>
            {playerState.inventory?.length > 0 && (
              <span className="bg-amber-500 text-slate-950 font-bold rounded-full w-4 h-4 flex items-center justify-center text-[10px]">
                {playerState.inventory.length}
              </span>
            )}
          </button>

          {onResetGame && (
            <button
              onClick={() => {
                if (window.confirm('确定要重置当前剧本的所有探索进度并重新开始吗？')) {
                  onResetGame();
                }
              }}
              className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-slate-400 hover:text-rose-300 hover:bg-rose-950/30 rounded-md border border-slate-700/60 hover:border-rose-800/40 transition shadow-sm"
              title="重置当前剧情与角色进度"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">重置</span>
            </button>
          )}
        </div>
      </header>

      {/* 背包弹窗 */}
      {showInventory && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#181b24] border border-slate-700 rounded-xl max-w-lg w-full p-5 shadow-2xl relative animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Backpack className="w-5 h-5 text-amber-400" />
                <h3 className="font-semibold text-slate-100">生存物品背包</h3>
                <span className="text-xs text-slate-500 font-mono">({playerState.inventory?.length || 0} 件)</span>
              </div>
              <button
                onClick={() => setShowInventory(false)}
                className="p-1 text-slate-400 hover:text-slate-100 rounded-lg hover:bg-slate-800 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="py-4 min-h-[180px] max-h-[340px] overflow-y-auto space-y-2.5">
              {!playerState.inventory || playerState.inventory.length === 0 ? (
                <div className="h-36 flex flex-col items-center justify-center text-slate-500 text-sm">
                  <ShieldAlert className="w-8 h-8 mb-2 opacity-40" />
                  <span>背包空空如也，尚未探索获得求生道具</span>
                  <span className="text-xs text-slate-600 mt-1">可在沙滩或丛林中搜寻打火机、绳子、玻璃瓶与树枝</span>
                </div>
              ) : (
                playerState.inventory.map((item, idx) => {
                  const iconUrl = item.icon || (
                    ['lighter', 'rope', 'glass_bottle', 'branches', 'fresh_water_bottle', 'wild_food'].includes(item.id)
                      ? `/assets/items/${item.id === 'fresh_water_bottle' ? 'glass_bottle' : item.id === 'wild_food' ? 'branches' : item.id}.png`
                      : undefined
                  );

                  return (
                    <div
                      key={`${item.id}-${idx}`}
                      onMouseEnter={() => setHoveredItem(item)}
                      onMouseLeave={() => setHoveredItem(null)}
                      className="p-3 bg-slate-850/80 hover:bg-slate-800 border border-slate-700/70 hover:border-amber-500/40 rounded-lg flex items-center justify-between cursor-pointer transition group"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        {iconUrl ? (
                          <img
                            src={iconUrl}
                            alt={item.name}
                            className="w-10 h-10 object-contain rounded-lg bg-slate-900/90 p-1 border border-amber-500/40 shrink-0 group-hover:scale-105 transition-transform"
                          />
                        ) : (
                          <div className="w-10 h-10 rounded-lg bg-slate-900/90 border border-slate-700 flex items-center justify-center text-lg shrink-0">
                            {item.id === 'raw_crab' ? '🦀' : item.id === 'coconut' ? '🥥' : item.id === 'cooked_food' ? '🍖' : '📦'}
                          </div>
                        )}
                        <div className="min-w-0">
                          <div className="text-sm font-semibold text-amber-300 group-hover:text-amber-200 truncate">
                            {item.name || item.id}
                          </div>
                          <div className="text-xs text-slate-400 mt-0.5 line-clamp-1">
                            {item.desc || '荒岛探索收集的关键物品'}
                          </div>
                        </div>
                      </div>
                      <span className="text-[10px] text-amber-400/80 font-mono uppercase bg-slate-900 px-2 py-0.5 rounded border border-slate-800 shrink-0 ml-2">
                        装备/物资
                      </span>
                    </div>
                  );
                })
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
