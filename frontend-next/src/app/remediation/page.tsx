"use client";

import { useEffect, useState } from "react";
import { FileText, Loader2, ShieldCheck, ChevronLeft, ChevronRight } from "lucide-react";
import { useAuth } from "@/lib/auth";

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

  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const pageSize = 20;

  async function fetchLogs() {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (statusFilter) params.set("status", statusFilter);
      params.set("page", String(page));
      params.set("page_size", String(pageSize));
      const resp = await authFetch(`/api/remediation/logs?${params.toString()}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setLogs(data.items || []);
      setTotal(data.total || 0);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!token) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchLogs();
  }, [token, authFetch, page, statusFilter]);

  const totalPages = Math.ceil(total / pageSize);

  if (!token)
    return (
      <div className="p-8 text-center text-gray-500 mt-20">
        <ShieldCheck size={48} className="mx-auto mb-4 opacity-50" />
        <p>请先登录</p>
      </div>
    );

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <ShieldCheck size={28} className="text-blue-400" />
        <div>
          <h1 className="text-2xl font-bold text-white">修复记录</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            告警触发后 AI 自动分析、生成修复命令并通过 SSH 执行，结果记录在此
          </p>
        </div>
      </div>

      {/* 统计概览 */}
      <div className="grid grid-cols-4 gap-3 mb-6">
        {[
          { label: "全部", value: total, color: "text-gray-400" },
          { label: "成功", value: logs.filter(l => l.status === "success").length, color: "text-green-400" },
          { label: "失败", value: logs.filter(l => l.status === "failed").length, color: "text-red-400" },
          { label: "待处理", value: logs.filter(l => l.status === "running" || l.status === "pending").length, color: "text-yellow-400" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-gray-800/50 border border-gray-700 rounded-xl p-4 text-center">
            <div className={`text-2xl font-bold ${color}`}>{value}</div>
            <div className="text-xs text-gray-500 mt-1">{label}</div>
          </div>
        ))}
      </div>

      {/* 筛选 */}
      <div className="flex gap-2 mb-4">
        {["", "success", "failed", "running", "pending"].map(s => (
          <button key={s} onClick={() => { setStatusFilter(s); setPage(1); }}
            className={`px-3 py-1 rounded-lg text-sm transition ${
              statusFilter === s ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"
            }`}>
            {s || "全部"}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20 text-gray-500">
          <Loader2 size={24} className="animate-spin mr-2" /> 加载中...
        </div>
      ) : error ? (
        <div className="text-center py-20 text-red-500">{error}</div>
      ) : logs.length === 0 ? (
        <div className="text-center py-20 text-gray-500">
          <FileText size={48} className="mx-auto mb-4 opacity-50" />
          <p className="text-lg">暂无修复记录</p>
          <p className="text-sm mt-2 text-gray-600">
            当巡检发现资源超阈值或日志事件（OOM/错误等）时，AI 会自动触发修复并在此记录
          </p>
        </div>
      ) : (
        <>
          <div className="space-y-3">
            {logs.map((l) => (
              <div key={l.id}
                onClick={() => setExpandedId(expandedId === l.id ? null : l.id)}
                className="bg-gray-800/50 border border-gray-700 rounded-xl p-4 cursor-pointer hover:border-gray-500 transition-colors"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-3">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                      l.status === "success" ? "bg-green-600/20 text-green-400"
                      : l.status === "failed" ? "bg-red-600/20 text-red-400"
                      : l.status === "running" ? "bg-blue-600/20 text-blue-400"
                      : "bg-yellow-600/20 text-yellow-400"
                    }`}>
                      {l.status === "success" ? "成功" :
                       l.status === "failed" ? "失败" :
                       l.status === "running" ? "执行中" :
                       l.status === "pending" ? "待处理" : l.status}
                    </span>
                    <span className="text-white font-medium text-sm">{l.action}</span>
                    {l.triggered_by === "auto" && (
                      <span className="text-xs bg-purple-600/20 text-purple-400 px-2 py-0.5 rounded">自动触发</span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-xs text-gray-500">
                    {l.duration_ms != null && <span>{l.duration_ms}ms</span>}
                    <span>{new Date(l.created_at).toLocaleString()}</span>
                  </div>
                </div>

                {/* 摘要信息始终显示 */}
                {l.input_text && (
                  <div className="text-xs text-gray-500 line-clamp-1">
                    输入: {l.input_text.slice(0, 120)}
                  </div>
                )}

                {/* 展开详情 */}
                {expandedId === l.id && (
                  <div className="mt-3 pt-3 border-t border-gray-700 space-y-2">
                    {l.command && (
                      <div>
                        <div className="text-xs text-gray-500 mb-1">执行命令</div>
                        <pre className="text-xs text-gray-300 bg-gray-900/50 p-2 rounded overflow-x-auto">{l.command}</pre>
                      </div>
                    )}
                    {l.output && (
                      <div>
                        <div className="text-xs text-gray-500 mb-1">输出</div>
                        <pre className="text-xs text-green-400 bg-gray-900/50 p-2 rounded overflow-x-auto max-h-40 overflow-y-auto">{l.output}</pre>
                      </div>
                    )}
                    {l.error_output && (
                      <div>
                        <div className="text-xs text-gray-500 mb-1">错误输出</div>
                        <pre className="text-xs text-red-400 bg-gray-900/50 p-2 rounded overflow-x-auto max-h-40 overflow-y-auto">{l.error_output}</pre>
                      </div>
                    )}
                    {l.exit_code != null && (
                      <div className="text-xs text-gray-500">退出码: {l.exit_code}</div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>

          {total > pageSize && (
            <div className="flex items-center justify-between mt-6 text-sm text-gray-400">
              <span>共 {total} 条记录</span>
              <div className="flex items-center gap-3">
                <button onClick={() => setPage(p => Math.max(1, p-1))} disabled={page <= 1}
                  className="p-1 hover:text-white disabled:opacity-30"><ChevronLeft size={18} /></button>
                <span>{page} / {totalPages}</span>
                <button onClick={() => setPage(p => Math.min(totalPages, p+1))} disabled={page >= totalPages}
                  className="p-1 hover:text-white disabled:opacity-30"><ChevronRight size={18} /></button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
