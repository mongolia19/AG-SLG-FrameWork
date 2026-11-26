import { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Sparkles, Loader2, Copy, Check, Pencil, RefreshCw, X } from 'lucide-react';


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
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const handleCopy = (id: string, text: string, e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => {
      setCopiedId((prev) => (prev === id ? null : prev));
    }, 2000);
  };

  const defaultWelcomeMessage: AuthoringMessage = {
    id: 'welcome',
    sender: 'agent',
    content:
      '你好！我是你的编剧与场景协创 Agent (Studio Co-pilot)。\n你可以随时吩咐我扩写新场景、组织视觉图片与立绘配置、设计检定机关或重构剧情分支，我会在构思后直接为你生成并写入剧本 YAML 文件！',
    timestamp: Date.now(),
  };

  const loadCachedMessages = (sid: string): AuthoringMessage[] => {
    try {
      const saved = localStorage.getItem(`ag_slg_studio_chat_${sid}`);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) {
          return parsed;
        }
      }
    } catch (e) {
      console.warn('Failed to load studio chat cache:', e);
    }
    return [defaultWelcomeMessage];
  };

  const [messages, setMessages] = useState<AuthoringMessage[]>(() =>
    loadCachedMessages(scenarioId)
  );

  const [inputText, setInputText] = useState<string>(() => {
    try {
      return localStorage.getItem(`ag_slg_studio_draft_${scenarioId}`) || '';
    } catch {
      return '';
    }
  });

  const loadStudioThreadId = (sid: string): string => {
    try {
      const existing = localStorage.getItem(`ag_slg_studio_thread_${sid}`);
      if (existing) return existing;
      const fresh = `studio-${sid}-${Date.now()}`;
      localStorage.setItem(`ag_slg_studio_thread_${sid}`, fresh);
      return fresh;
    } catch {
      return `studio-${sid}-${Date.now()}`;
    }
  };

  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingText, setStreamingText] = useState('');
  const [activeToolName, setActiveToolName] = useState<string | null>(null);
  // 编辑上一条输入时暂存“回滚后的消息列表”，发送时用它替换上一轮对话
  const [editBase, setEditBase] = useState<AuthoringMessage[] | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const prevScenarioIdRef = useRef(scenarioId);
  const threadIdRef = useRef<string>(loadStudioThreadId(scenarioId));

  // 当切换剧本时，切换对应剧本的会话与草稿
  useEffect(() => {
    if (prevScenarioIdRef.current !== scenarioId) {
      prevScenarioIdRef.current = scenarioId;
      threadIdRef.current = loadStudioThreadId(scenarioId);
      setEditBase(null);
      setMessages(loadCachedMessages(scenarioId));
      try {
        const draft = localStorage.getItem(`ag_slg_studio_draft_${scenarioId}`) || '';
        setInputText(draft);
      } catch {
        setInputText('');
      }
    }
  }, [scenarioId]);

  // 草稿输入变更时持久化
  useEffect(() => {
    try {
      if (inputText.trim()) {
        localStorage.setItem(`ag_slg_studio_draft_${scenarioId}`, inputText);
      } else {
        localStorage.removeItem(`ag_slg_studio_draft_${scenarioId}`);
      }
    } catch (e) {
      console.warn('Failed to save studio draft:', e);
    }
  }, [scenarioId, inputText]);

  // 消息发生变动时持久化
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
  }, [messages, streamingText, isStreaming, activeToolName]);

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    const prompt = inputText.trim();
    if (!prompt || isStreaming) return;

    const base = editBase;
    setEditBase(null);
    setInputText('');
    try {
      localStorage.removeItem(`ag_slg_studio_draft_${scenarioId}`);
    } catch {}
    void runPrompt(prompt, base ?? undefined);
  };

  const lastUserIdx = (() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].sender === 'user') return i;
    }
    return -1;
  })();

  // 重新生成本轮：丢弃上一条输入之后的回复，用同样的输入重新发送
  const handleRegenerate = () => {
    if (isStreaming || lastUserIdx < 0) return;
    runPrompt(messages[lastUserIdx].content, messages.slice(0, lastUserIdx));
  };

  // 重新编辑输入：把上一条输入放回输入框，发送时替换上一轮对话
  const handleEditLast = () => {
    if (isStreaming || lastUserIdx < 0) return;
    setEditBase(messages.slice(0, lastUserIdx));
    setInputText(messages[lastUserIdx].content);
  };

  const handleCancelEdit = () => {
    setEditBase(null);
    setInputText('');
  };

  const runPrompt = async (prompt: string, baseMessages?: AuthoringMessage[]) => {
    if (isStreaming) return;

    const userMsg: AuthoringMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      content: prompt,
      timestamp: Date.now(),
    };

    // 立即保存用户发送的消息（编辑/重新生成时基于回滚后的列表）
    setMessages((prev) => {
      const next = [...(baseMessages ?? prev), userMsg];
      try {
        localStorage.setItem(`ag_slg_studio_chat_${scenarioId}`, JSON.stringify(next));
      } catch {}
      return next;
    });

    setIsStreaming(true);
    setStreamingText('');
    setActiveToolName(null);

    let accumulated = '';
    try {
      const payload = {
        thread_id: threadIdRef.current,
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

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || trimmed.startsWith(':')) continue;
          if (!trimmed.startsWith('data: ')) continue;
          try {
            const event = JSON.parse(trimmed.slice(6));
            if (event.type === 'TEXT_MESSAGE_CONTENT' && event.delta) {
              setActiveToolName(null);
              accumulated += event.delta;
              setStreamingText(accumulated);
            } else if (event.type === 'TOOL_CALL_START') {
              setActiveToolName(event.toolCallName || event.toolName || event.tool_name || '工具调用');
            } else if (event.type === 'TOOL_CALL_END') {
              setActiveToolName(null);
            } else if (event.type === 'RUN_ERROR') {
              throw new Error(event.message || 'Agent 运行异常');
            }
          } catch (parseErr: any) {
            if (parseErr instanceof SyntaxError) {
              // ignore malformed SSE chunk
            } else {
              throw parseErr;
            }
          }
        }
      }

      if (accumulated.trim()) {
        const agentMsg: AuthoringMessage = {
          id: `agent-${Date.now()}`,
          sender: 'agent',
          content: accumulated.trim(),
          timestamp: Date.now(),
        };
        setMessages((prev) => {
          const next = [...prev, agentMsg];
          try {
            localStorage.setItem(`ag_slg_studio_chat_${scenarioId}`, JSON.stringify(next));
          } catch {}
          return next;
        });
        // 触发父级剧本树静默刷新（若 Agent 输出了 scene_yaml 自动写入）
        onScenarioUpdated();
      }
    } catch (err: any) {
      const rawMsg = String(err?.message || '未知错误');
      const friendlyMsg =
        rawMsg.toLowerCase().includes('network error') || rawMsg.toLowerCase().includes('failed to fetch')
          ? `${rawMsg}（连接被中断，可能由于后端服务刚刚重启、正在启动中或代理超时，请稍后重试）`
          : rawMsg;

      setMessages((prev) => {
        const additions: AuthoringMessage[] = [];
        if (accumulated.trim()) {
          additions.push({
            id: `agent-partial-${Date.now()}`,
            sender: 'agent',
            content: accumulated.trim(),
            timestamp: Date.now(),
          });
        }
        additions.push({
          id: `err-${Date.now()}`,
          sender: 'agent',
          content: `协作请求失败: ${friendlyMsg}`,
          timestamp: Date.now(),
        });
        return [...prev, ...additions];
      });
    } finally {
      setIsStreaming(false);
      setStreamingText('');
      setActiveToolName(null);
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
            className={`group flex gap-2.5 text-xs ${
              m.sender === 'user' ? 'justify-end' : 'justify-start'
            }`}
          >
            {m.sender === 'agent' && (
              <div className="w-6 h-6 rounded-full bg-indigo-600/30 border border-indigo-500/50 flex items-center justify-center text-indigo-300 shrink-0 mt-0.5">
                <Bot className="w-3.5 h-3.5" />
              </div>
            )}

            <div
              className={`relative p-3 rounded-xl max-w-[85%] leading-relaxed ${
                m.sender === 'user'
                  ? 'bg-amber-600 text-white rounded-tr-none shadow-sm'
                  : 'bg-slate-900 border border-slate-800 text-slate-200 rounded-tl-none font-mono text-[11px]'
              }`}
            >
              <div className="flex items-center justify-between gap-2 mb-1">
                <span className="text-[10px] opacity-60 font-sans">
                  {m.sender === 'user' ? '创作指令' : 'Co-pilot'}
                </span>
                <button
                  onClick={(e) => handleCopy(m.id, m.content, e)}
                  className={`opacity-60 group-hover:opacity-100 p-0.5 rounded transition ${
                    m.sender === 'user'
                      ? 'hover:bg-amber-700/80 text-amber-100 hover:text-white'
                      : 'hover:bg-slate-800/80 text-slate-400 hover:text-slate-200'
                  }`}
                  title="复制消息内容"
                >
                  {copiedId === m.id ? (
                    <Check className={`w-3 h-3 ${m.sender === 'user' ? 'text-emerald-300' : 'text-emerald-400'}`} />
                  ) : (
                    <Copy className="w-3 h-3" />
                  )}
                </button>
              </div>
              <div className="whitespace-pre-wrap select-text">{m.content}</div>
            </div>

            {m.sender === 'user' && (
              <div className="w-6 h-6 rounded-full bg-amber-600/30 border border-amber-500/50 flex items-center justify-center text-amber-300 shrink-0 mt-0.5">
                <User className="w-3.5 h-3.5" />
              </div>
            )}
          </div>
        ))}

        {/* 流式打字与执行状态 */}
        {isStreaming && (
          <div className="flex gap-2.5 text-xs justify-start">
            <div className="w-6 h-6 rounded-full bg-indigo-600/30 border border-indigo-500/50 flex items-center justify-center text-indigo-300 shrink-0 mt-0.5">
              <Bot className="w-3.5 h-3.5" />
            </div>
            <div className="p-3 rounded-xl max-w-[85%] bg-slate-900 border border-indigo-500/50 text-slate-200 rounded-tl-none font-mono text-[11px] leading-relaxed">
              {streamingText ? (
                <div className="whitespace-pre-wrap select-text">
                  {streamingText}
                  <span className="inline-block w-1.5 h-3 ml-1 bg-indigo-400 animate-pulse align-middle" />
                </div>
              ) : (
                <div className="flex items-center gap-2 text-indigo-300/90 font-sans">
                  <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" />
                  <span>
                    {activeToolName
                      ? `正在调用工具 (${activeToolName})...`
                      : 'Co-pilot 正在读取剧本并构思方案...'}
                  </span>
                </div>
              )}
              {streamingText && activeToolName && (
                <div className="mt-2 pt-2 border-t border-slate-800 flex items-center gap-1.5 text-[10px] text-indigo-300/80 font-sans">
                  <Loader2 className="w-3 h-3 animate-spin shrink-0" />
                  <span>正在调用工具 ({activeToolName})...</span>
                </div>
              )}
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

      {/* 上一轮操作：编辑输入 / 重新生成 */}
      {editBase ? (
        <div className="px-3 py-1.5 border-t border-slate-800/80 bg-indigo-950/40 flex items-center gap-2 text-[10px] text-indigo-200">
          <Pencil className="w-3 h-3 shrink-0" />
          <span className="flex-1">正在编辑上一条输入，发送后将替换上一轮对话</span>
          <button
            type="button"
            onClick={handleCancelEdit}
            className="p-0.5 rounded hover:bg-indigo-900/60 text-indigo-300 hover:text-white transition"
            title="取消编辑"
          >
            <X className="w-3 h-3" />
          </button>
        </div>
      ) : (
        !isStreaming &&
        lastUserIdx >= 0 && (
          <div className="px-3 py-1.5 border-t border-slate-800/80 bg-slate-950 flex items-center gap-1.5">
            <button
              type="button"
              onClick={handleEditLast}
              className="flex items-center gap-1 text-[10px] text-slate-400 hover:text-slate-200 px-2 py-0.5 rounded border border-slate-800 hover:border-slate-600 transition"
              title="修改上一条输入后重新发送"
            >
              <Pencil className="w-3 h-3" /> 编辑上一条
            </button>
            <button
              type="button"
              onClick={handleRegenerate}
              className="flex items-center gap-1 text-[10px] text-slate-400 hover:text-indigo-300 px-2 py-0.5 rounded border border-slate-800 hover:border-indigo-500/60 transition"
              title="丢弃上一轮回复并用同样的输入重新生成"
            >
              <RefreshCw className="w-3 h-3" /> 重新生成
            </button>
          </div>
        )
      )}

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
