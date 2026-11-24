import { useState, useEffect, useRef } from 'react';
import { StoryMessage, SceneNode, NPC, PropDecoration } from '../../types';
import {
  User,
  Sparkles,
  MessageSquare,
  Terminal,
  Image as ImageIcon,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';

interface StoryStreamProps {
  messages: StoryMessage[];
  currentScene?: SceneNode;
  streamingText?: string;
  isStreaming?: boolean;
  weather?: string;
  weatherType?: string;
}

export default function StoryStream({
  messages,
  currentScene,
  streamingText,
  isStreaming,
  weather,
  weatherType,
}: StoryStreamProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [isHeroCollapsed, setIsHeroCollapsed] = useState(false);
  const [isDescExpanded, setIsDescExpanded] = useState(false);

  const handleCopy = (id: string, text: string, e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => {
      setCopiedId((prev) => (prev === id ? null : prev));
    }, 2000);
  };

  // 自动滚动到底部
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, streamingText]);

  // 当前场景的 NPC 列表与视觉图层
  const npcs: NPC[] = currentScene?.npcs || [];
  const primaryNPC = npcs.length > 0 ? npcs[0] : null;

  const bgImage = currentScene?.visuals?.background || currentScene?.background;
  const heroImage = currentScene?.visuals?.hero_image || currentScene?.hero_image;
  const foregroundImage = currentScene?.visuals?.foreground || currentScene?.foreground;
  const atmosphereText = currentScene?.visuals?.atmosphere;

  // 仅在焦点图展开（非收起）情况下才更新并绘制焦点图；收起状态下不触发大图绘制与更新
  const [displayedHeroImage, setDisplayedHeroImage] = useState<string | undefined>(heroImage);

  useEffect(() => {
    if (!isHeroCollapsed) {
      setDisplayedHeroImage(heroImage);
    }
  }, [isHeroCollapsed, heroImage]);

  const resolveWeatherMode = (label?: string, wType?: string) => {
    if (wType) return wType;
    const text = label || '';
    if (/暴雨|雷暴|雷雨|风暴/.test(text)) return 'storm';
    if (/雨/.test(text)) return 'rain';
    if (/风/.test(text)) return 'windy';
    if (/阴|乌云|黑云|多云/.test(text)) return 'cloudy';
    if (/雾/.test(text)) return 'foggy';
    return 'clear';
  };
  const weatherMode = weather ? resolveWeatherMode(weather, weatherType) : '';

  const rawDecorations: PropDecoration[] =
    currentScene?.visuals?.decorations || currentScene?.decorations || [];
  const sortDecorations = (items: PropDecoration[]) =>
    [...items].sort((a, b) => {
      const aScore = a.category === 'structure' ? 0 : 1;
      const bScore = b.category === 'structure' ? 0 : 1;
      return aScore - bScore;
    });
  const builtStructures = rawDecorations.filter((d) => d.category === 'structure');
  const leftDecorations = sortDecorations(rawDecorations.filter((d) => d.side === 'left'));
  const rightDecorations = sortDecorations(rawDecorations.filter((d) => d.side === 'right'));

  const isImageSrc = (src?: string) => {
    if (!src) return false;
    return (
      src.startsWith('/') ||
      src.startsWith('http://') ||
      src.startsWith('https://') ||
      src.startsWith('data:') ||
      src.startsWith('./') ||
      /\.(png|jpe?g|webp|gif|svg)$/i.test(src)
    );
  };

  return (
    <div className="relative flex-1 flex flex-col h-full overflow-hidden bg-slate-950">
      {/* 1. 背景图层 (Background Layer) */}
      <div className="absolute inset-0 z-0 overflow-hidden pointer-events-none">
        {isImageSrc(bgImage) ? (
          <img
            src={bgImage}
            alt="Scene Background"
            className="w-full h-full object-cover opacity-50 scale-100 transition-all duration-1000"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-slate-900 border-b border-slate-800">
            <div className="text-center p-8 opacity-25">
              <div className="text-6xl mb-3">🏝️</div>
              <div className="text-xl font-serif tracking-widest text-slate-300">
                {currentScene?.title || '未知探索区域'}
              </div>
              <div className="text-xs text-slate-500 font-mono mt-1">
                {currentScene?.id || 'scene_loading'}
              </div>
            </div>
          </div>
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-[#0d1017] via-[#0d1017]/80 to-[#0d1017]/35 z-10" />

        {/* 1b. 动态天气视觉层 (Dynamic Weather Overlay) */}
        {weatherMode === 'cloudy' && (
          <div className="absolute inset-0 z-10 bg-slate-900/35 backdrop-saturate-75 transition-all duration-1000" />
        )}
        {weatherMode === 'windy' && (
          <div className="absolute inset-0 z-10 overflow-hidden">
            <div className="absolute inset-0 bg-teal-950/15 transition-all duration-1000" />
            <div className="absolute -inset-12 weather-wind-layer" />
          </div>
        )}
        {weatherMode === 'rain' && (
          <div className="absolute inset-0 z-10 overflow-hidden">
            <div className="absolute inset-0 bg-sky-950/25 backdrop-saturate-75 transition-all duration-1000" />
            <div className="absolute inset-0 weather-rain-layer" />
          </div>
        )}
        {weatherMode === 'storm' && (
          <div className="absolute inset-0 z-10 overflow-hidden">
            <div className="absolute inset-0 bg-slate-950/45 backdrop-saturate-50 transition-all duration-1000" />
            <div className="absolute inset-0 weather-storm-layer" />
            <div className="absolute inset-0 bg-sky-100 weather-storm-flash" />
          </div>
        )}
        {weatherMode === 'foggy' && (
          <div className="absolute inset-0 z-10 overflow-hidden">
            <div className="absolute inset-0 bg-gradient-to-b from-slate-300/10 via-slate-400/15 to-slate-200/20 weather-fog-layer" />
          </div>
        )}
      </div>

      {/* 2. 角色立绘图层 (Character / Foreground Layer) */}
      {(primaryNPC || foregroundImage) && (
        <div className="absolute right-8 bottom-28 z-10 hidden md:flex flex-col items-center pointer-events-none transition-all duration-700 animate-in fade-in slide-in-from-right-8">
          <div className="w-48 h-64 rounded-2xl bg-gradient-to-b from-slate-800/90 to-slate-900/95 border border-slate-700/80 shadow-2xl flex flex-col items-center justify-center p-4 backdrop-blur-md">
            {isImageSrc(foregroundImage) ? (
              <img
                src={foregroundImage}
                alt="Foreground Character"
                className="w-32 h-44 object-contain drop-shadow-md mb-2"
              />
            ) : (
              <div className="w-24 h-24 rounded-full bg-slate-700/80 border-2 border-amber-500/50 flex items-center justify-center text-4xl shadow-inner mb-3">
                👤
              </div>
            )}
            <span className="text-sm font-bold text-amber-300 tracking-wide">
              {primaryNPC?.name || '登场人物'}
            </span>
            {primaryNPC?.greeting && (
              <span className="text-[11px] text-slate-400 text-center mt-2 px-2 line-clamp-3 italic">
                "{primaryNPC.greeting}"
              </span>
            )}
          </div>
        </div>
      )}

      {/* 2a. 左侧场景氛围与已建耐用设施 (Left Margin Scenery & Built Structures) */}
      {leftDecorations.length > 0 && (
        <aside
          key={`left-decs-${currentScene?.id || 'none'}`}
          aria-label="左侧环境与建造设施区"
          className="absolute left-3 xl:left-8 top-6 bottom-6 z-10 hidden lg:flex flex-col gap-3.5 pointer-events-auto select-none w-32 xl:w-40 justify-start items-center overflow-y-auto no-scrollbar py-2"
        >
          {leftDecorations.map((item, idx) => {
            const isStructure = item.category === 'structure';
            return (
              <div
                key={item.id || idx}
                className={`group relative w-full bg-slate-900/85 hover:bg-slate-800/95 border rounded-xl overflow-hidden shadow-2xl backdrop-blur-md transition-all duration-300 hover:scale-[1.03] animate-in fade-in slide-in-from-left-4 ${
                  isStructure
                    ? 'border-emerald-500/60 hover:border-emerald-400/80 ring-1 ring-emerald-500/20'
                    : 'border-slate-700/70 hover:border-amber-500/60'
                }`}
                title={item.tooltip || item.caption || item.name}
              >
                <div className="w-full h-24 xl:h-32 overflow-hidden bg-slate-950/70 relative">
                  <img
                    src={item.image}
                    alt={item.name}
                    className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-slate-950/90 via-slate-950/20 to-transparent" />
                  <span
                    className={`absolute bottom-1.5 left-2 right-2 text-[11px] font-medium drop-shadow truncate ${
                      isStructure ? 'text-emerald-300' : 'text-amber-300'
                    }`}
                  >
                    {item.caption || item.name}
                  </span>
                </div>
                <div className="px-2 py-1 bg-slate-950/70 border-t border-slate-800/80 flex items-center justify-between gap-1">
                  <span className="text-[10px] text-slate-300 font-sans truncate">
                    {item.name}
                  </span>
                  <span
                    className={`text-[9px] font-mono px-1 py-0.5 rounded border shrink-0 ${
                      isStructure
                        ? 'text-emerald-300 bg-emerald-950/70 border-emerald-700/50'
                        : 'text-amber-400 bg-amber-950/60 border-amber-800/40'
                    }`}
                  >
                    {item.tag || (isStructure ? '已建成' : '环境')}
                  </span>
                </div>
              </div>
            );
          })}
        </aside>
      )}

      {/* 2b. 右侧场景氛围与已建耐用设施 (Right Margin Scenery & Built Structures) */}
      {rightDecorations.length > 0 && (
        <aside
          key={`right-decs-${currentScene?.id || 'none'}`}
          aria-label="右侧环境与建造设施区"
          className={`absolute right-3 xl:right-8 ${
            primaryNPC || foregroundImage ? 'top-6 max-h-[calc(100%-19rem)]' : 'top-6 bottom-6'
          } z-10 hidden lg:flex flex-col gap-3.5 pointer-events-auto select-none w-32 xl:w-40 justify-start items-center overflow-y-auto no-scrollbar py-2`}
        >
          {rightDecorations.map((item, idx) => {
            const isStructure = item.category === 'structure';
            return (
              <div
                key={item.id || idx}
                className={`group relative w-full bg-slate-900/85 hover:bg-slate-850/95 border rounded-xl overflow-hidden shadow-2xl backdrop-blur-md transition-all duration-300 hover:scale-[1.03] animate-in fade-in slide-in-from-right-4 ${
                  isStructure
                    ? 'border-emerald-500/60 hover:border-emerald-400/80 ring-1 ring-emerald-500/20'
                    : 'border-slate-700/70 hover:border-amber-500/60'
                }`}
                title={item.tooltip || item.caption || item.name}
              >
                <div className="w-full h-24 xl:h-32 overflow-hidden bg-slate-950/70 relative">
                  <img
                    src={item.image}
                    alt={item.name}
                    className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500"
                  />
                  <div className="absolute inset-0 bg-gradient-to-t from-slate-950/90 via-slate-950/20 to-transparent" />
                  <span
                    className={`absolute bottom-1.5 left-2 right-2 text-[11px] font-medium drop-shadow truncate ${
                      isStructure ? 'text-emerald-300' : 'text-amber-300'
                    }`}
                  >
                    {item.caption || item.name}
                  </span>
                </div>
                <div className="px-2 py-1 bg-slate-950/70 border-t border-slate-800/80 flex items-center justify-between gap-1">
                  <span className="text-[10px] text-slate-300 font-sans truncate">
                    {item.name}
                  </span>
                  <span
                    className={`text-[9px] font-mono px-1 py-0.5 rounded border shrink-0 ${
                      isStructure
                        ? 'text-emerald-300 bg-emerald-950/70 border-emerald-700/50'
                        : 'text-amber-400 bg-amber-950/60 border-amber-800/40'
                    }`}
                  >
                    {item.tag || (isStructure ? '已建成' : '环境')}
                  </span>
                </div>
              </div>
            );
          })}
        </aside>
      )}

      {/* 3. 剧情流主列 (包含置顶冻结的场景焦点图与独立向下滚动的消息流) */}
      <main className="relative z-10 flex-1 flex flex-col h-full min-h-0 overflow-hidden max-w-4xl lg:max-w-2xl xl:max-w-3xl 2xl:max-w-4xl w-full mx-auto">
        {/* 顶部固定/冻结区：窄屏设施缩略条 + 场景焦点图 */}
        <div className="flex-none px-4 sm:px-6 pt-1.5 pb-1 space-y-1.5 z-20">
          {/* 窄屏模式下展示已建成的耐用营地设施缩略条 */}
          {builtStructures.length > 0 && (
            <div
              key={`mobile-structs-${currentScene?.id || 'none'}`}
              className="lg:hidden flex items-center gap-2 overflow-x-auto no-scrollbar pb-0.5"
            >
              {builtStructures.map((item, idx) => (
                <div
                  key={item.id || idx}
                  title={item.tooltip || item.caption || item.name}
                  className="flex items-center gap-1.5 shrink-0 bg-slate-900/90 border border-emerald-500/50 rounded-lg p-1 pr-2 shadow-sm"
                >
                  <img
                    src={item.image}
                    alt={item.name}
                    className="w-8 h-8 rounded object-cover border border-slate-800"
                  />
                  <div className="min-w-0">
                    <div className="text-[10px] font-semibold text-emerald-300 truncate">{item.name}</div>
                    <div className="text-[9px] text-slate-400 truncate">{item.tag || '已建成'}</div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* 场景焦点图与开场卡片 (Pinned Scene Hero Card) */}
          {currentScene && (
            <div
              key={`scene-card-${currentScene.id}`}
              className="bg-slate-900/90 border border-slate-800/90 rounded-xl overflow-hidden backdrop-blur-md text-slate-300 shadow-lg transition-all duration-300"
            >
              {isHeroCollapsed ? (
                /* 紧凑条形状态 (收起状态：完全不绘制和加载焦点图，腾出最大对话纵向空间) */
                <div className="px-3 py-1.5 flex items-center justify-between gap-2.5 bg-slate-900/95">
                  <div className="flex items-center gap-2 min-w-0 flex-wrap">
                    <Sparkles className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                    <span className="text-xs font-semibold text-amber-400 truncate font-sans">
                      {currentScene.title}
                    </span>
                    {(weather || atmosphereText) && (
                      <span className="text-[10px] text-slate-300 bg-slate-800/80 border border-slate-700/70 px-2 py-0.5 rounded-full truncate">
                        {weather ? `${weather}` : ''}
                        {weather && atmosphereText ? ' · ' : ''}
                        {atmosphereText || ''}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <button
                      onClick={() => setIsHeroCollapsed(false)}
                      className="flex items-center gap-1 text-[11px] text-amber-300/90 hover:text-amber-200 px-2.5 py-0.5 rounded-md bg-slate-800 hover:bg-slate-700 border border-slate-700 transition"
                      title="展开场景焦点大图与描述"
                    >
                      <span>展开焦点图</span>
                      <ChevronDown className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ) : (
                /* 展开完整焦点图与描述状态 (仅在打开时才绘制和更新焦点图) */
                <div>
                  {displayedHeroImage && (
                    isImageSrc(displayedHeroImage) ? (
                      <div className="w-full h-28 sm:h-36 max-h-40 bg-slate-800/90 relative flex items-center justify-center overflow-hidden border-b border-slate-800">
                        <img
                          src={displayedHeroImage}
                          alt={currentScene.title}
                          className="w-full h-full object-cover hover:scale-105 transition-transform duration-700"
                        />
                        <div className="absolute inset-0 bg-gradient-to-t from-slate-950/90 via-transparent to-transparent pointer-events-none" />

                        {/* 右上角收起按钮 */}
                        <div className="absolute top-2 right-2 z-10 flex items-center gap-1.5">
                          <button
                            onClick={() => setIsHeroCollapsed(true)}
                            className="flex items-center gap-1 text-[11px] text-slate-300 bg-slate-950/75 hover:bg-slate-900 border border-slate-700/80 px-2 py-0.5 rounded-lg backdrop-blur-md shadow-md transition"
                            title="收起焦点大图以获得更大的对话滚动视野"
                          >
                            <span>收起</span>
                            <ChevronUp className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    ) : (
                      /* 文本/线索占位条：高度压至极小，不占多余屏幕空间 */
                      <div className="w-full px-3 py-1.5 bg-slate-800/60 border-b border-slate-800 flex items-center justify-between gap-2">
                        <div className="flex items-center gap-1.5 text-slate-300 min-w-0">
                          <ImageIcon className="w-3.5 h-3.5 text-amber-500/80 shrink-0" />
                          <span className="text-[11px] font-mono font-medium tracking-wide truncate">
                            {displayedHeroImage}
                          </span>
                        </div>
                        <button
                          onClick={() => setIsHeroCollapsed(true)}
                          className="flex items-center gap-1 text-[10px] text-slate-300 hover:text-white px-2 py-0.5 rounded bg-slate-700/60 border border-slate-600/60 transition shrink-0"
                          title="收起"
                        >
                          <span>收起</span>
                          <ChevronUp className="w-3 h-3" />
                        </button>
                      </div>
                    )
                  )}

                  <div className="p-2 sm:p-2.5 text-xs leading-relaxed font-serif">
                    <div className="flex items-center justify-between text-amber-400 font-semibold mb-1 text-xs font-sans uppercase tracking-wider gap-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        <Sparkles className="w-3 h-3 shrink-0" />
                        <span>当前幕境 · {currentScene.title}</span>
                        {(weather || atmosphereText) && (
                          <span className="text-[10px] font-normal normal-case tracking-normal text-slate-300/90 bg-slate-800/80 border border-slate-700/70 px-2 py-0.5 rounded-full">
                            {weather ? `${weather}` : ''}
                            {weather && atmosphereText ? ' · ' : ''}
                            {atmosphereText || ''}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={(e) => handleCopy('scene_desc', currentScene.description, e)}
                          className="flex items-center gap-1 text-[10px] text-slate-400 hover:text-amber-300 px-2 py-0.5 rounded bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700 transition"
                          title="复制场景描述"
                        >
                          {copiedId === 'scene_desc' ? (
                            <>
                              <Check className="w-3 h-3 text-emerald-400" />
                              <span className="text-emerald-400 text-[9px]">已复制</span>
                            </>
                          ) : (
                            <>
                              <Copy className="w-3 h-3" />
                              <span className="text-[9px]">复制</span>
                            </>
                          )}
                        </button>
                        {!displayedHeroImage && (
                          <button
                            onClick={() => setIsHeroCollapsed(true)}
                            className="flex items-center gap-0.5 text-[10px] text-slate-400 hover:text-slate-200 px-1.5 py-0.5 rounded bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700 transition"
                            title="收起场景信息"
                          >
                            <ChevronUp className="w-3 h-3" />
                          </button>
                        )}
                      </div>
                    </div>
                    {/* 场景描述文本 */}
                    <div className="text-slate-300/90 select-text">
                      <p className={`whitespace-pre-line ${!isDescExpanded ? 'line-clamp-2' : ''}`}>
                        {currentScene.description}
                      </p>
                      {currentScene.description && currentScene.description.length > 80 && (
                        <button
                          onClick={() => setIsDescExpanded(!isDescExpanded)}
                          className="mt-0.5 text-[10px] text-amber-400/80 hover:text-amber-300 underline font-sans"
                        >
                          {isDescExpanded ? '收起描述' : '展开全文'}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* 历史消息流与对话区 - 独立向下滚动，至少占画面大半空间 */}
        <div
          ref={scrollRef}
          className="relative flex-1 min-h-[35vh] overflow-y-auto px-4 sm:px-6 py-2.5 space-y-4"
        >

        {/* 历史消息流 */}
        {messages.map((msg) => {
          if (msg.kind === 'user') {
            return (
              <div key={msg.id} className="flex justify-end animate-in fade-in duration-200">
                <div className="flex items-start gap-2.5 max-w-[85%]">
                  <div className="group relative bg-amber-600/90 text-amber-50 rounded-2xl rounded-tr-none px-4 py-2.5 text-sm shadow-md border border-amber-500/50">
                    <div className="flex items-center justify-between text-[10px] text-amber-200/80 mb-0.5 font-medium gap-3">
                      <span>玩家决策</span>
                      <button
                        onClick={(e) => handleCopy(msg.id, msg.content, e)}
                        className="opacity-60 group-hover:opacity-100 p-0.5 rounded hover:bg-amber-700/80 transition"
                        title="复制决策文本"
                      >
                        {copiedId === msg.id ? (
                          <Check className="w-3 h-3 text-emerald-300" />
                        ) : (
                          <Copy className="w-3 h-3 text-amber-100" />
                        )}
                      </button>
                    </div>
                    <div className="leading-relaxed whitespace-pre-wrap select-text">{msg.content}</div>
                  </div>
                  <div className="w-8 h-8 rounded-full bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400 shrink-0">
                    <User className="w-4 h-4" />
                  </div>
                </div>
              </div>
            );
          }

          if (msg.kind === 'dialogue') {
            return (
              <div key={msg.id} className="flex justify-start animate-in fade-in duration-200">
                <div className="flex items-start gap-3 max-w-[90%]">
                  <div className="w-8 h-8 rounded-full bg-indigo-500/20 border border-indigo-500/40 flex items-center justify-center text-indigo-400 shrink-0 mt-1">
                    <MessageSquare className="w-4 h-4" />
                  </div>
                  <div className="group relative bg-slate-900/90 border border-slate-700/80 rounded-2xl rounded-tl-none p-4 text-sm text-slate-200 shadow-lg backdrop-blur">
                    <div className="flex items-center justify-between text-xs font-semibold text-indigo-300 mb-1.5 gap-3">
                      <span>{msg.speaker || '人物对话'}</span>
                      <button
                        onClick={(e) => handleCopy(msg.id, msg.content, e)}
                        className="opacity-50 group-hover:opacity-100 p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-indigo-200 transition"
                        title="复制对话内容"
                      >
                        {copiedId === msg.id ? (
                          <Check className="w-3 h-3 text-emerald-400" />
                        ) : (
                          <Copy className="w-3 h-3" />
                        )}
                      </button>
                    </div>
                    <div className="leading-relaxed whitespace-pre-wrap font-serif text-slate-100 select-text">
                      {msg.content}
                    </div>
                  </div>
                </div>
              </div>
            );
          }

          if (msg.kind === 'system') {
            return (
              <div key={msg.id} className="flex justify-center my-2 group">
                <div className="flex items-center gap-2 bg-slate-900/90 border border-slate-700 text-xs text-amber-400/90 px-3.5 py-1.5 rounded-full shadow">
                  <Terminal className="w-3.5 h-3.5 text-amber-400" />
                  <span className="select-text">{msg.content}</span>
                  <button
                    onClick={(e) => handleCopy(msg.id, msg.content, e)}
                    className="opacity-0 group-hover:opacity-100 ml-1 p-0.5 rounded text-slate-400 hover:text-amber-300 transition"
                    title="复制系统消息"
                  >
                    {copiedId === msg.id ? (
                      <Check className="w-3 h-3 text-emerald-400" />
                    ) : (
                      <Copy className="w-3 h-3" />
                    )}
                  </button>
                </div>
              </div>
            );
          }

          // 默认：Narrator 旁白
          return (
            <div key={msg.id} className="flex justify-start animate-in fade-in duration-200">
              <div className="group relative max-w-[92%] bg-slate-900/75 border border-slate-800 rounded-xl p-4 text-sm text-slate-200 shadow backdrop-blur-sm">
                <div className="flex items-center justify-between text-[11px] font-sans uppercase tracking-wider text-slate-500 mb-1.5 font-medium">
                  <div className="flex items-center gap-1">
                    <Sparkles className="w-3 h-3 text-amber-500" />
                    <span>DM 叙事判定</span>
                  </div>
                  <button
                    onClick={(e) => handleCopy(msg.id, msg.content, e)}
                    className="opacity-50 group-hover:opacity-100 p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-amber-300 transition"
                    title="复制旁白内容"
                  >
                    {copiedId === msg.id ? (
                      <Check className="w-3 h-3 text-emerald-400" />
                    ) : (
                      <Copy className="w-3 h-3" />
                    )}
                  </button>
                </div>
                {msg.hero_image && (
                  <div className="mb-3 rounded-lg overflow-hidden border border-slate-700 bg-slate-800">
                    {isImageSrc(msg.hero_image) ? (
                      <div className="relative group max-h-56 overflow-hidden bg-slate-950">
                        <img
                          src={msg.hero_image}
                          alt="Clue"
                          className="w-full max-h-56 object-cover hover:scale-105 transition-transform duration-500"
                        />
                        <div className="p-2 text-xs text-amber-300 flex items-center gap-1.5 bg-slate-900/90 border-t border-slate-800">
                          <ImageIcon className="w-3.5 h-3.5" />
                          <span>线索特写插图</span>
                        </div>
                      </div>
                    ) : (
                      <div className="p-2 text-xs text-amber-300 flex items-center gap-2 bg-slate-850">
                        <ImageIcon className="w-3.5 h-3.5" />
                        <span>线索视觉特写：{msg.hero_image}</span>
                      </div>
                    )}
                  </div>
                )}
                <div className="leading-relaxed whitespace-pre-wrap font-serif text-slate-200 select-text">
                  {msg.content}
                </div>
              </div>
            </div>
          );
        })}

        {/* 正在流式打字输出的文本 */}
        {isStreaming && streamingText && (
          <div className="flex justify-start animate-in fade-in duration-100">
            <div className="max-w-[92%] bg-slate-900/85 border border-amber-500/40 rounded-xl p-4 text-sm text-slate-200 shadow-xl backdrop-blur-sm">
              <div className="text-[11px] font-sans uppercase tracking-wider text-amber-400/90 mb-1.5 font-medium flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
                <span>DM 正在推演剧情与场景视觉...</span>
              </div>
              <div className="leading-relaxed whitespace-pre-wrap font-serif text-slate-100 select-text">
                {streamingText}
                <span className="inline-block w-1.5 h-4 ml-1 bg-amber-400 animate-pulse align-middle" />
              </div>
            </div>
          </div>
        )}
      </div>
      </main>
    </div>
  );
}
