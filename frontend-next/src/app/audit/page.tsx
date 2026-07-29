"use client";

import { useEffect, useState } from "react";
import { FileText, Search, ChevronLeft, ChevronRight } from "lucide-react";
import { useAuth } from "@/lib/auth";

interface AuditLog {
  id: string;
  username: string;
  action: string;
  resource_type?: string;
  resource_id?: string;
  detail?: string;
  ip_address?: string;
  created_at: string;
}

export default function AuditPage() {
  const { token, authFetch } = useAuth();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [filterUsername, setFilterUsername] = useState("");
  const [filterAction, setFilterAction] = useState("");
  const [filterResourceType, setFilterResourceType] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const pageSize = 50;

  useEffect(() => {
    if (!token) return;
    fetchLogs();
  }, [token, authFetch, page]);

  async function fetchLogs() {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (filterUsername) params.set("username", filterUsername);
      if (filterAction) params.set("action", filterAction);
      if (filterResourceType) params.set("resource_type", filterResourceType);
      params.set("page", String(page));
      params.set("page_size", String(pageSize));
      const resp = await authFetch(`/api/audit/logs?${params.toString()}`);
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

  function handleSearch() {
    setPage(1);
    fetchLogs();
  }

  function actionColor(action: string) {
    if (action.includes("create") || action.includes("添加")) return "text-green-400";
    if (action.includes("update") || action.includes("修改")) return "text-yellow-400";
    if (action.includes("delete") || action.includes("删除")) return "text-red-400";
    return "text-gray-400";
  }

  const totalPages = Math.ceil(total / pageSize);

  if (!token)
    return (
      <div className="p-8 text-center text-gray-500 mt-20">
        <FileText size={48} className="mx-auto mb-4 opacity-50" />
        <p>请先登录</p>
      </div>
    );

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <h1 className="text-2xl font-bold text-white mb-6">审计日志</h1>

      <div className="flex flex-wrap gap-3 mb-6">
        <input
          value={filterUsername}
          onChange={(e) => setFilterUsername(e.target.value)}
          placeholder="用户名..."
          className="bg-gray-800/50 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none w-40"
        />
        <input
          value={filterAction}
          onChange={(e) => setFilterAction(e.target.value)}
          placeholder="操作..."
          className="bg-gray-800/50 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none w-40"
        />
        <input
          value={filterResourceType}
          onChange={(e) => setFilterResourceType(e.target.value)}
          placeholder="资源类型..."
          className="bg-gray-800/50 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none w-40"
        />
        <button
          onClick={handleSearch}
          className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg text-white flex items-center gap-2 text-sm"
        >
          <Search size={16} /> 查询
        </button>
      </div>

      {loading ? (
        <div className="text-gray-400 p-8">加载中...</div>
      ) : error ? (
        <div className="text-red-500 p-8">{error}</div>
      ) : logs.length === 0 ? (
        <div className="text-center text-gray-500 mt-20">
          <FileText size={48} className="mx-auto mb-4 opacity-50" />
          <p>暂无审计日志</p>
        </div>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-700 text-gray-400">
                  <th className="text-left py-3 px-4">时间</th>
                  <th className="text-left py-3 px-4">用户</th>
                  <th className="text-left py-3 px-4">操作</th>
                  <th className="text-left py-3 px-4">资源类型</th>
                  <th className="text-left py-3 px-4">详情</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id} className="border-b border-gray-700/50 hover:bg-gray-800/30">
                    <td className="py-3 px-4 text-gray-400 whitespace-nowrap">
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                    <td className="py-3 px-4 text-white">{log.username}</td>
                    <td className={`py-3 px-4 ${actionColor(log.action)}`}>{log.action}</td>
                    <td className="py-3 px-4 text-gray-400">{log.resource_type || "-"}</td>
                    <td className="py-3 px-4 text-gray-500 max-w-xs truncate">{log.detail || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between mt-6 text-sm text-gray-400">
            <span>共 {total} 条</span>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="p-1 hover:text-white disabled:opacity-30"
              >
                <ChevronLeft size={18} />
              </button>
              <span>
                第 {page} / {totalPages} 页
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="p-1 hover:text-white disabled:opacity-30"
              >
                <ChevronRight size={18} />
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
