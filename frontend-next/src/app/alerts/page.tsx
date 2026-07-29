"use client";

import { useEffect, useState } from "react";
import { Bell, AlertTriangle, Info, CheckCircle, BellOff, BellRing, Plus, X, Trash2, ChevronLeft, ChevronRight, Wand2, Loader2 } from "lucide-react";
import { useAuth } from "@/lib/auth";

interface AlertItem {
  id: string;
  alert_name: string;
  severity: "critical" | "warning" | "info";
  status: "firing" | "acknowledged" | "resolved";
  instance: string;
  summary: string;
  created_at: string;
}

interface SilenceRule {
  id: string;
  name: string;
  match_labels: Record<string, string>;
  duration_minutes: number;
  comment?: string;
  enabled: boolean;
  created_by: string;
}

export default function AlertsPage() {
  const { token, authFetch } = useAuth();
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const pageSize = 20;

  const [showSilence, setShowSilence] = useState(false);
  const [silences, setSilences] = useState<SilenceRule[]>([]);
  const [silenceLoading, setSilenceLoading] = useState(false);
  const [showSilenceForm, setShowSilenceForm] = useState(false);
  const [silenceSubmitting, setSilenceSubmitting] = useState(false);
  const [silenceError, setSilenceError] = useState<string | null>(null);

  const [remediatingId, setRemediatingId] = useState<string | null>(null);
  const [remediationResult, setRemediationResult] = useState<{ id: string; status: string; output: string } | null>(null);

  useEffect(() => {
    if (!token) return;
    fetchAlerts();
  }, [filter, page, token, authFetch]);

  async function fetchAlerts() {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (filter) params.set("status", filter);
      params.set("page", String(page));
      params.set("page_size", String(pageSize));
      const resp = await authFetch(`/api/alerts?${params.toString()}`);
      if (!resp.ok) throw new Error(`API 返回 ${resp.status}`);
      const data = await resp.json();
      setAlerts(data.items || []);
      setTotal(data.total || 0);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  async function handleAcknowledge(id: string) {
    try {
      const resp = await authFetch(`/api/alerts/${id}`, {
        method: "PUT",
        body: JSON.stringify({ status: "acknowledged" }),
      });
      if (resp.ok) fetchAlerts();
    } catch { /* ignore */ }
  }

  async function handleResolve(id: string) {
    try {
      const resp = await authFetch(`/api/alerts/${id}`, {
        method: "PUT",
        body: JSON.stringify({ status: "resolved" }),
      });
      if (resp.ok) fetchAlerts();
    } catch { /* ignore */ }
  }

  async function handleRemediate(id: string) {
    setRemediatingId(id);
    setRemediationResult(null);
    try {
      const resp = await authFetch(`/api/alerts/${id}/remediate`, { method: "POST" });
      const data = await resp.json();
      setRemediationResult({
        id,
        status: data.status === "success" ? "success" : "failed",
        output: data.output || JSON.stringify(data),
      });
      if (resp.ok) fetchAlerts();
    } catch (e: unknown) {
      setRemediationResult({
        id,
        status: "failed",
        output: e instanceof Error ? e.message : String(e),
      });
    } finally {
      setRemediatingId(null);
    }
  }

  async function fetchSilences() {
    setSilenceLoading(true);
    try {
      const resp = await authFetch("/api/alerts/silence");
      if (resp.ok) {
        const data = await resp.json();
        setSilences(data.items || []);
      }
    } catch { /* ignore */ }
    finally { setSilenceLoading(false); }
  }

  async function handleCreateSilence(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSilenceSubmitting(true);
    setSilenceError(null);
    const form = new FormData(e.currentTarget);
    const matchLabelsStr = form.get("match_labels") as string;
    let matchLabels = {};
    try { matchLabels = matchLabelsStr ? JSON.parse(matchLabelsStr) : {}; } catch { matchLabels = {}; }
    const body = {
      name: form.get("name") as string,
      match_labels: matchLabels,
      duration_minute: Number(form.get("duration_minutes")) || 60,
      comment: (form.get("comment") as string) || undefined,
    };
    try {
      const resp = await authFetch("/api/alerts/silence", {
        method: "POST",
        body: JSON.stringify(body),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error((err as { detail?: string }).detail || `HTTP ${resp.status}`);
      }
      setShowSilenceForm(false);
      fetchSilences();
    } catch (e: unknown) {
      setSilenceError(e instanceof Error ? e.message : String(e));
    } finally {
      setSilenceSubmitting(false);
    }
  }

  async function handleDeleteSilence(id: string) {
    try {
      const resp = await authFetch(`/api/alerts/silence/${id}`, { method: "DELETE" });
      if (resp.ok) fetchSilences();
    } catch { /* ignore */ }
  }

  function openSilencePanel() {
    setShowSilence(!showSilence);
    if (!showSilence) fetchSilences();
  }

  const severityIcon = (s: string) => {
    if (s === "critical") return <AlertTriangle size={16} className="text-red-400" />;
    if (s === "warning") return <AlertTriangle size={16} className="text-yellow-400" />;
    return <Info size={16} className="text-blue-400" />;
  };

  const statusColor = (s: string) => {
    if (s === "firing") return "bg-red-600/20 text-red-400";
    if (s === "acknowledged") return "bg-yellow-600/20 text-yellow-400";
    return "bg-green-600/20 text-green-400";
  };

  const statusLabel = (s: string) => {
    if (s === "firing") return "告警中";
    if (s === "acknowledged") return "已确认";
    return "已解决";
  };

  const totalPages = Math.ceil(total / pageSize);

  if (!token) return <div className="p-8 text-center text-gray-500 mt-20"><Bell size={48} className="mx-auto mb-4 opacity-50" /><p>请先登录</p></div>;
  if (loading) return <div className="p-8 text-gray-400">加载中...</div>;
  if (error) return <div className="p-8 text-red-500">{error}</div>;

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">告警中心</h1>
        <div className="flex gap-2">
          <button onClick={openSilencePanel}
            className={`px-3 py-1 rounded-lg text-sm flex items-center gap-1 ${showSilence ? "bg-purple-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"}`}>
            <BellRing size={16} /> 静默规则
          </button>
          {["", "firing", "acknowledged", "resolved"].map((s) => (
            <button key={s} onClick={() => { setFilter(s); setPage(1); }}
              className={`px-3 py-1 rounded-lg text-sm ${filter === s ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"}`}>
              {s === "" ? "全部" : s === "firing" ? "告警中" : s === "acknowledged" ? "已确认" : "已解决"}
            </button>
          ))}
        </div>
      </div>

      {showSilence && (
        <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-4 mb-6">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-white font-medium">静默规则</h3>
            <button onClick={() => setShowSilenceForm(true)} className="text-blue-400 hover:text-blue-300 text-sm flex items-center gap-1">
              <Plus size={14} /> 添加规则
            </button>
          </div>
          {silenceLoading ? <div className="text-sm text-gray-500">加载中...</div>
          : silences.length === 0 ? <div className="text-sm text-gray-500">暂无静默规则</div>
          : (
            <div className="space-y-2">
              {silences.map((r) => (
                <div key={r.id} className="flex items-center justify-between bg-gray-900/50 rounded-lg p-3 text-sm">
                  <div>
                    <span className="text-white">{r.name}</span>
                    <span className="text-gray-500 ml-2">时长: {r.duration_minutes}分钟</span>
                    {r.comment && <span className="text-gray-500 ml-2">- {r.comment}</span>}
                    <span className="text-gray-600 ml-2">创建者: {r.created_by}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs px-2 py-0.5 rounded ${r.enabled ? "bg-green-600/20 text-green-400" : "bg-gray-600/20 text-gray-400"}`}>
                      {r.enabled ? "启用" : "禁用"}
                    </span>
                    <button onClick={() => handleDeleteSilence(r.id)} className="text-gray-400 hover:text-red-400"><Trash2 size={14} /></button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {showSilenceForm && (
            <div className="mt-4 border-t border-gray-700 pt-4">
              <form onSubmit={handleCreateSilence} className="space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-medium text-gray-300">新建静默规则</h4>
                  <button type="button" onClick={() => setShowSilenceForm(false)} className="text-gray-400 hover:text-white"><X size={16} /></button>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-gray-400 mb-1">名称</label>
                    <input name="name" required className="w-full bg-gray-900 border border-gray-600 rounded px-3 py-1.5 text-white text-sm focus:border-blue-500 focus:outline-none" />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-400 mb-1">静默时长 (分钟)</label>
                    <input name="duration_minutes" type="number" defaultValue="60" className="w-full bg-gray-900 border border-gray-600 rounded px-3 py-1.5 text-white text-sm focus:border-blue-500 focus:outline-none" />
                  </div>
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">匹配标签 (JSON)</label>
                  <input name="match_labels" placeholder='{"severity": "critical"}' className="w-full bg-gray-900 border border-gray-600 rounded px-3 py-1.5 text-white text-sm focus:border-blue-500 focus:outline-none font-mono" />
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1">备注</label>
                  <input name="comment" className="w-full bg-gray-900 border border-gray-600 rounded px-3 py-1.5 text-white text-sm focus:border-blue-500 focus:outline-none" />
                </div>
                {silenceError && <p className="text-red-400 text-xs">{silenceError}</p>}
                <button type="submit" disabled={silenceSubmitting}
                  className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 px-4 py-1.5 rounded text-white text-sm">
                  {silenceSubmitting ? "提交中..." : "创建规则"}
                </button>
              </form>
            </div>
          )}
        </div>
      )}

      {remediationResult && (
        <div className={`mb-4 p-4 rounded-xl border ${remediationResult.status === "success" ? "bg-green-600/10 border-green-600/30" : "bg-red-600/10 border-red-600/30"}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {remediationResult.status === "success"
                ? <CheckCircle size={18} className="text-green-400" />
                : <AlertTriangle size={18} className="text-red-400" />}
              <span className={`font-medium ${remediationResult.status === "success" ? "text-green-400" : "text-red-400"}`}>
                {remediationResult.status === "success" ? "AI修复执行完成" : "AI修复执行失败"}
              </span>
            </div>
            <button onClick={() => setRemediationResult(null)} className="text-gray-400 hover:text-white"><X size={16} /></button>
          </div>
          <div className="mt-2 text-sm text-gray-300 whitespace-pre-wrap max-h-40 overflow-y-auto">{remediationResult.output}</div>
        </div>
      )}

      {alerts.length === 0 ? (
        <div className="text-center text-gray-500 mt-20">
          <Bell size={48} className="mx-auto mb-4 opacity-50" />
          <p>暂无告警记录</p>
        </div>
      ) : (
        <>
          <div className="grid gap-3">
            {alerts.map((a) => (
              <div key={a.id} className="bg-gray-800/50 border border-gray-700 rounded-xl p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    {severityIcon(a.severity)}
                    <span className="text-white font-medium">{a.alert_name}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs px-2 py-1 rounded ${statusColor(a.status)}`}>{statusLabel(a.status)}</span>
                    {a.status === "firing" && (
                      <>
                        <button onClick={() => handleRemediate(a.id)} disabled={remediatingId === a.id}
                          className="p-1 text-gray-400 hover:text-purple-400 transition disabled:opacity-50" title="AI修复">
                          {remediatingId === a.id ? <Loader2 size={16} className="animate-spin" /> : <Wand2 size={16} />}
                        </button>
                        <button onClick={() => handleAcknowledge(a.id)} className="p-1 text-gray-400 hover:text-yellow-400 transition" title="确认告警">
                          <CheckCircle size={16} />
                        </button>
                      </>
                    )}
                    {a.status !== "resolved" && (
                      <button onClick={() => handleResolve(a.id)} className="p-1 text-gray-400 hover:text-green-400 transition" title="解决告警">
                        <BellOff size={16} />
                      </button>
                    )}
                  </div>
                </div>
                <div className="text-sm text-gray-400">{a.summary}</div>
                <div className="text-xs text-gray-500 mt-2">{a.instance} · {new Date(a.created_at).toLocaleString()}</div>
              </div>
            ))}
          </div>

          {total > pageSize && (
            <div className="flex items-center justify-between mt-6 text-sm text-gray-400">
              <span>共 {total} 条</span>
              <div className="flex items-center gap-3">
                <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1} className="p-1 hover:text-white disabled:opacity-30"><ChevronLeft size={18} /></button>
                <span>第 {page} / {totalPages} 页</span>
                <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page >= totalPages} className="p-1 hover:text-white disabled:opacity-30"><ChevronRight size={18} /></button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
