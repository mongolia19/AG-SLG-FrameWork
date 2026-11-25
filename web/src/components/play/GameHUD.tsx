import { useState } from 'react';
import { PlayerState, InventoryItem, OutfitItem, SkillItem } from '../../types';
import {
  Heart,
  Brain,
  Coins,
  Backpack,
  MapPin,
  X,
  ShieldAlert,
  Droplets,
  Utensils,
  Zap,
  Thermometer,
  Sun,
  Moon,
  Clock,
  Cloud,
  CloudRain,
  CloudLightning,
  Wind,
  CloudFog,
  RotateCcw,
  RefreshCw,
  Shirt,
  Sparkles,
  Watch,
  Footprints,
  Gem,
  Shield,
  Swords,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

interface OutfitSlotMeta {
  slot: string;
  label: string;
  category: 'clothing' | 'accessory';
  emptyHint: string;
}

const CLOTHING_SLOTS: OutfitSlotMeta[] = [
  { slot: 'head', label: '头部 / 帽饰', category: 'clothing', emptyHint: '未佩戴帽饰' },
  { slot: 'outer', label: '外套 / 防护', category: 'clothing', emptyHint: '未穿着外套' },
  { slot: 'top', label: '上装', category: 'clothing', emptyHint: '未穿着上装' },
  { slot: 'bottom', label: '下装', category: 'clothing', emptyHint: '未穿着下装' },
  { slot: 'shoes', label: '鞋履', category: 'clothing', emptyHint: '赤足（未穿鞋）' },
];

const DEFAULT_ACCESSORY_SLOTS: OutfitSlotMeta[] = [
  { slot: 'accessory', label: '随身配饰', category: 'accessory', emptyHint: '暂无配饰' },
  { slot: 'wrist', label: '腕部配饰', category: 'accessory', emptyHint: '空置腕饰槽' },
  { slot: 'neck', label: '颈部挂件', category: 'accessory', emptyHint: '空置颈饰槽' },
];

const SLOT_LABEL_MAP: Record<string, string> = {
  head: '头饰',
  outer: '外套',
  top: '上装',
  bottom: '下装',
  shoes: '鞋履',
  accessory: '配饰',
  wrist: '腕饰',
  neck: '颈饰',
  waist: '腰饰',
  charm: '护符',
};

function renderSlotIcon(slot: string, className = 'w-4 h-4') {
  switch (slot) {
    case 'head':
      return <Sparkles className={`${className} text-amber-400`} />;
    case 'outer':
      return <Shield className={`${className} text-sky-400`} />;
    case 'top':
    case 'bottom':
      return <Shirt className={`${className} text-indigo-400`} />;
    case 'shoes':
      return <Footprints className={`${className} text-emerald-400`} />;
    case 'wrist':
      return <Watch className={`${className} text-cyan-400`} />;
    default:
      return <Gem className={`${className} text-violet-400`} />;
  }
}

interface GameHUDProps {
  playerState: PlayerState;
  currentSceneTitle: string;
  onResetGame?: () => void;
  onSyncScenario?: () => void;
  isSyncing?: boolean;
  syncFeedback?: string | null;
}

export default function GameHUD({
  playerState,
  currentSceneTitle,
  onResetGame,
  onSyncScenario,
  isSyncing = false,
  syncFeedback = null,
}: GameHUDProps) {
  const [showInventory, setShowInventory] = useState(false);
  const [showOutfit, setShowOutfit] = useState(false);
  const [showSkills, setShowSkills] = useState(false);
  const [skillsBarExpanded, setSkillsBarExpanded] = useState(true);
  const [hoveredItem, setHoveredItem] = useState<InventoryItem | null>(null);
  const [hoveredOutfit, setHoveredOutfit] = useState<{ slotLabel: string; item: OutfitItem } | null>(null);
  const [hoveredSkill, setHoveredSkill] = useState<SkillItem | null>(null);

  const skillsList: SkillItem[] = Array.isArray(playerState.skills)
    ? playerState.skills.filter((sk): sk is SkillItem => Boolean(sk && (sk.name || sk.id)))
    : [];
  const hasSkillFeature = skillsList.length > 0 || playerState.variables?.skills !== undefined;

  const outfitMap = playerState.outfit || {};
  const equippedEntries = Object.entries(outfitMap).filter(
    (entry): entry is [string, OutfitItem] => Boolean(entry[1] && entry[1].name)
  );
  const clothingSlotKeys = new Set(CLOTHING_SLOTS.map((s) => s.slot));
  const defaultAccessoryKeys = new Set(DEFAULT_ACCESSORY_SLOTS.map((s) => s.slot));
  const extraAccessorySlots: OutfitSlotMeta[] = equippedEntries
    .filter(([slot]) => !clothingSlotKeys.has(slot) && !defaultAccessoryKeys.has(slot))
    .map(([slot]) => ({
      slot,
      label: SLOT_LABEL_MAP[slot] || `配饰 (${slot})`,
      category: 'accessory',
      emptyHint: '空置配饰槽',
    }));
  const accessorySlots = [...DEFAULT_ACCESSORY_SLOTS, ...extraAccessorySlots];

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
  const rawWeatherType = (playerState.variables?.weather_type as string | undefined) || '';
  const isNight = timeSlot === '夜晚' || timeSlot === '深夜';

  const resolveWeatherCategory = (label?: string, wType?: string) => {
    if (wType) return wType;
    const text = label || '';
    if (/暴雨|雷暴|雷雨|风暴/.test(text)) return 'storm';
    if (/雨/.test(text)) return 'rain';
    if (/风/.test(text)) return 'windy';
    if (/阴|乌云|黑云|多云/.test(text)) return 'cloudy';
    if (/雾/.test(text)) return 'foggy';
    return 'clear';
  };
  const weatherCategory = resolveWeatherCategory(weather, rawWeatherType);

  const weatherBadgeTone =
    weatherCategory === 'storm'
      ? 'bg-slate-900/90 border-sky-500/50 text-sky-200'
      : weatherCategory === 'rain'
        ? 'bg-sky-950/60 border-sky-700/50 text-sky-200'
        : weatherCategory === 'windy'
          ? 'bg-teal-950/60 border-teal-700/50 text-teal-200'
          : weatherCategory === 'cloudy'
            ? 'bg-slate-800/80 border-slate-600/60 text-slate-200'
            : weatherCategory === 'foggy'
              ? 'bg-zinc-900/75 border-zinc-600/50 text-zinc-200'
              : isNight
                ? 'bg-indigo-950/60 border-indigo-700/50 text-indigo-200'
                : 'bg-amber-950/40 border-amber-700/40 text-amber-200';

  const renderTimeWeatherIcon = () => {
    if (weatherCategory === 'storm') return <CloudLightning className="w-3.5 h-3.5 text-sky-300 animate-pulse" />;
    if (weatherCategory === 'rain') return <CloudRain className="w-3.5 h-3.5 text-sky-400" />;
    if (weatherCategory === 'windy') return <Wind className="w-3.5 h-3.5 text-teal-300" />;
    if (weatherCategory === 'cloudy') return <Cloud className="w-3.5 h-3.5 text-slate-300" />;
    if (weatherCategory === 'foggy') return <CloudFog className="w-3.5 h-3.5 text-zinc-300" />;
    if (isNight) return <Moon className="w-3.5 h-3.5 text-indigo-300" />;
    if (timeSlot) return <Sun className="w-3.5 h-3.5 text-amber-400" />;
    return <Clock className="w-3.5 h-3.5 text-slate-400" />;
  };

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

          {(day !== undefined || timeSlot || weather) && (
            <div
              className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-md border transition-colors duration-500 ${weatherBadgeTone}`}
              title="当前游戏时间与天气变化"
            >
              {renderTimeWeatherIcon()}
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

        {/* 右侧：金币、服装配饰与道具背包按钮 */}
        <div className="flex items-center gap-2.5">
          {playerState.gold > 0 && (
            <div className="flex items-center gap-1 text-xs font-medium text-amber-300 bg-amber-950/40 border border-amber-800/50 px-2.5 py-1 rounded-md">
              <Coins className="w-3.5 h-3.5 text-amber-400" />
              <span>{playerState.gold}</span>
            </div>
          )}

          <button
            onClick={() => setShowSkills(true)}
            className="flex items-center gap-1.5 px-3 py-1 text-xs font-medium bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-200 rounded-md border border-emerald-500/40 transition relative shadow-sm"
            title="查看当前技能与技能简介"
          >
            <Swords className="w-3.5 h-3.5 text-emerald-400" />
            <span>技能栏</span>
            {skillsList.length > 0 && (
              <span className="bg-emerald-500 text-slate-950 font-bold rounded-full w-4 h-4 flex items-center justify-center text-[10px]">
                {skillsList.length}
              </span>
            )}
          </button>

          <button
            onClick={() => setShowOutfit(true)}
            className="flex items-center gap-1.5 px-3 py-1 text-xs font-medium bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-200 rounded-md border border-indigo-500/40 transition relative shadow-sm"
            title="查看当前穿着与随身配饰"
          >
            <Shirt className="w-3.5 h-3.5 text-indigo-400" />
            <span>服装栏</span>
            {equippedEntries.length > 0 && (
              <span className="bg-indigo-500 text-white font-bold rounded-full w-4 h-4 flex items-center justify-center text-[10px]">
                {equippedEntries.length}
              </span>
            )}
          </button>

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

          {onSyncScenario && (
            <button
              onClick={onSyncScenario}
              className={`flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-md border transition shadow-sm ${
                isSyncing
                  ? 'text-indigo-300 bg-indigo-950/60 border-indigo-700/60'
                  : 'text-slate-300 hover:text-indigo-300 hover:bg-indigo-950/30 border-slate-700/60 hover:border-indigo-800/40'
              }`}
              title="即时从 Studio 同步最新的剧本与场景修改"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin text-indigo-400' : ''}`} />
              <span className="hidden sm:inline">同步剧本</span>
            </button>
          )}

          {syncFeedback && (
            <div className="absolute top-12 right-6 px-3 py-1 text-[11px] font-medium bg-indigo-900/90 text-indigo-200 border border-indigo-500/50 rounded-lg shadow-lg animate-in fade-in zoom-in-95 duration-150 z-50">
              ✓ {syncFeedback}
            </div>
          )}

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

      {/* 快捷技能卡片栏 */}
      {hasSkillFeature && (
        <div className="px-6 py-2 bg-slate-950/90 border-b border-slate-800/80 text-xs z-20">
          <div className="flex items-center justify-between gap-2 mb-1.5">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowSkills(true)}
                className="flex items-center gap-1.5 text-[11px] font-semibold text-emerald-300 hover:text-emerald-200 transition"
                title="点击展开完整技能栏弹窗"
              >
                <Swords className="w-3.5 h-3.5 text-emerald-400" />
                <span>技能卡片栏</span>
              </button>
              <span className="text-[10px] font-mono text-slate-500">
                ({skillsList.length} 项技能)
              </span>
            </div>

            {skillsList.length > 0 && (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setSkillsBarExpanded((prev) => !prev)}
                  className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-emerald-300 px-2 py-0.5 rounded bg-slate-900/80 border border-slate-800 transition"
                  title={skillsBarExpanded ? '折叠技能卡片区' : '展开技能卡片区'}
                >
                  {skillsBarExpanded ? (
                    <>
                      <ChevronUp className="w-3 h-3" />
                      <span>收起卡片</span>
                    </>
                  ) : (
                    <>
                      <ChevronDown className="w-3 h-3" />
                      <span>展开卡片</span>
                    </>
                  )}
                </button>
              </div>
            )}
          </div>

          {skillsList.length === 0 ? (
            <button
              onClick={() => setShowSkills(true)}
              className="w-full text-left px-3 py-1.5 rounded-lg bg-slate-900/50 hover:bg-slate-900 border border-dashed border-slate-800 text-[11px] text-slate-500 hover:text-slate-300 italic transition"
            >
              {typeof playerState.variables?.skills === 'string' && playerState.variables.skills
                ? `${playerState.variables.skills} · 觉醒后每个技能将以独立卡片形式展示作用说明`
                : '尚未习得技能 · 觉醒后每个技能将以独立卡片形式展示作用说明'}
            </button>
          ) : skillsBarExpanded ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5 max-h-48 overflow-y-auto pr-0.5">
              {skillsList.map((skill, idx) => (
                <button
                  key={`${skill.id || skill.name}-${idx}`}
                  type="button"
                  onClick={() => {
                    setHoveredSkill(skill);
                    setShowSkills(true);
                  }}
                  title={`${skill.name || skill.id}${skill.level !== undefined ? ` (Lv.${skill.level})` : ''} — ${skill.effect || skill.desc || ''}`}
                  className="text-left p-2.5 rounded-lg bg-slate-900/95 hover:bg-slate-800/95 border border-emerald-800/40 hover:border-emerald-500/60 shadow-sm transition flex flex-col gap-1.5 group"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-1.5 min-w-0">
                      <div className="w-6 h-6 rounded-md bg-emerald-950/70 border border-emerald-700/50 flex items-center justify-center shrink-0">
                        <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
                      </div>
                      <span className="text-xs font-semibold text-emerald-200 group-hover:text-emerald-100 truncate">
                        {skill.name || skill.id}
                      </span>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      {skill.level !== undefined && (
                        <span className="text-[10px] font-mono text-amber-300 bg-amber-950/50 border border-amber-800/40 px-1.5 py-0.5 rounded">
                          Lv.{skill.level}
                        </span>
                      )}
                      {skill.tag && (
                        <span className="text-[10px] text-emerald-300 bg-emerald-950/50 border border-emerald-800/40 px-1.5 py-0.5 rounded">
                          {skill.tag}
                        </span>
                      )}
                    </div>
                  </div>

                  {skill.desc && (
                    <p className="text-[11px] text-slate-300 leading-snug">
                      {skill.desc}
                    </p>
                  )}

                  {skill.effect && (
                    <div className="text-[10px] text-emerald-200/90 bg-emerald-950/35 border border-emerald-800/35 rounded px-2 py-1 leading-snug">
                      <span className="font-semibold text-emerald-400">作用说明：</span>
                      {skill.effect}
                    </div>
                  )}

                  {(skill.cost || skill.cooldown) && (
                    <div className="flex items-center gap-2 text-[10px] font-mono text-slate-400 pt-0.5">
                      {skill.cost && (
                        <span className="bg-slate-950/80 border border-slate-800 px-1.5 py-0.5 rounded">
                          消耗: {skill.cost}
                        </span>
                      )}
                      {skill.cooldown && (
                        <span className="bg-slate-950/80 border border-slate-800 px-1.5 py-0.5 rounded">
                          冷却: {skill.cooldown}
                        </span>
                      )}
                    </div>
                  )}
                </button>
              ))}
            </div>
          ) : (
            <div className="flex items-center gap-2 overflow-x-auto no-scrollbar">
              {skillsList.map((skill, idx) => (
                <button
                  key={`${skill.id || skill.name}-${idx}`}
                  type="button"
                  onClick={() => {
                    setHoveredSkill(skill);
                    setShowSkills(true);
                  }}
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-900/90 hover:bg-slate-800 border border-slate-700/70 hover:border-emerald-500/50 text-[11px] text-slate-200 shrink-0 transition"
                >
                  <Sparkles className="w-3 h-3 text-emerald-400 shrink-0" />
                  <span className="font-semibold text-emerald-200">{skill.name || skill.id}</span>
                  {skill.level !== undefined && (
                    <span className="text-[10px] font-mono text-amber-300">Lv.{skill.level}</span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 快捷服装与配饰展示条 */}
      <div className="flex items-center gap-2 px-6 py-1.5 bg-slate-950/85 border-b border-slate-800/80 text-xs overflow-x-auto no-scrollbar z-20">
        <button
          onClick={() => setShowOutfit(true)}
          className="flex items-center gap-1.5 text-[11px] font-semibold text-indigo-300 hover:text-indigo-200 shrink-0 pr-2 border-r border-slate-800 transition"
          title="点击展开完整服装与配饰栏"
        >
          <Shirt className="w-3.5 h-3.5 text-indigo-400" />
          <span>当前穿着与配饰</span>
        </button>

        {equippedEntries.length === 0 ? (
          <button
            onClick={() => setShowOutfit(true)}
            className="text-[11px] text-slate-500 hover:text-slate-300 italic transition"
          >
            暂无穿戴记录 · 点击查看服装与配饰槽位
          </button>
        ) : (
          <div className="flex items-center gap-1.5 min-w-0">
            {equippedEntries.map(([slot, piece]) => (
              <button
                key={slot}
                onClick={() => setShowOutfit(true)}
                title={`${SLOT_LABEL_MAP[slot] || slot}: ${piece.name}${piece.desc ? ` — ${piece.desc}` : ''}`}
                className="flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-slate-900/90 hover:bg-slate-800 border border-slate-700/70 hover:border-indigo-500/50 text-[11px] text-slate-200 shrink-0 transition"
              >
                {renderSlotIcon(slot, 'w-3 h-3')}
                <span className="text-slate-400">{SLOT_LABEL_MAP[slot] || slot}:</span>
                <span className="font-medium text-indigo-200">{piece.name}</span>
                {piece.tag && (
                  <span className="hidden md:inline text-[10px] text-amber-300/80 bg-amber-950/40 px-1 rounded border border-amber-800/30">
                    {piece.tag}
                  </span>
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* 技能栏详情弹窗 */}
      {showSkills && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#181b24] border border-slate-700 rounded-xl max-w-2xl w-full p-5 shadow-2xl relative animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Swords className="w-5 h-5 text-emerald-400" />
                <h3 className="font-semibold text-slate-100">角色技能栏</h3>
                <span className="text-xs text-slate-500 font-mono">
                  (已掌握 {skillsList.length} 项技能)
                </span>
              </div>
              <button
                onClick={() => {
                  setShowSkills(false);
                  setHoveredSkill(null);
                }}
                className="p-1 text-slate-400 hover:text-slate-100 rounded-lg hover:bg-slate-800 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="py-4 min-h-[180px] max-h-[65vh] overflow-y-auto space-y-2.5">
              {skillsList.length === 0 ? (
                <div className="h-36 flex flex-col items-center justify-center text-slate-500 text-sm text-center px-4">
                  <Sparkles className="w-8 h-8 mb-2 opacity-40 text-emerald-400" />
                  <span>
                    {typeof playerState.variables?.skills === 'string' && playerState.variables.skills
                      ? playerState.variables.skills
                      : '尚未掌握任何技能'}
                  </span>
                  <span className="text-xs text-slate-600 mt-1">
                    完成职业觉醒或剧情试炼后，习得的技能名称与技能简介将显示在此处
                  </span>
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {skillsList.map((skill, idx) => (
                    <div
                      key={`${skill.id || skill.name}-${idx}`}
                      onMouseEnter={() => setHoveredSkill(skill)}
                      onClick={() => setHoveredSkill(skill)}
                      className={`p-3.5 rounded-lg border transition cursor-pointer flex flex-col gap-1.5 ${
                        hoveredSkill?.id === skill.id && hoveredSkill?.name === skill.name
                          ? 'bg-slate-800/90 border-emerald-500/60 shadow-md'
                          : 'bg-slate-900/90 hover:bg-slate-800 border-slate-700/80 hover:border-emerald-500/40'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <div className="w-7 h-7 rounded-md bg-emerald-950/60 border border-emerald-700/50 flex items-center justify-center shrink-0">
                            <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
                          </div>
                          <span className="text-sm font-semibold text-emerald-200 truncate">
                            {skill.name || skill.id}
                          </span>
                        </div>
                        <div className="flex items-center gap-1 shrink-0">
                          {skill.level !== undefined && (
                            <span className="text-[10px] font-mono text-amber-300 bg-amber-950/50 border border-amber-800/40 px-1.5 py-0.5 rounded">
                              Lv.{skill.level}
                            </span>
                          )}
                          {skill.tag && (
                            <span className="text-[10px] text-emerald-300 bg-emerald-950/50 border border-emerald-800/40 px-1.5 py-0.5 rounded">
                              {skill.tag}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="pl-9 space-y-1.5">
                        <p className="text-xs text-slate-300 leading-relaxed">
                          {skill.desc || '暂无技能简介。'}
                        </p>
                        {skill.effect && (
                          <div className="text-[11px] text-emerald-200/90 bg-emerald-950/35 border border-emerald-800/40 rounded px-2 py-1 leading-relaxed">
                            <span className="font-semibold text-emerald-400">作用说明：</span>
                            {skill.effect}
                          </div>
                        )}
                        {(skill.cost || skill.cooldown) && (
                          <div className="flex flex-wrap items-center gap-2 text-[10px] font-mono text-slate-400 pt-0.5">
                            {skill.cost && (
                              <span className="bg-slate-950/80 border border-slate-800 px-1.5 py-0.5 rounded">
                                消耗: {skill.cost}
                              </span>
                            )}
                            {skill.cooldown && (
                              <span className="bg-slate-950/80 border border-slate-800 px-1.5 py-0.5 rounded">
                                冷却: {skill.cooldown}
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {hoveredSkill && (
              <div className="p-2.5 bg-slate-900 border border-emerald-900/50 rounded-lg text-xs text-slate-300 mb-3 animate-in fade-in duration-100 space-y-1">
                <div>
                  <span className="text-emerald-300 font-semibold">
                    {hoveredSkill.name || hoveredSkill.id}
                    {hoveredSkill.level !== undefined ? ` (Lv.${hoveredSkill.level})` : ''}:{' '}
                  </span>
                  {hoveredSkill.desc || '暂无更多技能简介。'}
                </div>
                {hoveredSkill.effect && (
                  <div className="text-emerald-200/90">
                    <span className="text-emerald-400 font-semibold">作用说明：</span>
                    {hoveredSkill.effect}
                  </div>
                )}
              </div>
            )}

            <div className="pt-3 border-t border-slate-800 text-right">
              <button
                onClick={() => {
                  setShowSkills(false);
                  setHoveredSkill(null);
                }}
                className="px-4 py-1.5 text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-md transition"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 服装与配饰详情弹窗 */}
      {showOutfit && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#181b24] border border-slate-700 rounded-xl max-w-2xl w-full p-5 shadow-2xl relative animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Shirt className="w-5 h-5 text-indigo-400" />
                <h3 className="font-semibold text-slate-100">角色服装与配饰栏</h3>
                <span className="text-xs text-slate-500 font-mono">
                  (已穿戴 {equippedEntries.length} 件)
                </span>
              </div>
              <button
                onClick={() => {
                  setShowOutfit(false);
                  setHoveredOutfit(null);
                }}
                className="p-1 text-slate-400 hover:text-slate-100 rounded-lg hover:bg-slate-800 transition"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="py-4 max-h-[65vh] overflow-y-auto space-y-5">
              {/* 服装穿着槽位 */}
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wider text-indigo-300 mb-2.5 flex items-center gap-1.5">
                  <Shirt className="w-3.5 h-3.5" />
                  <span>当前穿着（服饰部位）</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  {CLOTHING_SLOTS.map(({ slot, label, emptyHint }) => {
                    const piece = outfitMap[slot];
                    return (
                      <div
                        key={slot}
                        onMouseEnter={() => piece && setHoveredOutfit({ slotLabel: label, item: piece })}
                        onMouseLeave={() => setHoveredOutfit(null)}
                        onClick={() => piece && setHoveredOutfit({ slotLabel: label, item: piece })}
                        className={`p-3 rounded-lg border transition flex items-start gap-3 ${
                          piece
                            ? 'bg-slate-900/90 hover:bg-slate-800 border-slate-700/80 hover:border-indigo-500/50 cursor-pointer'
                            : 'bg-slate-950/50 border-slate-800/80 border-dashed opacity-70'
                        }`}
                      >
                        <div className="w-9 h-9 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-center shrink-0">
                          {piece?.icon ? (
                            <img src={piece.icon} alt={piece.name} className="w-7 h-7 object-contain rounded" />
                          ) : (
                            renderSlotIcon(slot, 'w-4 h-4')
                          )}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-[10px] font-mono uppercase text-slate-400">{label}</span>
                            {piece?.tag && (
                              <span className="text-[10px] text-amber-300 bg-amber-950/50 border border-amber-800/40 px-1.5 py-0.2 rounded shrink-0">
                                {piece.tag}
                              </span>
                            )}
                          </div>
                          {piece ? (
                            <>
                              <div className="text-sm font-semibold text-indigo-200 truncate mt-0.5">
                                {piece.name}
                              </div>
                              <div className="text-xs text-slate-400 mt-0.5 line-clamp-1">
                                {piece.desc || '当前穿戴的随身衣物'}
                              </div>
                            </>
                          ) : (
                            <div className="text-xs text-slate-500 italic mt-1">{emptyHint}</div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* 配饰与挂件槽位 */}
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-wider text-violet-300 mb-2.5 flex items-center gap-1.5">
                  <Gem className="w-3.5 h-3.5" />
                  <span>配饰与随身挂件</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  {accessorySlots.map(({ slot, label, emptyHint }) => {
                    const piece = outfitMap[slot];
                    return (
                      <div
                        key={slot}
                        onMouseEnter={() => piece && setHoveredOutfit({ slotLabel: label, item: piece })}
                        onMouseLeave={() => setHoveredOutfit(null)}
                        onClick={() => piece && setHoveredOutfit({ slotLabel: label, item: piece })}
                        className={`p-3 rounded-lg border transition flex items-start gap-3 ${
                          piece
                            ? 'bg-slate-900/90 hover:bg-slate-800 border-slate-700/80 hover:border-violet-500/50 cursor-pointer'
                            : 'bg-slate-950/50 border-slate-800/80 border-dashed opacity-70'
                        }`}
                      >
                        <div className="w-9 h-9 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-center shrink-0">
                          {piece?.icon ? (
                            <img src={piece.icon} alt={piece.name} className="w-7 h-7 object-contain rounded" />
                          ) : (
                            renderSlotIcon(slot, 'w-4 h-4')
                          )}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-[10px] font-mono uppercase text-slate-400">{label}</span>
                            {piece?.tag && (
                              <span className="text-[10px] text-violet-300 bg-violet-950/50 border border-violet-800/40 px-1.5 py-0.2 rounded shrink-0">
                                {piece.tag}
                              </span>
                            )}
                          </div>
                          {piece ? (
                            <>
                              <div className="text-sm font-semibold text-violet-200 truncate mt-0.5">
                                {piece.name}
                              </div>
                              <div className="text-xs text-slate-400 mt-0.5 line-clamp-1">
                                {piece.desc || '随身佩戴的小件配饰'}
                              </div>
                            </>
                          ) : (
                            <div className="text-xs text-slate-500 italic mt-1">{emptyHint}</div>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {hoveredOutfit && (
              <div className="p-2.5 bg-slate-900 border border-indigo-900/50 rounded-lg text-xs text-slate-300 mb-3 animate-in fade-in duration-100">
                <span className="text-indigo-300 font-semibold">
                  [{hoveredOutfit.slotLabel}] {hoveredOutfit.item.name}:{' '}
                </span>
                {hoveredOutfit.item.desc || '没有更多详细描述。'}
              </div>
            )}

            <div className="pt-3 border-t border-slate-800 text-right">
              <button
                onClick={() => {
                  setShowOutfit(false);
                  setHoveredOutfit(null);
                }}
                className="px-4 py-1.5 text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-md transition"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}

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
