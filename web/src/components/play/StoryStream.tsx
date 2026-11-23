import { useEffect, useRef } from 'react';
import { StoryMessage, SceneNode, NPC, PropDecoration } from '../../types';
import { User, Sparkles, MessageSquare, Terminal, Image as ImageIcon } from 'lucide-react';

interface StoryStreamProps {
  messages: StoryMessage[];
  currentScene?: SceneNode;
  streamingText?: string;
  isStreaming?: boolean;
}

export default function StoryStream({
  messages,
  currentScene,
  streamingText,
  isStreaming,
}: StoryStreamProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

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

  const decorations: PropDecoration[] =
    currentScene?.visuals?.decorations || currentScene?.decorations || [];
  const leftDecorations = decorations.filter((d) => d.side === 'left');
  const rightDecorations = decorations.filter((d) => d.side === 'right');

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

      {/* 2a. 左侧场景氛围物件 (Left Margin Scenery Props) */}
      {leftDecorations.length > 0 && (
        <aside
          aria-label="左侧环境氛围物"
          className="absolute left-3 xl:left-8 top-6 bottom-6 z-10 hidden lg:flex flex-col gap-3.5 pointer-events-auto select-none w-32 xl:w-40 justify-start items-center overflow-y-auto no-scrollbar py-2"
        >
          {leftDecorations.map((item, idx) => (
            <div
              key={item.id || idx}
              className="group relative w-full bg-slate-900/85 hover:bg-slate-800/95 border border-slate-700/70 hover:border-amber-500/60 rounded-xl overflow-hidden shadow-2xl backdrop-blur-md transition-all duration-300 hover:scale-[1.03] animate-in fade-in slide-in-from-left-4"
              title={item.tooltip || item.caption || item.name}
            >
              <div className="w-full h-24 xl:h-32 overflow-hidden bg-slate-950/70 relative">
                <img
                  src={item.image}
                  alt={item.name}
                  className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-slate-950/90 via-slate-950/20 to-transparent" />
                <span className="absolute bottom-1.5 left-2 right-2 text-[11px] font-medium text-amber-300 drop-shadow truncate">
                  {item.caption || item.name}
                </span>
              </div>
              <div className="px-2 py-1 bg-slate-950/70 border-t border-slate-800/80 flex items-center justify-between">
                <span className="text-[10px] text-slate-300 font-sans truncate">
                  {item.name}
                </span>
                <span className="text-[9px] font-mono text-amber-400 bg-amber-950/60 px-1 py-0.5 rounded border border-amber-800/40 shrink-0">
                  环境
                </span>
              </div>
            </div>
          ))}
        </aside>
      )}

      {/* 2b. 右侧场景氛围物件 (Right Margin Scenery Props) */}
      {rightDecorations.length > 0 && (
        <aside
          aria-label="右侧环境氛围物"
          className={`absolute right-3 xl:right-8 ${
            primaryNPC || foregroundImage ? 'top-6 max-h-[calc(100%-19rem)]' : 'top-6 bottom-6'
          } z-10 hidden lg:flex flex-col gap-3.5 pointer-events-auto select-none w-32 xl:w-40 justify-start items-center overflow-y-auto no-scrollbar py-2`}
        >
          {rightDecorations.map((item, idx) => (
            <div
              key={item.id || idx}
              className="group relative w-full bg-slate-900/85 hover:bg-slate-850/95 border border-slate-700/70 hover:border-amber-500/60 rounded-xl overflow-hidden shadow-2xl backdrop-blur-md transition-all duration-300 hover:scale-[1.03] animate-in fade-in slide-in-from-right-4"
              title={item.tooltip || item.caption || item.name}
            >
              <div className="w-full h-24 xl:h-32 overflow-hidden bg-slate-950/70 relative">
                <img
                  src={item.image}
                  alt={item.name}
                  className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-slate-950/90 via-slate-950/20 to-transparent" />
                <span className="absolute bottom-1.5 left-2 right-2 text-[11px] font-medium text-amber-300 drop-shadow truncate">
                  {item.caption || item.name}
                </span>
              </div>
              <div className="px-2 py-1 bg-slate-950/70 border-t border-slate-800/80 flex items-center justify-between">
                <span className="text-[10px] text-slate-300 font-sans truncate">
                  {item.name}
                </span>
                <span className="text-[9px] font-mono text-amber-400 bg-amber-950/60 px-1 py-0.5 rounded border border-amber-800/40 shrink-0">
                  环境
                </span>
              </div>
            </div>
          ))}
        </aside>
      )}

      {/* 3. 剧情流内容视窗 */}
      <div
        ref={scrollRef}
        className="relative z-10 flex-1 overflow-y-auto px-6 py-6 space-y-5 max-w-4xl w-full mx-auto"
      >
        {/* 场景开场卡片与主图 (Hero Image) */}
        {currentScene && (
          <div className="bg-slate-900/80 border border-slate-800/80 rounded-xl overflow-hidden backdrop-blur-sm text-slate-300 shadow-xl">
            {heroImage && (
              <div className="w-full h-52 bg-slate-800/90 relative flex items-center justify-center overflow-hidden border-b border-slate-800">
                {isImageSrc(heroImage) ? (
                  <img
                    src={heroImage}
                    alt={currentScene.title}
                    className="w-full h-full object-cover hover:scale-105 transition-transform duration-700"
                  />
                ) : (
                  <div className="flex flex-col items-center text-slate-400">
                    <ImageIcon className="w-8 h-8 mb-1.5 text-amber-500/70" />
                    <span className="text-xs font-mono font-medium tracking-wide">
                      【场景焦点图】{heroImage}
                    </span>
                  </div>
                )}
                <div className="absolute inset-0 bg-gradient-to-t from-slate-950/90 via-transparent to-transparent" />
              </div>
            )}

            <div className="p-4 text-xs sm:text-sm leading-relaxed font-serif">
              <div className="flex items-center gap-2 text-amber-400 font-semibold mb-1.5 text-xs font-sans uppercase tracking-wider">
                <Sparkles className="w-3.5 h-3.5" />
                <span>当前幕境 · {currentScene.title}</span>
              </div>
              <p className="whitespace-pre-line text-slate-300/90">{currentScene.description}</p>
            </div>
          </div>
        )}

        {/* 历史消息流 */}
        {messages.map((msg) => {
          if (msg.kind === 'user') {
            return (
              <div key={msg.id} className="flex justify-end animate-in fade-in duration-200">
                <div className="flex items-start gap-2.5 max-w-[85%]">
                  <div className="bg-amber-600/90 text-amber-50 rounded-2xl rounded-tr-none px-4 py-2.5 text-sm shadow-md border border-amber-500/50">
                    <div className="text-[10px] text-amber-200/80 mb-0.5 font-medium">玩家决策</div>
                    <div className="leading-relaxed whitespace-pre-wrap">{msg.content}</div>
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
                  <div className="bg-slate-900/90 border border-slate-700/80 rounded-2xl rounded-tl-none p-4 text-sm text-slate-200 shadow-lg backdrop-blur">
                    <div className="text-xs font-semibold text-indigo-300 mb-1.5 flex items-center gap-1.5">
                      <span>{msg.speaker || '人物对话'}</span>
                    </div>
                    <div className="leading-relaxed whitespace-pre-wrap font-serif text-slate-100">
                      {msg.content}
                    </div>
                  </div>
                </div>
              </div>
            );
          }

          if (msg.kind === 'system') {
            return (
              <div key={msg.id} className="flex justify-center my-2">
                <div className="flex items-center gap-2 bg-slate-900/90 border border-slate-700 text-xs text-amber-400/90 px-3.5 py-1.5 rounded-full shadow">
                  <Terminal className="w-3.5 h-3.5 text-amber-400" />
                  <span>{msg.content}</span>
                </div>
              </div>
            );
          }

          // 默认：Narrator 旁白
          return (
            <div key={msg.id} className="flex justify-start animate-in fade-in duration-200">
              <div className="max-w-[92%] bg-slate-900/75 border border-slate-800 rounded-xl p-4 text-sm text-slate-200 shadow backdrop-blur-sm">
                <div className="text-[11px] font-sans uppercase tracking-wider text-slate-500 mb-1.5 font-medium flex items-center gap-1">
                  <Sparkles className="w-3 h-3 text-amber-500" />
                  <span>DM 叙事判定</span>
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
                <div className="leading-relaxed whitespace-pre-wrap font-serif text-slate-200">
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
              <div className="leading-relaxed whitespace-pre-wrap font-serif text-slate-100">
                {streamingText}
                <span className="inline-block w-1.5 h-4 ml-1 bg-amber-400 animate-pulse align-middle" />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
