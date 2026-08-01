"use client";

import { useEffect, useState, useCallback } from "react";
import { Settings, Loader2, CheckCircle, AlertTriangle } from "lucide-react";
import { useAuth } from "@/lib/auth";

const PROVIDER_OPTIONS = [
  { value: "glm", label: "GLM (智谱·免费)" },
  { value: "deepseek", label: "DeepSeek" },
  { value: "openai", label: "OpenAI" },
];

const AGENT_TYPES = [
  { value: "generic", label: "通用助手" },
  { value: "monitor", label: "指标采集" },
  { value: "diagnostic", label: "故障诊断" },
  { value: "remediation", label: "自动修复" },
  { value: "alert_analyzer", label: "告警分析" },
  { value: "log_analyzer", label: "日志分析" },
  { value: "change_executor", label: "变更执行" },
  { value: "doc_generator", label: "文档生成" },
  { value: "compliance_checker", label: "合规检查" },
];

interface LLMConfig {
  provider: string;
  api_key: string | null;
  api_base: string | null;
  model: string | null;
}

interface AgentConfig {
  active_agents: string[];
  default_agent: string;
  preferences: Record<string, unknown>;
}

export default function SettingsPage() {
  const { token, authFetch } = useAuth();

  // LLM config state
  const [llmConfig, setLlmConfig] = useState<LLMConfig | null>(null);
  const [llmLoading, setLlmLoading] = useState(false);
  const [llmSaving, setLlmSaving] = useState(false);
  const [llmMsg, setLlmMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [llmForm, setLlmForm] = useState({ provider: "glm", api_key: "", api_base: "", model: "" });

  // Agent config state
  const [agentLoading, setAgentLoading] = useState(false);
  const [agentSaving, setAgentSaving] = useState(false);
  const [agentMsg, setAgentMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [agentForm, setAgentForm] = useState<{ active_agents: string[]; default_agent: string }>({
    active_agents: [],
    default_agent: "generic",
  });

  const fetchLlmConfig = useCallback(async () => {
    setLlmLoading(true);
    try {
      const resp = await authFetch("/api/user/llm-config");
      if (resp.ok) {
        const data: LLMConfig = await resp.json();
        setLlmConfig(data);
        setLlmForm({
          provider: data.provider || "glm",
          api_key: "",
          api_base: data.api_base || "",
          model: data.model || "",
        });
      }
    } catch {
      // ignore
    } finally {
      setLlmLoading(false);
    }
  }, [authFetch]);

  const fetchAgentConfig = useCallback(async () => {
    setAgentLoading(true);
    try {
      const resp = await authFetch("/api/user/agent-config");
      if (resp.ok) {
        const data: AgentConfig = await resp.json();
        setAgentForm({
          active_agents: data.active_agents || [],
          default_agent: data.default_agent || "generic",
        });
      }
    } catch {
      // ignore
    } finally {
      setAgentLoading(false);
    }
  }, [authFetch]);

  useEffect(() => {
    if (!token) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchLlmConfig();
    fetchAgentConfig();
  }, [token, fetchLlmConfig, fetchAgentConfig]);

  async function saveLlmConfig(e: React.FormEvent) {
    e.preventDefault();
    setLlmSaving(true);
    setLlmMsg(null);
    try {
      const body: Record<string, string> = {
        provider: llmForm.provider,
      };
      if (llmForm.api_key) body.api_key = llmForm.api_key;
      if (llmForm.api_base) body.api_base = llmForm.api_base;
      if (llmForm.model) body.model = llmForm.model;

      const resp = await authFetch("/api/user/llm-config", {
        method: "PUT",
        body: JSON.stringify(body),
      });
      if (resp.ok) {
        setLlmMsg({ type: "success", text: "LLM 配置已保存" });
        fetchLlmConfig();
      } else {
        const err = await resp.json().catch(() => ({}));
        setLlmMsg({ type: "error", text: (err as { detail?: string }).detail || "保存失败" });
      }
    } catch (e: unknown) {
      setLlmMsg({ type: "error", text: e instanceof Error ? e.message : "保存失败" });
    } finally {
      setLlmSaving(false);
    }
  }

  async function saveAgentConfig(e: React.FormEvent) {
    e.preventDefault();
    setAgentSaving(true);
    setAgentMsg(null);
    try {
      const resp = await authFetch("/api/user/agent-config", {
        method: "PUT",
        body: JSON.stringify({
          active_agents: agentForm.active_agents,
          default_agent: agentForm.default_agent,
        }),
      });
      if (resp.ok) {
        setAgentMsg({ type: "success", text: "Agent 偏好已保存" });
        fetchAgentConfig();
      } else {
        const err = await resp.json().catch(() => ({}));
        setAgentMsg({ type: "error", text: (err as { detail?: string }).detail || "保存失败" });
      }
    } catch (e: unknown) {
      setAgentMsg({ type: "error", text: e instanceof Error ? e.message : "保存失败" });
    } finally {
      setAgentSaving(false);
    }
  }

  function toggleAgent(agentType: string) {
    setAgentForm((prev) => {
      const next = prev.active_agents.includes(agentType)
        ? prev.active_agents.filter((a) => a !== agentType)
        : [...prev.active_agents, agentType];
      return { ...prev, active_agents: next };
    });
  }

  if (!token)
    return (
      <div className="p-8 text-center text-gray-500 mt-20">
        <Settings size={48} className="mx-auto mb-4 opacity-50" />
        <p>请先登录</p>
      </div>
    );

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold text-white mb-6">用户设置</h1>

      {/* LLM 配置卡片 */}
      <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-6 mb-6">
        <h2 className="text-lg font-semibold text-white mb-4">LLM API 配置</h2>
        <p className="text-sm text-gray-400 mb-4">
          配置你的个人 API Key，留空则使用全局默认配置。API Key 仅保存后四位可见。
        </p>
        {llmLoading ? (
          <div className="text-gray-400">加载中...</div>
        ) : (
          <form onSubmit={saveLlmConfig} className="space-y-4">
            <div>
              <label className="block text-sm text-gray-300 mb-1">Provider</label>
              <select
                value={llmForm.provider}
                onChange={(e) => setLlmForm({ ...llmForm, provider: e.target.value })}
                className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
              >
                {PROVIDER_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-gray-300 mb-1">API Key</label>
              <input
                type="password"
                value={llmForm.api_key}
                onChange={(e) => setLlmForm({ ...llmForm, api_key: e.target.value })}
                placeholder={llmConfig?.api_key ? `当前: ${llmConfig.api_key}` : "输入你的 API Key"}
                className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-300 mb-1">API Base URL</label>
              <input
                type="text"
                value={llmForm.api_base}
                onChange={(e) => setLlmForm({ ...llmForm, api_base: e.target.value })}
                placeholder="https://api.deepseek.com/v1"
                className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-300 mb-1">Model</label>
              <input
                type="text"
                value={llmForm.model}
                onChange={(e) => setLlmForm({ ...llmForm, model: e.target.value })}
                placeholder="deepseek-v4-flash"
                className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
              />
            </div>
            {llmMsg && (
              <div className={`text-sm rounded-lg p-2 flex items-center gap-2 ${
                llmMsg.type === "success"
                  ? "bg-green-600/10 border border-green-600/30 text-green-400"
                  : "bg-red-600/10 border border-red-600/30 text-red-400"
              }`}>
                {llmMsg.type === "success" ? <CheckCircle size={16} /> : <AlertTriangle size={16} />}
                {llmMsg.text}
              </div>
            )}
            <button
              type="submit"
              disabled={llmSaving}
              className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white py-2 px-6 rounded-lg text-sm font-medium flex items-center gap-2"
            >
              {llmSaving && <Loader2 size={16} className="animate-spin" />}
              {llmSaving ? "保存中..." : "保存 LLM 配置"}
            </button>
          </form>
        )}
      </div>

      {/* Agent 偏好卡片 */}
      <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-white mb-4">Agent 偏好</h2>
        <p className="text-sm text-gray-400 mb-4">
          选择启用的 Agent 类型，未启用的 Agent 在前端列表中隐藏。
        </p>
        {agentLoading ? (
          <div className="text-gray-400">加载中...</div>
        ) : (
          <form onSubmit={saveAgentConfig} className="space-y-4">
            <div>
              <label className="block text-sm text-gray-300 mb-2">启用的 Agent</label>
              <div className="grid grid-cols-2 gap-2">
                {AGENT_TYPES.map((agent) => (
                  <label
                    key={agent.value}
                    className={`flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer text-sm transition ${
                      agentForm.active_agents.includes(agent.value)
                        ? "border-blue-500 bg-blue-600/10 text-blue-400"
                        : "border-gray-600 bg-gray-900 text-gray-400 hover:border-gray-500"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={agentForm.active_agents.includes(agent.value)}
                      onChange={() => toggleAgent(agent.value)}
                      className="sr-only"
                    />
                    {agent.label}
                  </label>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm text-gray-300 mb-1">默认 Agent</label>
              <select
                value={agentForm.default_agent}
                onChange={(e) => setAgentForm({ ...agentForm, default_agent: e.target.value })}
                className="w-full max-w-xs bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
              >
                {AGENT_TYPES.map((agent) => (
                  <option key={agent.value} value={agent.value}>{agent.label}</option>
                ))}
              </select>
            </div>
            {agentMsg && (
              <div className={`text-sm rounded-lg p-2 flex items-center gap-2 ${
                agentMsg.type === "success"
                  ? "bg-green-600/10 border border-green-600/30 text-green-400"
                  : "bg-red-600/10 border border-red-600/30 text-red-400"
              }`}>
                {agentMsg.type === "success" ? <CheckCircle size={16} /> : <AlertTriangle size={16} />}
                {agentMsg.text}
              </div>
            )}
            <button
              type="submit"
              disabled={agentSaving}
              className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white py-2 px-6 rounded-lg text-sm font-medium flex items-center gap-2"
            >
              {agentSaving && <Loader2 size={16} className="animate-spin" />}
              {agentSaving ? "保存中..." : "保存 Agent 偏好"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
