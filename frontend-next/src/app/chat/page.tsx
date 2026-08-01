"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Send, Bot, User, Trash2, MessageSquare, X, Menu, Loader2 } from "lucide-react";
import { useAuth } from "@/lib/auth";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface ChatSession {
  session_id: string;
  title?: string;
  message_count?: number;
}

export default function ChatPage() {
  const { token, authFetch } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const [showSessions, setShowSessions] = useState(false);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const fetchSessions = useCallback(async () => {
    if (!token) return;
    setSessionsLoading(true);
    try {
      const resp = await authFetch("/api/chat/sessions");
      if (resp.ok) {
        const data = await resp.json();
        setSessions(data.sessions || []);
      }
    } catch { /* ignore */ }
    finally { setSessionsLoading(false); }
  }, [token, authFetch]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (token && showSessions) fetchSessions();
  }, [token, showSessions, fetchSessions]);

  async function loadSession(sid: string) {
    try {
      const resp = await authFetch(`/api/chat/session/${sid}`);
      if (resp.ok) {
        const data = await resp.json();
        setMessages(data.messages || []);
        setSessionId(sid);
        setShowSessions(false);
      }
    } catch { /* ignore */ }
  }

  async function deleteSession(sid: string) {
    try {
      const resp = await authFetch(`/api/chat/session/${sid}`, { method: "DELETE" });
      if (resp.ok) {
        if (sessionId === sid) {
          setMessages([]);
          setSessionId(null);
        }
        fetchSessions();
      }
    } catch { /* ignore */ }
  }

  async function sendMessage() {
    if (!input.trim() || streaming) return;

    const userMsg: Message = { role: "user", content: input };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setStreaming(true);
    setError(null);

    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    try {
      const resp = await authFetch("/api/chat/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: input,
          session_id: sessionId,
        }),
      });

      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error((errData as { detail?: string }).detail || `请求失败 (HTTP ${resp.status})`);
      }

      const reader = resp.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === "token") {
                setMessages((prev) => {
                  const updated = [...prev];
                  updated[updated.length - 1] = {
                    ...updated[updated.length - 1],
                    content: updated[updated.length - 1].content + data.content,
                  };
                  return updated;
                });
              } else if (data.type === "done") {
                setSessionId(data.session_id);
              } else if (data.type === "error") {
                setError(data.message || "服务异常");
              }
            } catch {
              // skip parse errors for incomplete chunks
            }
          }
        }
      }
    } catch (error: unknown) {
      console.error("Send failed:", error);
      setError(error instanceof Error ? error.message : String(error) || "发送失败");
    } finally {
      setStreaming(false);
    }
  }

  function clearChat() {
    setMessages([]);
    setSessionId(null);
  }

  if (!token) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900">
        <div className="text-center text-gray-400">
          <Bot size={48} className="mx-auto mb-4 opacity-50" />
          <p className="text-lg">请先登录以使用 AI 运维助手</p>
          <a href="/login" className="text-blue-400 hover:underline mt-2 inline-block">前往登录</a>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-64px)] max-w-5xl mx-auto">
      {showSessions && (
        <div className="w-64 bg-gray-800/50 border-r border-gray-700 flex flex-col flex-shrink-0">
          <div className="flex items-center justify-between p-3 border-b border-gray-700">
            <span className="text-sm font-medium text-white">历史会话</span>
            <button onClick={() => setShowSessions(false)} className="text-gray-400 hover:text-white"><X size={16} /></button>
          </div>
          <div className="flex-1 overflow-y-auto p-2">
            {sessionsLoading ? (
              <div className="text-center text-gray-500 text-sm py-4"><Loader2 size={16} className="animate-spin mx-auto" /></div>
            ) : sessions.length === 0 ? (
              <div className="text-center text-gray-500 text-sm py-4">暂无历史会话</div>
            ) : (
              sessions.map((s) => (
                <div key={s.session_id} className="flex items-center justify-between p-2 rounded-lg hover:bg-gray-700/50 group">
                  <button onClick={() => loadSession(s.session_id)} className="text-left flex-1 text-sm text-gray-400 hover:text-white truncate">
                    <MessageSquare size={14} className="inline mr-1" />
                    {s.title || s.session_id.slice(0, 8)}
                  </button>
                  <button onClick={() => deleteSession(s.session_id)}
                    className="text-gray-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition">
                    <Trash2 size={14} />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      <div className="flex-1 flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <div className="flex items-center gap-2">
            <button onClick={() => setShowSessions(!showSessions)} className="text-gray-400 hover:text-white transition">
              <Menu size={20} />
            </button>
            <h1 className="text-lg font-semibold text-white flex items-center gap-2">
              <Bot size={20} /> AI 运维助手
            </h1>
          </div>
          <button onClick={clearChat} className="text-gray-400 hover:text-red-400 transition">
            <Trash2 size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 && (
            <div className="text-center text-gray-500 mt-20">
              <Bot size={48} className="mx-auto mb-4 opacity-50" />
              <p>向 AI 运维助手提问，获取运维建议和诊断帮助</p>
              <p className="text-sm mt-2">支持流式响应，逐字实时展示</p>
            </div>
          )}
          {messages.map((msg, i) => (
            <div key={i} className={`flex gap-3 ${msg.role === "user" ? "justify-end" : ""}`}>
              {msg.role === "assistant" && (
                <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0">
                  <Bot size={16} />
                </div>
              )}
              <div className={`max-w-[80%] rounded-xl px-4 py-2 ${
                msg.role === "user" ? "bg-blue-600 text-white" : "bg-gray-800 border border-gray-700 text-gray-100"
              }`}>
                <pre className="whitespace-pre-wrap font-sans text-sm">{msg.content || (streaming ? "..." : "")}</pre>
              </div>
              {msg.role === "user" && (
                <div className="w-8 h-8 rounded-full bg-gray-600 flex items-center justify-center flex-shrink-0">
                  <User size={16} />
                </div>
              )}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        <div className="p-4 border-t border-gray-700">
          <div className="flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendMessage()}
              placeholder="输入运维问题，如：如何排查 CPU 过高..."
              className="flex-1 bg-gray-800 border border-gray-600 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
              disabled={streaming}
            />
            <button
              onClick={sendMessage}
              disabled={streaming || !input.trim()}
              className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 px-4 py-2 rounded-lg text-white transition"
            >
              <Send size={18} />
            </button>
          </div>
          {error && <div className="text-sm text-red-400 mt-2">{error}</div>}
          {sessionId && (
            <p className="text-xs text-gray-500 mt-2">会话 ID: {sessionId}</p>
          )}
        </div>
      </div>
    </div>
  );
}
