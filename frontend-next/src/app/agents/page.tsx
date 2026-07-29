"use client";

import { useEffect, useState } from "react";
import { Bot, Play, Terminal, Loader2, Server, AlertTriangle, CheckCircle2, XCircle } from "lucide-react";
import { useAuth } from "@/lib/auth";

interface AgentType {
  type: string;
  name: string;
  description: string;
}

interface ServerItem {
  id: string;
  name: string;
  host: string;
  port: number;
  username: string;
  enabled: boolean;
}

export default function AgentsPage() {
  const { token, authFetch } = useAuth();
  const [agents, setAgents] = useState<AgentType[]>([]);
  const [servers, setServers] = useState<ServerItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedAgent, setSelectedAgent] = useState("generic");
  const [inputText, setInputText] = useState("");
  const [selectedServerId, setSelectedServerId] = useState("");
  const [executing, setExecuting] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [execError, setExecError] = useState<string | null>(null);

  const needServer = ["monitor", "diagnostic", "remediation", "log_analyzer", "compliance_checker"];

  useEffect(() => {
    if (!token) return;
    async function fetchData() {
      setLoading(true);
      setError(null);
      try {
        const [agentResp, serverResp] = await Promise.all([
          authFetch("/api/agents"),
          authFetch("/api/servers"),
        ]);
        if (!agentResp.ok) throw new Error(`Agent HTTP ${agentResp.status}`);
        const agentData = await agentResp.json();
        setAgents(agentData.agents || []);
        if (serverResp.ok) {
          const serverData = await serverResp.json();
          setServers((Array.isArray(serverData) ? serverData : serverData.items || []).filter((s: ServerItem) => s.enabled));
        }
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [token, authFetch]);

  function selectAgent(type: string) {
    setSelectedAgent(type);
    setResult(null);
    setExecError(null);
    document.getElementById("execute-form")?.scrollIntoView({ behavior: "smooth" });
  }

  async function handleExecute() {
    if (!inputText.trim()) return;
    setExecuting(true);
    setExecError(null);
    setResult(null);
    try {
      const body: Record<string, unknown> = {
        agent_type: selectedAgent,
        input_text: inputText,
      };
      if (selectedServerId) body.server_id = selectedServerId;
      const resp = await authFetch("/api/agents/execute", {
        method: "POST",
        body: JSON.stringify(body),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error((err as { detail?: string }).detail || `HTTP ${resp.status}`);
      }
      const data = await resp.json();
      setResult(data);
    } catch (e: unknown) {
      setExecError(e instanceof Error ? e.message : String(e));
    } finally {
      setExecuting(false);
    }
  }

  function getAgentHint(type: string): string {
    const hints: Record<string, string> = {
      generic: "任意运维问题，AI 自动识别意图并路由到合适的专用 Agent",
      monitor: "[只读] AI 生成采集命令 → 远程获取 CPU温度/使用率、内存、磁盘、网络等指标 → 整理为结构化报告",
      diagnostic: "[只读] AI 根据故障现象生成诊断命令 → 深入排查根因 → 给出诊断结论和修复建议",
      remediation: "[可写] AI 生成修复命令 → 执行重启服务/关闭进程/清理资源等操作 → 验证修复结果",
      alert_analyzer: "纯AI分析：评估告警严重程度、优先级，结合当前活跃告警关联分析",
      log_analyzer: "[只读] AI 生成日志拉取命令 → 远程提取错误/警告/安全事件 → 分类分析异常模式",
      change_executor: "纯AI规划：生成完整的变更计划、预检步骤和回滚方案（不直接执行命令）",
      doc_generator: "纯AI生成：根据需求和服务器信息自动生成运维文档和报告",
      compliance_checker: "[只读] AI 生成安全检查命令 → 审计SSH/防火墙/密码策略/权限/端口 → 输出合规评分报告",
    };
    return hints[type] || "";
  }

  if (!token) return (
    <div className="p-8 text-center text-gray-500 mt-20">
      <Bot size={48} className="mx-auto mb-4 opacity-50" />
      <p>请先登录</p>
    </div>
  );
  if (loading) return <div className="p-8 text-gray-400">加载中...</div>;
  if (error) return <div className="p-8 text-red-500">{error}</div>;

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <h1 className="text-2xl font-bold text-white mb-6">智能代理</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mb-8">
        {agents.map((a) => (
          <div
            key={a.type}
            onClick={() => selectAgent(a.type)}
            className={`bg-gray-800/50 border rounded-xl p-4 cursor-pointer transition-all hover:scale-[1.02] ${
              selectedAgent === a.type
                ? "border-blue-500 bg-blue-600/10 shadow-lg shadow-blue-500/10"
                : "border-gray-700 hover:border-gray-500"
            }`}
          >
            <div className="flex items-center gap-2 mb-1">
              <Bot size={18} className={selectedAgent === a.type ? "text-blue-400" : "text-gray-400"} />
              <span className="text-white font-medium text-sm">{a.name}</span>
              {needServer.includes(a.type) && <Server size={12} className="text-yellow-500 ml-auto" />}
            </div>
            <div className="text-xs text-gray-500 leading-relaxed">{a.description}</div>
          </div>
        ))}
      </div>

      <div id="execute-form" className="bg-gray-800/50 border border-gray-700 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-white mb-1 flex items-center gap-2">
          <Play size={18} /> 执行代理
        </h2>
        <p className="text-xs text-gray-500 mb-4">
          {agents.find(a => a.type === selectedAgent)?.name} — {getAgentHint(selectedAgent)}
        </p>
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-300 mb-1">Agent 类型</label>
              <select
                value={selectedAgent}
                onChange={(e) => { setSelectedAgent(e.target.value); setResult(null); setExecError(null); }}
                className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
              >
                {agents.map((a) => (
                  <option key={a.type} value={a.type}>{a.name}</option>
                ))}
              </select>
            </div>
            {needServer.includes(selectedAgent) && (
              <div>
                <label className="block text-sm text-gray-300 mb-1">
                  目标服务器 {servers.length === 0 && <span className="text-yellow-400 text-xs">（暂无服务器，请先在服务器管理中添加）</span>}
                </label>
                <select
                  value={selectedServerId}
                  onChange={(e) => setSelectedServerId(e.target.value)}
                  className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
                >
                  <option value="">-- 选择服务器 --</option>
                  {servers.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} ({s.host}:{s.port} / {s.username})
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
          <div>
            <label className="block text-sm text-gray-300 mb-1">输入指令</label>
            <textarea
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              rows={3}
              placeholder={
                selectedAgent === "monitor" ? "如：采集 CPU 和内存指标" :
                selectedAgent === "diagnostic" ? "如：服务器响应缓慢，帮我诊断原因" :
                selectedAgent === "remediation" ? "如：重启 nginx 服务" :
                "输入运维指令"
              }
              className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none resize-none"
            />
          </div>
          <button
            onClick={handleExecute}
            disabled={executing || !inputText.trim() || (needServer.includes(selectedAgent) && !selectedServerId)}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed px-6 py-2 rounded-lg text-white flex items-center gap-2 text-sm transition"
          >
            {executing ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
            {executing ? "执行中..." : "执行"}
          </button>
        </div>

        {execError && (
          <div className="mt-4 p-3 bg-red-600/10 border border-red-600/30 rounded-lg text-red-400 text-sm flex items-start gap-2">
            <XCircle size={16} className="mt-0.5 shrink-0" />
            <span>{execError}</span>
          </div>
        )}
        {result && (
          <div className="mt-4">
            <div className="flex items-center gap-2 mb-2 text-sm">
              {result.status === "success" || (!result.status && !execError) ? (
                <CheckCircle2 size={16} className="text-green-400" />
              ) : result.status === "error" || result.status === "failed" ? (
                <XCircle size={16} className="text-red-400" />
              ) : (
                <AlertTriangle size={16} className="text-yellow-400" />
              )}
              <span className={result.status === "success" || !result.status ? "text-green-400" : "text-red-400"}>
                {result.agent ? `Agent: ${result.agent}` : "执行结果"}
                {result.auto_routed_from ? ` (自动路由自 ${result.auto_routed_from})` : ""}
              </span>
            </div>
            <pre className="bg-gray-900 border border-gray-700 rounded-lg p-4 text-sm text-gray-300 overflow-x-auto whitespace-pre-wrap max-h-96 overflow-y-auto">
              {typeof result.output === "string" ? result.output : JSON.stringify(result, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
