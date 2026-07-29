"use client";

import { useEffect, useState } from "react";
import { Activity, CheckCircle, AlertTriangle, XCircle, ChevronLeft, ChevronRight } from "lucide-react";
import { useAuth } from "@/lib/auth";

interface PatrolSummary {
  total: number;
  success: number;
  warning: number;
  error: number;
  avg_cpu: number;
  avg_memory: number;
  avg_disk: number;
}

interface PatrolRecord {
  id: string;
  server_name: string;
  status: "success" | "warning" | "error";
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  checked_at: string;
}

export default function PatrolPage() {
  const [summary, setSummary] = useState<PatrolSummary | null>(null);
  const [records, setRecords] = useState<PatrolRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [days, setDays] = useState(7);
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const pageSize = 20;

  const { token, authFetch } = useAuth();

  useEffect(() => {
    if (!token) return;
    async function fetchData() {
      try {
        setLoading(true);
        setError(null);
        const params = new URLSearchParams();
        params.set("days", String(days));
        if (statusFilter) params.set("status", statusFilter);
        params.set("page", String(page));
        params.set("page_size", String(pageSize));

        const [summaryRes, recordsRes] = await Promise.all([
          authFetch(`/api/patrol/summary?days=${days}`),
          authFetch(`/api/patrol/records?${params.toString()}`),
        ]);
        if (!summaryRes.ok) throw new Error(`巡检摘要 API 返回 ${summaryRes.status}`);
        if (!recordsRes.ok) throw new Error(`巡检记录 API 返回 ${recordsRes.status}`);
        setSummary(await summaryRes.json());
        const data = await recordsRes.json();
        setRecords(data.items || []);
        setTotal(data.total || 0);
      } catch (error: unknown) {
        setError(error instanceof Error ? error.message : String(error));
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [token, authFetch, days, statusFilter, page]);

  const statusIcon = (s: string) => {
    if (s === "success") return <CheckCircle size={16} className="text-green-400" />;
    if (s === "warning") return <AlertTriangle size={16} className="text-yellow-400" />;
    return <XCircle size={16} className="text-red-400" />;
  };

  const totalPages = Math.ceil(total / pageSize);

  if (!token) return <div className="p-8 text-center text-gray-500 mt-20"><Activity size={48} className="mx-auto mb-4 opacity-50" /><p>请先登录</p></div>;
  if (loading) return <div className="p-8 text-gray-400">加载中...</div>;
  if (error) return <div className="p-8 text-red-500">{error}</div>;

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">巡检记录</h1>
        <div className="flex items-center gap-2">
          <select value={days} onChange={(e) => { setDays(Number(e.target.value)); setPage(1); }}
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-white text-sm focus:border-blue-500 focus:outline-none">
            <option value={1}>最近 1 天</option>
            <option value={7}>最近 7 天</option>
            <option value={30}>最近 30 天</option>
            <option value={90}>最近 90 天</option>
          </select>
          {["", "success", "warning", "error"].map((s) => (
            <button key={s} onClick={() => { setStatusFilter(s); setPage(1); }}
              className={`px-3 py-1.5 rounded-lg text-sm ${statusFilter === s ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"}`}>
              {s === "" ? "全部" : s === "success" ? "正常" : s === "warning" ? "警告" : "失败"}
            </button>
          ))}
        </div>
      </div>

      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <StatCard label="巡检总次数" value={summary.total} />
          <StatCard label="正常" value={summary.success} color="text-green-400" />
          <StatCard label="警告" value={summary.warning} color="text-yellow-400" />
          <StatCard label="失败" value={summary.error} color="text-red-400" />
        </div>
      )}

      {summary && (
        <div className="bg-gray-800/50 rounded-xl border border-gray-700 p-4 mb-8 text-sm text-gray-400">
          近 {days} 日平均资源使用: CPU {summary.avg_cpu}% / 内存 {summary.avg_memory}% / 磁盘 {summary.avg_disk}%
        </div>
      )}

      {records.length === 0 ? (
        <div className="text-center text-gray-500 mt-10">
          <Activity size={48} className="mx-auto mb-4 opacity-50" />
          <p>暂无巡检记录</p>
        </div>
      ) : (
        <>
          <div className="grid gap-3">
            {records.map((r) => (
              <div key={r.id} className="bg-gray-800/50 border border-gray-700 rounded-xl p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {statusIcon(r.status)}
                  <div>
                    <div className="text-white">{r.server_name}</div>
                    <div className="text-xs text-gray-500">
                      CPU {r.cpu_usage}% / 内存 {r.memory_usage}% / 磁盘 {r.disk_usage}%
                    </div>
                  </div>
                </div>
                <div className="text-xs text-gray-500">
                  {new Date(r.checked_at).toLocaleString()}
                </div>
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

function StatCard({ label, value, color = "text-white" }: {
  label: string; value: number; color?: string;
}) {
  return (
    <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-4 text-center">
      <div className="text-xs text-gray-400 mb-1">{label}</div>
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
    </div>
  );
}
