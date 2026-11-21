import { useEffect, useRef } from 'react';
import { StoryMessage, SceneNode, NPC } from '../../types';
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

  return (
    <div className="relative flex-1 flex flex-col h-full overflow-hidden bg-slate-950">
      {/* 1. 背景图层 (Background Layer) */}
      <div className="absolute inset-0 z-0 overflow-hidden pointer-events-none">
        {bgImage && bgImage.startsWith('http') ? (
          <img
            src={bgImage}
            alt="Scene Background"
            className="w-full h-full object-cover opacity-20 filter blur-xs scale-105 transition-all duration-1000"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-slate-900 border-b border-slate-800">
            <div className="text-center p-8 opacity-25">
              <div className="text-6xl mb-3">🏰</div>
              <div className="text-xl font-serif tracking-widest text-slate-300">
                {currentScene?.title || '未知探索区域'}
              </div>
              <div className="text-xs text-slate-500 font-mono mt-1">
                {currentScene?.id || 'scene_loading'}
              </div>
            </div>
          </div>
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-[#0d1017] via-[#0d1017]/85 to-transparent z-10" />
      </div>

      {/* 2. 角色立绘图层 (Character / Foreground Layer) */}
      {(primaryNPC || foregroundImage) && (
        <div className="absolute right-8 bottom-28 z-10 hidden md:flex flex-col items-center pointer-events-none transition-all duration-700 animate-in fade-in slide-in-from-right-8">
          <div className="w-48 h-64 rounded-2xl bg-gradient-to-b from-slate-800/90 to-slate-900/95 border border-slate-700/80 shadow-2xl flex flex-col items-center justify-center p-4 backdrop-blur-md">
            {foregroundImage && foregroundImage.startsWith('http') ? (
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

      {/* 3. 剧情流内容视窗 */}
      <div
        ref={scrollRef}
        className="relative z-10 flex-1 overflow-y-auto px-6 py-6 space-y-5 max-w-4xl w-full mx-auto"
      >
        {/* 场景开场卡片与主图 (Hero Image) */}
        {currentScene && (
          <div className="bg-slate-900/70 border border-slate-800/80 rounded-xl overflow-hidden backdrop-blur-sm text-slate-300 shadow">
            {heroImage && (
              <div className="w-full h-44 bg-slate-800/90 relative flex items-center justify-center overflow-hidden border-b border-slate-800">
                {heroImage.startsWith('http') ? (
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
                <div className="absolute inset-0 bg-gradient-to-t from-slate-900 via-transparent to-transparent" />
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
                    <div className="p-2 text-xs text-amber-300 flex items-center gap-2 bg-slate-850">
                      <ImageIcon className="w-3.5 h-3.5" />
                      <span>线索视觉特写：{msg.hero_image}</span>
                    </div>
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
