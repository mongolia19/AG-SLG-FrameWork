import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Sparkles, Loader2 } from 'lucide-react';


interface AuthoringMessage {
  id: string;
  sender: 'user' | 'agent';
  content: string;
  timestamp: number;
}

interface AuthoringChatProps {
  scenarioId: string;
  onScenarioUpdated: () => void;
}

export default function AuthoringChat({
  scenarioId,
  onScenarioUpdated,
}: AuthoringChatProps) {
  const defaultWelcomeMessage: AuthoringMessage = {
    id: 'welcome',
    sender: 'agent',
    content:
      '你好！我是你的编剧与场景协创 Agent (Studio Co-pilot)。\n你可以随时吩咐我扩写新场景、组织视觉图片与立绘配置、设计检定机关或重构剧情分支，我会在构思后直接为你生成并写入剧本 YAML 文件！',
    timestamp: Date.now(),
  };

  const [messages, setMessages] = useState<AuthoringMessage[]>([defaultWelcomeMessage]);
  const [inputText, setInputText] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingText, setStreamingText] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);

  // 加载已保存的协创对话
  useEffect(() => {
    try {
      const saved = localStorage.getItem(`ag_slg_studio_chat_${scenarioId}`);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setMessages(parsed);
          return;
        }
      }
    } catch (e) {
      console.warn('Failed to load studio chat cache:', e);
    }
    setMessages([defaultWelcomeMessage]);
  }, [scenarioId]);

  // 对话更新时自动写入缓存
  useEffect(() => {
    if (messages.length > 0) {
      try {
        localStorage.setItem(`ag_slg_studio_chat_${scenarioId}`, JSON.stringify(messages));
      } catch (e) {
        console.warn('Failed to save studio chat cache:', e);
      }
    }
  }, [scenarioId, messages]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, streamingText]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    const prompt = inputText.trim();
    if (!prompt || isStreaming) return;

    const userMsg: AuthoringMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      content: prompt,
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInputText('');
    setIsStreaming(true);
    setStreamingText('');

    try {
      const payload = {
        thread_id: `studio-${Date.now()}`,
        run_id: `run-${Date.now()}`,
        messages: [
          {
            id: `msg-${Date.now()}`,
            role: 'user',
            content: [{ type: 'text', text: prompt }],
          },
        ],
        forwarded_props: { scenario_id: scenarioId },
      };

      const res = await fetch('/api/studio/run', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok || !res.body) {
        throw new Error(`HTTP error ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      let accumulated = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('data: ')) continue;
          try {
            const event = JSON.parse(trimmed.slice(6));
            if (event.type === 'TEXT_MESSAGE_CONTENT' && event.delta) {
              accumulated += event.delta;
              setStreamingText(accumulated);
            }
          } catch {
            // ignore
          }
        }
      }

      if (accumulated.trim()) {
        setMessages((prev) => [
          ...prev,
          {
            id: `agent-${Date.now()}`,
            sender: 'agent',
            content: accumulated.trim(),
            timestamp: Date.now(),
          },
        ]);
        // 触发父级剧本树刷新（若 Agent 输出了 scene_yaml 自动写入）
        onScenarioUpdated();
      }
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          sender: 'agent',
          content: `协作请求失败: ${err.message || '未知错误'}`,
          timestamp: Date.now(),
        },
      ]);
    } finally {
      setIsStreaming(false);
      setStreamingText('');
    }
  };

  return (
    <div className="w-96 bg-[#11131a] border-l border-slate-800 flex flex-col h-full z-10">
      <div className="p-3.5 border-b border-slate-800 flex items-center gap-2">
        <Sparkles className="w-4 h-4 text-amber-400" />
        <span className="text-xs font-bold text-slate-200 tracking-wide">
          编剧 Co-pilot (本地 Agent)
        </span>
      </div>

      {/* 消息历史 */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((m) => (
          <div
            key={m.id}
            className={`flex gap-2.5 text-xs ${
              m.sender === 'user' ? 'justify-end' : 'justify-start'
            }`}
          >
            {m.sender === 'agent' && (
              <div className="w-6 h-6 rounded-full bg-indigo-600/30 border border-indigo-500/50 flex items-center justify-center text-indigo-300 shrink-0 mt-0.5">
                <Bot className="w-3.5 h-3.5" />
              </div>
            )}

            <div
              className={`p-3 rounded-xl max-w-[85%] leading-relaxed ${
                m.sender === 'user'
                  ? 'bg-amber-600 text-white rounded-tr-none shadow-sm'
                  : 'bg-slate-900 border border-slate-800 text-slate-200 rounded-tl-none font-mono text-[11px]'
              }`}
            >
              <div className="whitespace-pre-wrap">{m.content}</div>
            </div>

            {m.sender === 'user' && (
              <div className="w-6 h-6 rounded-full bg-amber-600/30 border border-amber-500/50 flex items-center justify-center text-amber-300 shrink-0 mt-0.5">
                <User className="w-3.5 h-3.5" />
              </div>
            )}
          </div>
        ))}

        {/* 流式打字 */}
        {isStreaming && streamingText && (
          <div className="flex gap-2.5 text-xs justify-start">
            <div className="w-6 h-6 rounded-full bg-indigo-600/30 border border-indigo-500/50 flex items-center justify-center text-indigo-300 shrink-0 mt-0.5">
              <Bot className="w-3.5 h-3.5" />
            </div>
            <div className="p-3 rounded-xl max-w-[85%] bg-slate-900 border border-indigo-500/50 text-slate-200 rounded-tl-none font-mono text-[11px] leading-relaxed">
              <div className="whitespace-pre-wrap">
                {streamingText}
                <span className="inline-block w-1.5 h-3 ml-1 bg-indigo-400 animate-pulse align-middle" />
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 快捷创作提示 */}
      <div className="p-2 border-t border-slate-800/80 bg-slate-950 flex flex-wrap gap-1.5">
        <button
          onClick={() =>
            setInputText('在公馆地窖与门厅走廊之间设计一个【隐秘密室】场景，包含一张关于家主死因的泛黄日记主图特写')
          }
          className="text-[10px] text-slate-400 hover:text-slate-200 bg-slate-900 px-2 py-0.5 rounded border border-slate-800 hover:border-slate-700 transition line-clamp-1"
        >
          + 扩写【隐秘密室】场景与插画
        </button>
      </div>

      {/* 输入栏 */}
      <form onSubmit={handleSend} className="p-3 border-t border-slate-800 bg-[#141721] flex gap-2">
        <input
          type="text"
          disabled={isStreaming}
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          placeholder="吩咐编剧 Agent 扩写或修改场景..."
          className="flex-1 bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={isStreaming || !inputText.trim()}
          className="px-3.5 py-2 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 disabled:opacity-50 text-white rounded-lg transition"
        >
          {isStreaming ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
        </button>
      </form>
    </div>
  );
}
