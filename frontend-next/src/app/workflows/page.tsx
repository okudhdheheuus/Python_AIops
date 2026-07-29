"use client";

import { useEffect, useState } from "react";
import { Workflow, Plus, Play, Trash2, Edit3, History, Loader2, ChevronLeft, ChevronRight } from "lucide-react";
import { useAuth } from "@/lib/auth";
import WorkflowEditor from "@/components/WorkflowEditor";

interface WorkflowItem {
  id: string;
  name: string;
  description?: string;
  nodes: unknown[];
  edges: unknown[];
  is_template: boolean;
  created_at: string;
  updated_at?: string;
}

interface Execution {
  id: string;
  workflow_name: string;
  status: string;
  node_count: number;
  completed_count: number;
  failed_count: number;
  duration_ms: number;
  error_message?: string;
  started_at: string;
  finished_at?: string;
}

interface ServerOption {
  id: string;
  name: string;
  host: string;
}

export default function WorkflowsPage() {
  const { token, authFetch } = useAuth();
  const [viewMode, setViewMode] = useState<"list" | "editor">("list");
  const [editingWorkflow, setEditingWorkflow] = useState<WorkflowItem | null>(null);

  const [workflows, setWorkflows] = useState<WorkflowItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const pageSize = 20;

  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [running, setRunning] = useState<string | null>(null);
  const [runResult, setRunResult] = useState<Record<string, unknown> | null>(null);

  const [showExecutions, setShowExecutions] = useState<string | null>(null);
  const [executions, setExecutions] = useState<Execution[]>([]);
  const [execLoading, setExecLoading] = useState(false);

  const [serverOptions, setServerOptions] = useState<ServerOption[]>([]);

  async function fetchWorkflows() {
    setLoading(true);
    setError(null);
    try {
      const resp = await authFetch(`/api/workflows?page=${page}&page_size=${pageSize}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setWorkflows(data.items || []);
      setTotal(data.total || 0);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  async function fetchServers() {
    try {
      const resp = await authFetch("/api/servers");
      if (resp.ok) {
        const data = await resp.json();
        const all = Array.isArray(data) ? data : data.items || [];
        setServerOptions(
          all.filter((s: { enabled?: boolean }) => s.enabled !== false).map((s: { id: string; name: string; host: string }) => ({
            id: s.id,
            name: s.name,
            host: s.host,
          }))
        );
      }
    } catch {
      // servers are optional
    }
  }

  useEffect(() => {
    if (!token) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchWorkflows();
    fetchServers();
  }, [token, authFetch, page]);

  async function handleDelete(id: string) {
    try {
      const resp = await authFetch(`/api/workflows/${id}`, { method: "DELETE" });
      if (resp.ok) {
        setDeleteConfirm(null);
        fetchWorkflows();
      }
    } catch {
      // ignore
    }
  }

  async function handleRun(id: string) {
    setRunning(id);
    setRunResult(null);
    try {
      const resp = await authFetch(`/api/workflows/${id}/run`, { method: "POST" });
      const data = await resp.json();
      setRunResult(data);
    } catch {
      // ignore
    } finally {
      setRunning(null);
    }
  }

  async function fetchExecutions(id: string) {
    setShowExecutions(id);
    setExecLoading(true);
    try {
      const resp = await authFetch(`/api/workflows/${id}/executions?page_size=50`);
      if (resp.ok) {
        const data = await resp.json();
        setExecutions(data.items || []);
      }
    } catch {
      // ignore
    } finally {
      setExecLoading(false);
    }
  }

  function openCreate() {
    setEditingWorkflow(null);
    setViewMode("editor");
  }

  function openEdit(wf: WorkflowItem) {
    setEditingWorkflow(wf);
    setViewMode("editor");
  }

  const totalPages = Math.ceil(total / pageSize);

  if (!token)
    return (
      <div className="p-8 text-center text-gray-500 mt-20">
        <Workflow size={48} className="mx-auto mb-4 opacity-50" />
        <p>请先登录</p>
      </div>
    );

  if (viewMode === "editor") {
    return (
      <div className="h-[calc(100vh-0px)] -m-6">
        <WorkflowEditor
          workflow={editingWorkflow}
          servers={serverOptions}
          authFetch={authFetch}
          onSaved={() => {
            setViewMode("list");
            fetchWorkflows();
          }}
          onCancel={() => setViewMode("list")}
        />
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">工作流</h1>
        <button
          onClick={openCreate}
          className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg text-white flex items-center gap-2 text-sm"
        >
          <Plus size={16} /> 创建工作流
        </button>
      </div>

      {loading ? (
        <div className="text-gray-400 p-8">加载中...</div>
      ) : error ? (
        <div className="text-red-500 p-8">{error}</div>
      ) : workflows.length === 0 ? (
        <div className="text-center text-gray-500 mt-20">
          <Workflow size={48} className="mx-auto mb-4 opacity-50" />
          <p>暂无工作流</p>
        </div>
      ) : (
        <>
          <div className="grid gap-3">
            {workflows.map((wf) => (
              <div key={wf.id} className="bg-gray-800/50 border border-gray-700 rounded-xl p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <Workflow size={18} className="text-blue-400" />
                      <span className="text-white font-medium">{wf.name}</span>
                      {wf.is_template && (
                        <span className="text-xs bg-purple-600/20 text-purple-400 px-2 py-0.5 rounded">模板</span>
                      )}
                    </div>
                    {wf.description && <div className="text-sm text-gray-400 mt-1">{wf.description}</div>}
                    <div className="text-xs text-gray-500 mt-1">
                      {wf.nodes?.length || 0} 节点 · {new Date(wf.created_at).toLocaleDateString()}
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => handleRun(wf.id)}
                      disabled={running === wf.id}
                      className="p-2 text-gray-400 hover:text-green-400 transition"
                      title="运行"
                    >
                      {running === wf.id ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
                    </button>
                    <button
                      onClick={() => fetchExecutions(wf.id)}
                      className="p-2 text-gray-400 hover:text-blue-400 transition"
                      title="执行历史"
                    >
                      <History size={16} />
                    </button>
                    <button
                      onClick={() => openEdit(wf)}
                      className="p-2 text-gray-400 hover:text-yellow-400 transition"
                      title="编辑"
                    >
                      <Edit3 size={16} />
                    </button>
                    <button
                      onClick={() => setDeleteConfirm(wf.id)}
                      className="p-2 text-gray-400 hover:text-red-400 transition"
                      title="删除"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>

                {runResult && running === null && (
                  <div className="mt-3 p-3 bg-gray-900/50 rounded-lg text-sm">
                    <span
                      className={`font-medium ${
                        runResult.status === "success" ? "text-green-400" : "text-red-400"
                      }`}
                    >
                      状态: {runResult.status as string}
                    </span>
                    <span className="text-gray-500 ml-4">
                      节点: {runResult.completed_count as number}/{runResult.node_count as number}
                    </span>
                    <span className="text-gray-500 ml-4">耗时: {runResult.duration_ms as number}ms</span>
                  </div>
                )}

                {showExecutions === wf.id && (
                  <div className="mt-4 border-t border-gray-700 pt-4">
                    <h4 className="text-sm font-medium text-gray-300 mb-3">执行历史</h4>
                    {execLoading ? (
                      <div className="text-sm text-gray-500">加载中...</div>
                    ) : executions.length === 0 ? (
                      <div className="text-sm text-gray-500">暂无执行记录</div>
                    ) : (
                      <div className="space-y-2">
                        {executions.map((e) => (
                          <div key={e.id} className="bg-gray-900/50 rounded-lg p-3 flex items-center justify-between text-sm">
                            <div className="flex items-center gap-3">
                              <span
                                className={`text-xs px-2 py-0.5 rounded ${
                                  e.status === "success"
                                    ? "bg-green-600/20 text-green-400"
                                    : e.status === "failed"
                                    ? "bg-red-600/20 text-red-400"
                                    : "bg-yellow-600/20 text-yellow-400"
                                }`}
                              >
                                {e.status}
                              </span>
                              <span className="text-gray-400">
                                {e.completed_count}/{e.node_count} 节点
                              </span>
                            </div>
                            <div className="text-gray-500">
                              {e.duration_ms}ms · {new Date(e.started_at).toLocaleString()}
                            </div>
                          </div>
                        ))}
                      </div>
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
                <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1} className="p-1 hover:text-white disabled:opacity-30"><ChevronLeft size={18} /></button>
                <span>第 {page} / {totalPages} 页</span>
                <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages} className="p-1 hover:text-white disabled:opacity-30"><ChevronRight size={18} /></button>
              </div>
            </div>
          )}
        </>
      )}

      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-800 border border-gray-700 rounded-xl p-6 max-w-sm">
            <p className="text-white mb-4">确认删除此工作流？</p>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setDeleteConfirm(null)} className="px-4 py-2 rounded-lg bg-gray-700 text-white text-sm">取消</button>
              <button onClick={() => handleDelete(deleteConfirm)} className="px-4 py-2 rounded-lg bg-red-600 text-white text-sm">确认删除</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
