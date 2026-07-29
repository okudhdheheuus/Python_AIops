"use client";

import { useEffect, useState, useRef } from "react";
import { Server, Plus, X, Trash2, Edit3, Wifi, Download, Upload, Loader2 } from "lucide-react";
import { useAuth } from "@/lib/auth";

interface ServerItem {
  id: string;
  name: string;
  host: string;
  port: number;
  username: string;
  password?: string;
  tags?: string;
  description?: string;
  enabled: boolean;
  created_at: string;
}

export default function ServersPage() {
  const [servers, setServers] = useState<ServerItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [editingServer, setEditingServer] = useState<ServerItem | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const [testingId, setTestingId] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ id: string; ok: boolean; msg: string } | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const { token, authFetch } = useAuth();

  async function fetchServers() {
    setLoading(true);
    setError(null);
    try {
      const resp = await authFetch("/api/servers");
      if (!resp.ok) throw new Error(`API 返回 ${resp.status}`);
      setServers(await resp.json());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!token) return;
    fetchServers();
  }, [token, authFetch]);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setFormError(null);
    const form = new FormData(e.currentTarget);
    const body: Record<string, unknown> = {
      name: form.get("name") as string,
      host: form.get("host") as string,
      port: Number(form.get("port")) || 22,
      username: form.get("username") as string,
      password: (form.get("password") as string) || undefined,
      description: (form.get("description") as string) || undefined,
      tags: (form.get("tags") as string) || undefined,
    };

    try {
      const isEdit = !!editingServer;
      const url = isEdit ? `/api/servers/${editingServer.id}` : "/api/servers";
      const method = isEdit ? "PUT" : "POST";
      const resp = await authFetch(url, { method, body: JSON.stringify(body) });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error((err as { detail?: string }).detail || `HTTP ${resp.status}`);
      }
      setShowForm(false);
      setEditingServer(null);
      fetchServers();
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  function openCreate() {
    setEditingServer(null);
    setFormError(null);
    setShowForm(true);
  }

  function openEdit(s: ServerItem) {
    setEditingServer(s);
    setFormError(null);
    setShowForm(true);
  }

  async function handleDelete(id: string) {
    setDeleting(true);
    try {
      const resp = await authFetch(`/api/servers/${id}`, { method: "DELETE" });
      if (resp.ok) {
        setDeleteConfirm(null);
        fetchServers();
      }
    } catch {
      // ignore
    } finally {
      setDeleting(false);
    }
  }

  async function handleTestConnection(id: string) {
    setTestingId(id);
    setTestResult(null);
    try {
      const resp = await authFetch(`/api/servers/${id}/test-connection`, { method: "POST" });
      const data = await resp.json().catch(() => ({}));
      setTestResult({
        id,
        ok: resp.ok,
        msg: (data as { detail?: string }).detail || (data as { message?: string }).message || (resp.ok ? "连接成功" : "连接失败"),
      });
    } catch {
      setTestResult({ id, ok: false, msg: "请求失败" });
    } finally {
      setTestingId(null);
    }
  }

  async function handleExportCsv() {
    try {
      const resp = await authFetch("/api/servers/export-csv");
      if (!resp.ok) return;
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "servers.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // ignore
    }
  }

  async function handleImportCsv(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const formData = new FormData();
      formData.append("file", file);
      const headers: Record<string, string> = {};
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const resp = await fetch("/api/servers/import-csv", {
        method: "POST",
        headers,
        body: formData,
      });
      if (resp.ok) {
        fetchServers();
        const data = await resp.json();
        alert(`导入完成: ${(data as { imported?: number }).imported || 0} 条`);
      }
    } catch {
      // ignore
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  if (!token) return <div className="p-8 text-center text-gray-500 mt-20"><Server size={48} className="mx-auto mb-4 opacity-50" /><p>请先登录</p></div>;
  if (loading) return <div className="p-8 text-gray-400">加载中...</div>;
  if (error) return <div className="p-8 text-red-500">{error}</div>;

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">服务器管理</h1>
        <div className="flex items-center gap-2">
          <button onClick={handleExportCsv} className="bg-gray-700 hover:bg-gray-600 px-3 py-2 rounded-lg text-white flex items-center gap-2 text-sm" title="导出 CSV">
            <Download size={16} /> 导出
          </button>
          <button onClick={() => fileInputRef.current?.click()} className="bg-gray-700 hover:bg-gray-600 px-3 py-2 rounded-lg text-white flex items-center gap-2 text-sm" title="导入 CSV">
            <Upload size={16} /> 导入
          </button>
          <input ref={fileInputRef} type="file" accept=".csv" onChange={handleImportCsv} className="hidden" />
          <button onClick={openCreate} className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg text-white flex items-center gap-2 text-sm">
            <Plus size={16} /> 添加服务器
          </button>
        </div>
      </div>

      {servers.length === 0 ? (
        <div className="text-center text-gray-500 mt-20">
          <Server size={48} className="mx-auto mb-4 opacity-50" />
          <p>暂无管理服务器</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {servers.map((s) => (
            <div key={s.id} className="bg-gray-800/50 border border-gray-700 rounded-xl p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <Server size={20} className={s.enabled ? "text-green-400" : "text-gray-500"} />
                  <div>
                    <div className="text-white font-medium">{s.name}</div>
                    <div className="text-sm text-gray-400">{s.host}:{s.port} · {s.username}</div>
                    {s.description && <div className="text-xs text-gray-500 mt-0.5">{s.description}</div>}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {s.tags && <span className="text-xs bg-gray-700 px-2 py-1 rounded">{s.tags}</span>}
                  <span className={`text-xs px-2 py-1 rounded ${s.enabled ? "bg-green-600/20 text-green-400" : "bg-gray-600/20 text-gray-400"}`}>
                    {s.enabled ? "启用" : "禁用"}
                  </span>
                  <button onClick={() => handleTestConnection(s.id)} disabled={testingId === s.id}
                    className="p-1.5 text-gray-400 hover:text-green-400 transition" title="测试连接">
                    {testingId === s.id ? <Loader2 size={16} className="animate-spin" /> : <Wifi size={16} />}
                  </button>
                  <button onClick={() => openEdit(s)} className="p-1.5 text-gray-400 hover:text-yellow-400 transition" title="编辑">
                    <Edit3 size={16} />
                  </button>
                  <button onClick={() => setDeleteConfirm(s.id)} className="p-1.5 text-gray-400 hover:text-red-400 transition" title="删除">
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
              {testResult?.id === s.id && (
                <div className={`mt-2 text-sm px-3 py-1.5 rounded-lg ${testResult.ok ? "bg-green-600/10 text-green-400" : "bg-red-600/10 text-red-400"}`}>
                  {testResult.msg}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {showForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-800 border border-gray-700 rounded-xl w-full max-w-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-white">{editingServer ? "编辑服务器" : "添加服务器"}</h2>
              <button onClick={() => { setShowForm(false); setEditingServer(null); }} className="text-gray-400 hover:text-white"><X size={20} /></button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-3">
              <InputField label="名称" name="name" required defaultValue={editingServer?.name} />
              <InputField label="主机地址" name="host" required defaultValue={editingServer?.host} />
              <InputField label="SSH 端口" name="port" type="number" defaultValue={String(editingServer?.port || 22)} />
              <InputField label="用户名" name="username" defaultValue={editingServer?.username || "root"} />
              <InputField label="密码" name="password" type="password" />
              <InputField label="标签" name="tags" placeholder="逗号分隔" defaultValue={editingServer?.tags} />
              <InputField label="描述" name="description" defaultValue={editingServer?.description} />
              {formError && <p className="text-red-400 text-sm">{formError}</p>}
              <button
                type="submit"
                disabled={submitting}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white py-2 rounded-lg text-sm font-medium flex items-center justify-center gap-2"
              >
                {submitting && <Loader2 size={16} className="animate-spin" />}
                {submitting ? "提交中..." : editingServer ? "保存修改" : "确认添加"}
              </button>
            </form>
          </div>
        </div>
      )}

      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-800 border border-gray-700 rounded-xl p-6 max-w-sm">
            <p className="text-white mb-4">确认删除服务器 &ldquo;{servers.find((s) => s.id === deleteConfirm)?.name}&rdquo;？</p>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setDeleteConfirm(null)} className="px-4 py-2 rounded-lg bg-gray-700 text-white text-sm">取消</button>
              <button onClick={() => handleDelete(deleteConfirm)} disabled={deleting} className="px-4 py-2 rounded-lg bg-red-600 text-white text-sm disabled:opacity-50">
                {deleting ? "删除中..." : "确认删除"}
              </button>
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
