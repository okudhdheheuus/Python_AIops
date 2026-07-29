"use client";

import { useEffect, useState } from "react";
import { ShieldCheck, Shield, FileText, Plus, X, Trash2, Edit3, Play, Loader2, ChevronLeft, ChevronRight } from "lucide-react";
import { useAuth } from "@/lib/auth";

interface Policy {
  id: string;
  name: string;
  description?: string;
  match_labels: Record<string, string>;
  command: string;
  timeout_seconds: number;
  enabled: boolean;
  created_at: string;
}

interface LogEntry {
  id: string;
  alert_id?: string;
  server_id?: string;
  action: string;
  command?: string;
  triggered_by: string;
  status: string;
  input_text?: string;
  output?: string;
  error_output?: string;
  exit_code?: number;
  duration_ms?: number;
  created_at: string;
}

export default function RemediationPage() {
  const { token, authFetch } = useAuth();
  const [activeTab, setActiveTab] = useState<"policies" | "logs">("policies");

  // Policies state
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [policiesLoading, setPoliciesLoading] = useState(false);
  const [policiesError, setPoliciesError] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  // Test match state
  const [testPolicyId, setTestPolicyId] = useState<string | null>(null);
  const [testLabels, setTestLabels] = useState("");
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ matched_count: number; items: Policy[] } | null>(null);

  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const pageSize = 20;

  // Logs state
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [logsError, setLogsError] = useState<string | null>(null);
  const [logPage, setLogPage] = useState(1);
  const [logTotal, setLogTotal] = useState(0);
  const [logStatusFilter, setLogStatusFilter] = useState("");

  useEffect(() => {
    if (!token) return;
    if (activeTab === "policies") fetchPolicies();
    else fetchLogs();
  }, [token, authFetch, activeTab, page, logPage, logStatusFilter]);

  async function fetchPolicies() {
    setPoliciesLoading(true);
    setPoliciesError(null);
    try {
      const resp = await authFetch(`/api/remediation/policies?page=${page}&page_size=${pageSize}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setPolicies(data.items || []);
      setTotal(data.total || 0);
    } catch (e: unknown) {
      setPoliciesError(e instanceof Error ? e.message : String(e));
    } finally {
      setPoliciesLoading(false);
    }
  }

  async function fetchLogs() {
    setLogsLoading(true);
    setLogsError(null);
    try {
      const params = new URLSearchParams();
      if (logStatusFilter) params.set("status", logStatusFilter);
      params.set("page", String(logPage));
      params.set("page_size", String(pageSize));
      const resp = await authFetch(`/api/remediation/logs?${params.toString()}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setLogs(data.items || []);
      setLogTotal(data.total || 0);
    } catch (e: unknown) {
      setLogsError(e instanceof Error ? e.message : String(e));
    } finally {
      setLogsLoading(false);
    }
  }

  async function handlePolicySubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setFormError(null);
    const form = new FormData(e.currentTarget);
    const matchLabelsStr = form.get("match_labels") as string;
    let matchLabels = {};
    try { matchLabels = matchLabelsStr ? JSON.parse(matchLabelsStr) : {}; } catch { matchLabels = {}; }

    const body = {
      name: form.get("name") as string,
      description: (form.get("description") as string) || undefined,
      match_labels: matchLabels,
      command: form.get("command") as string,
      timeout_seconds: Number(form.get("timeout_seconds")) || 30,
      enabled: form.get("enabled") === "true",
    };

    try {
      const url = editingId ? `/api/remediation/policies/${editingId}` : "/api/remediation/policies";
      const method = editingId ? "PUT" : "POST";
      const resp = await authFetch(url, { method, body: JSON.stringify(body) });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      setShowModal(false);
      setEditingId(null);
      fetchPolicies();
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDeletePolicy(id: string) {
    try {
      const resp = await authFetch(`/api/remediation/policies/${id}`, { method: "DELETE" });
      if (resp.ok) { setDeleteConfirm(null); fetchPolicies(); }
    } catch { /* ignore */ }
  }

  async function handleTestMatch(policyId: string) {
    if (testPolicyId === policyId) { setTestPolicyId(null); return; }
    setTestPolicyId(policyId);
    setTestResult(null);
    setTestLabels("");
  }

  async function executeTestMatch() {
    setTesting(true);
    try {
      let labels = {};
      try { labels = testLabels ? JSON.parse(testLabels) : {}; } catch { labels = {}; }
      const resp = await authFetch("/api/remediation/policies/test-match", {
        method: "POST",
        body: JSON.stringify(labels),
      });
      if (resp.ok) setTestResult(await resp.json());
    } catch { /* ignore */ }
    finally { setTesting(false); }
  }

  const totalPages = Math.ceil(total / pageSize);
  const logTotalPages = Math.ceil(logTotal / pageSize);

  if (!token)
    return (
      <div className="p-8 text-center text-gray-500 mt-20">
        <ShieldCheck size={48} className="mx-auto mb-4 opacity-50" />
        <p>请先登录</p>
      </div>
    );

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <h1 className="text-2xl font-bold text-white mb-6">自动修复</h1>

      <div className="flex gap-1 mb-6 bg-gray-800/50 rounded-lg p-1 w-fit">
        <button
          onClick={() => setActiveTab("policies")}
          className={`px-4 py-2 rounded-lg text-sm flex items-center gap-2 ${
            activeTab === "policies" ? "bg-blue-600 text-white" : "text-gray-400 hover:text-white"
          }`}
        >
          <Shield size={16} /> 修复策略
        </button>
        <button
          onClick={() => setActiveTab("logs")}
          className={`px-4 py-2 rounded-lg text-sm flex items-center gap-2 ${
            activeTab === "logs" ? "bg-blue-600 text-white" : "text-gray-400 hover:text-white"
          }`}
        >
          <FileText size={16} /> 修复日志
        </button>
      </div>

      {activeTab === "policies" && (
        <>
          <div className="flex justify-end mb-4">
            <button onClick={() => { setEditingId(null); setFormError(null); setShowModal(true); }}
              className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg text-white flex items-center gap-2 text-sm">
              <Plus size={16} /> 添加策略
            </button>
          </div>

          {policiesLoading ? <div className="text-gray-400 p-8">加载中...</div>
          : policiesError ? <div className="text-red-500 p-8">{policiesError}</div>
          : policies.length === 0 ? (
            <div className="text-center text-gray-500 mt-10">
              <Shield size={48} className="mx-auto mb-4 opacity-50" /><p>暂无修复策略</p>
            </div>
          ) : (
            <>
              <div className="grid gap-3">
                {policies.map((p) => (
                  <div key={p.id} className="bg-gray-800/50 border border-gray-700 rounded-xl p-4">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Shield size={18} className={p.enabled ? "text-green-400" : "text-gray-500"} />
                        <span className="text-white font-medium">{p.name}</span>
                        <span className={`text-xs px-2 py-0.5 rounded ${p.enabled ? "bg-green-600/20 text-green-400" : "bg-gray-600/20 text-gray-400"}`}>
                          {p.enabled ? "启用" : "禁用"}
                        </span>
                      </div>
                      <div className="flex items-center gap-1">
                        <button onClick={() => handleTestMatch(p.id)} className="p-1 text-gray-400 hover:text-blue-400 transition" title="测试匹配"><Play size={16} /></button>
                        <button onClick={() => { setEditingId(p.id); setFormError(null); setShowModal(true); }} className="p-1 text-gray-400 hover:text-yellow-400 transition" title="编辑"><Edit3 size={16} /></button>
                        <button onClick={() => setDeleteConfirm(p.id)} className="p-1 text-gray-400 hover:text-red-400 transition" title="删除"><Trash2 size={16} /></button>
                      </div>
                    </div>
                    {p.description && <div className="text-sm text-gray-400 mb-1">{p.description}</div>}
                    <div className="text-xs text-gray-500 font-mono">命令: {p.command}</div>
                    <div className="text-xs text-gray-600 mt-1">
                      超时: {p.timeout_seconds}s · 匹配标签: {JSON.stringify(p.match_labels)}
                    </div>

                    {testPolicyId === p.id && (
                      <div className="mt-3 p-3 bg-gray-900/50 rounded-lg">
                        <p className="text-sm text-gray-300 mb-2">测试标签匹配 (JSON)</p>
                        <textarea
                          value={testLabels}
                          onChange={(e) => setTestLabels(e.target.value)}
                          rows={3}
                          placeholder='{"severity": "critical"}'
                          className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none resize-none font-mono"
                        />
                        <button onClick={executeTestMatch} disabled={testing}
                          className="mt-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 px-3 py-1 rounded-lg text-white text-sm flex items-center gap-1">
                          {testing ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />} 测试
                        </button>
                        {testResult && (
                          <div className="mt-2 text-sm text-green-400">匹配数量: {testResult.matched_count}</div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
              {total > pageSize && (
                <div className="flex items-center justify-between mt-6 text-sm text-gray-400">
                  <span>共 {total} 条</span>
                  <div className="flex items-center gap-3">
                    <button onClick={() => setPage(p => Math.max(1, p-1))} disabled={page <= 1} className="p-1 hover:text-white disabled:opacity-30"><ChevronLeft size={18} /></button>
                    <span>第 {page} / {totalPages} 页</span>
                    <button onClick={() => setPage(p => Math.min(totalPages, p+1))} disabled={page >= totalPages} className="p-1 hover:text-white disabled:opacity-30"><ChevronRight size={18} /></button>
                  </div>
                </div>
              )}
            </>
          )}
        </>
      )}

      {activeTab === "logs" && (
        <>
          <div className="flex gap-2 mb-4">
            {["", "success", "failed", "running"].map(s => (
              <button key={s} onClick={() => { setLogStatusFilter(s); setLogPage(1); }}
                className={`px-3 py-1 rounded-lg text-sm ${logStatusFilter === s ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"}`}>
                {s || "全部"}
              </button>
            ))}
          </div>

          {logsLoading ? <div className="text-gray-400 p-8">加载中...</div>
          : logsError ? <div className="text-red-500 p-8">{logsError}</div>
          : logs.length === 0 ? (
            <div className="text-center text-gray-500 mt-10">
              <FileText size={48} className="mx-auto mb-4 opacity-50" /><p>暂无修复日志</p>
            </div>
          ) : (
            <>
              <div className="grid gap-3">
                {logs.map((l) => (
                  <div key={l.id} className="bg-gray-800/50 border border-gray-700 rounded-xl p-4">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className={`text-xs px-2 py-0.5 rounded ${
                          l.status === "success" ? "bg-green-600/20 text-green-400"
                          : l.status === "failed" ? "bg-red-600/20 text-red-400"
                          : "bg-yellow-600/20 text-yellow-400"}`}>{l.status}</span>
                        <span className="text-white font-medium">{l.action}</span>
                      </div>
                      <span className="text-xs text-gray-500">{new Date(l.created_at).toLocaleString()}</span>
                    </div>
                    <div className="text-sm text-gray-400">触发者: {l.triggered_by}</div>
                    {l.command && <div className="text-xs text-gray-500 font-mono mt-1">命令: {l.command}</div>}
                    {l.output && <pre className="text-xs text-green-400 mt-1 bg-gray-900/50 p-2 rounded overflow-x-auto">{l.output.slice(0, 500)}</pre>}
                    {l.error_output && <pre className="text-xs text-red-400 mt-1 bg-gray-900/50 p-2 rounded overflow-x-auto">{l.error_output.slice(0, 500)}</pre>}
                    <div className="text-xs text-gray-500 mt-1">退出码: {l.exit_code} · 耗时: {l.duration_ms}ms</div>
                  </div>
                ))}
              </div>
              {logTotal > pageSize && (
                <div className="flex items-center justify-between mt-6 text-sm text-gray-400">
                  <span>共 {logTotal} 条</span>
                  <div className="flex items-center gap-3">
                    <button onClick={() => setLogPage(p => Math.max(1, p-1))} disabled={logPage <= 1} className="p-1 hover:text-white disabled:opacity-30"><ChevronLeft size={18} /></button>
                    <span>第 {logPage} / {logTotalPages} 页</span>
                    <button onClick={() => setLogPage(p => Math.min(logTotalPages, p+1))} disabled={logPage >= logTotalPages} className="p-1 hover:text-white disabled:opacity-30"><ChevronRight size={18} /></button>
                  </div>
                </div>
              )}
            </>
          )}
        </>
      )}

      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-800 border border-gray-700 rounded-xl w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-white">{editingId ? "编辑策略" : "添加策略"}</h2>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-white"><X size={20} /></button>
            </div>
            <form onSubmit={handlePolicySubmit} className="space-y-3">
              <InputField label="名称" name="name" required />
              <InputField label="描述" name="description" />
              <div>
                <label className="block text-sm text-gray-300 mb-1">匹配标签 (JSON)</label>
                <textarea name="match_labels" rows={3} placeholder='{"severity": "critical"}' className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none resize-none font-mono" />
              </div>
              <InputField label="修复命令" name="command" required placeholder="systemctl restart nginx" />
              <InputField label="超时时间 (秒)" name="timeout_seconds" type="number" defaultValue="30" />
              <div>
                <label className="block text-sm text-gray-300 mb-1">状态</label>
                <select name="enabled" className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none">
                  <option value="true">启用</option>
                  <option value="false">禁用</option>
                </select>
              </div>
              {formError && <p className="text-red-400 text-sm">{formError}</p>}
              <button type="submit" disabled={submitting} className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white py-2 rounded-lg text-sm font-medium flex items-center justify-center gap-2">
                {submitting && <Loader2 size={16} className="animate-spin" />}
                {submitting ? "提交中..." : editingId ? "保存修改" : "确认添加"}
              </button>
            </form>
          </div>
        </div>
      )}

      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-800 border border-gray-700 rounded-xl p-6 max-w-sm">
            <p className="text-white mb-4">确认删除此策略？</p>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setDeleteConfirm(null)} className="px-4 py-2 rounded-lg bg-gray-700 text-white text-sm">取消</button>
              <button onClick={() => handleDeletePolicy(deleteConfirm)} className="px-4 py-2 rounded-lg bg-red-600 text-white text-sm">确认删除</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function InputField({ label, name, required, type = "text", defaultValue, placeholder }: {
  label: string; name: string; required?: boolean; type?: string; defaultValue?: string; placeholder?: string;
}) {
  return (
    <div>
      <label className="block text-sm text-gray-300 mb-1">{label}</label>
      <input
        name={name} type={type} required={required} defaultValue={defaultValue} placeholder={placeholder}
        className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
      />
    </div>
  );
}
