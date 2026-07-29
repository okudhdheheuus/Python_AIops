"use client";

import { useEffect, useState, useCallback } from "react";
import { BellRing, Plus, X, Trash2, Edit3, Loader2, Play } from "lucide-react";
import { useAuth } from "@/lib/auth";

interface Channel {
  id: string;
  name: string;
  channel_type: string;
  channel_type_label?: string;
  webhook_url: string;
  has_sign_secret?: boolean;
  enabled: boolean;
  created_at: string;
}

interface ChannelDetail {
  id: string;
  name: string;
  channel_type: string;
  webhook_url: string;
  has_sign_secret: boolean;
  enabled: boolean;
}

const CHANNEL_TYPE_OPTIONS = [
  { value: "wecom", label: "企业微信" },
  { value: "dingtalk", label: "钉钉" },
  { value: "feishu", label: "飞书" },
  { value: "email", label: "邮件" },
];

const CHANNEL_TYPE_LABEL: Record<string, string> = {
  wecom: "企业微信",
  dingtalk: "钉钉",
  feishu: "飞书",
  email: "邮件",
};

export default function NotificationsPage() {
  const { token, user, authFetch } = useAuth();
  const [channels, setChannels] = useState<Channel[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editData, setEditData] = useState<ChannelDetail | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);

  const isAdmin = user?.role === "admin";

  const fetchChannels = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await authFetch("/api/notifications/channels");
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setChannels(data.items || []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [authFetch]);

  useEffect(() => {
    if (!token) return;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchChannels();
  }, [token, fetchChannels]);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!isAdmin) return;
    setSubmitting(true);
    setFormError(null);
    const form = new FormData(e.currentTarget);
    const body: Record<string, unknown> = {
      name: form.get("name") as string,
      channel_type: form.get("channel_type") as string,
      webhook_url: form.get("webhook_url") as string,
      enabled: form.get("enabled") === "true",
    };

    const signSecret = form.get("sign_secret") as string;
    if (signSecret) {
      body.sign_secret = signSecret;
    }

    try {
      const url = editingId
        ? `/api/notifications/channels/${editingId}`
        : "/api/notifications/channels";
      const method = editingId ? "PUT" : "POST";
      const resp = await authFetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(
          (err as { detail?: string }).detail || `HTTP ${resp.status}`
        );
      }
      setShowModal(false);
      setEditingId(null);
      setEditData(null);
      fetchChannels();
    } catch (e: unknown) {
      setFormError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id: string) {
    setDeleting(true);
    try {
      const resp = await authFetch(`/api/notifications/channels/${id}`, {
        method: "DELETE",
      });
      if (resp.ok) {
        setDeleteConfirm(null);
        fetchChannels();
      }
    } catch {
      // ignore
    } finally {
      setDeleting(false);
    }
  }

  async function handleTest(id: string) {
    setTestingId(id);
    try {
      const resp = await authFetch(`/api/notifications/channels/${id}/test`, {
        method: "POST",
      });
      const data = await resp.json();
      if (resp.ok) {
        alert(`测试成功: ${data.message || "消息已发送"}`);
      } else {
        alert(`测试失败: ${data.detail || `HTTP ${resp.status}`}`);
      }
    } catch (e: unknown) {
      alert(`测试失败: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setTestingId(null);
    }
  }

  async function openEdit(ch: Channel) {
    if (!isAdmin) return;
    setFormError(null);
    setSubmitting(false);
    // 先用列表数据兜底，再尝试获取完整 webhook_url
    setEditData({
      id: ch.id,
      name: ch.name,
      channel_type: ch.channel_type,
      webhook_url: ch.webhook_url,
      has_sign_secret: ch.has_sign_secret || false,
      enabled: ch.enabled,
    });
    setEditingId(ch.id);
    setShowModal(true);

    try {
      const resp = await authFetch(`/api/notifications/channels/${ch.id}`);
      if (resp.ok) {
        const detail: ChannelDetail = await resp.json();
        setEditData(detail);
      }
    } catch {
      // 保持列表兜底数据
    }
  }

  function openCreate() {
    if (!isAdmin) return;
    setEditingId(null);
    setEditData(null);
    setFormError(null);
    setSubmitting(false);
    setShowModal(true);
  }

  if (!token)
    return (
      <div className="p-8 text-center text-gray-500 mt-20">
        <BellRing size={48} className="mx-auto mb-4 opacity-50" />
        <p>请先登录</p>
      </div>
    );

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">通知管理</h1>
        {isAdmin && (
          <button
            onClick={openCreate}
            className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg text-white flex items-center gap-2 text-sm"
          >
            <Plus size={16} /> 添加渠道
          </button>
        )}
      </div>

      {!isAdmin && (
        <div className="text-sm text-yellow-400 mb-4 bg-yellow-600/10 border border-yellow-600/30 rounded-lg p-3">
          仅管理员可创建/修改/删除通知渠道
        </div>
      )}

      {loading ? (
        <div className="text-gray-400 p-8">加载中...</div>
      ) : error ? (
        <div className="text-red-500 p-8">{error}</div>
      ) : channels.length === 0 ? (
        <div className="text-center text-gray-500 mt-20">
          <BellRing size={48} className="mx-auto mb-4 opacity-50" />
          <p>暂无通知渠道</p>
        </div>
      ) : (
        <div className="grid gap-3">
          {channels.map((ch) => (
            <div
              key={ch.id}
              className="bg-gray-800/50 border border-gray-700 rounded-xl p-4 flex items-center justify-between"
            >
              <div className="flex items-center gap-3">
                <BellRing
                  size={20}
                  className={ch.enabled ? "text-green-400" : "text-gray-500"}
                />
                <div>
                  <div className="text-white font-medium">{ch.name}</div>
                  <div className="text-sm text-gray-400">
                    <span className="text-xs bg-blue-600/20 text-blue-400 px-2 py-0.5 rounded mr-2">
                      {CHANNEL_TYPE_LABEL[ch.channel_type] || ch.channel_type}
                    </span>
                    {ch.webhook_url}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span
                  className={`text-xs px-2 py-1 rounded ${
                    ch.enabled
                      ? "bg-green-600/20 text-green-400"
                      : "bg-gray-600/20 text-gray-400"
                  }`}
                >
                  {ch.enabled ? "启用" : "禁用"}
                </span>
                {isAdmin && (
                  <>
                    <button
                      onClick={() => handleTest(ch.id)}
                      disabled={testingId === ch.id}
                      className="p-1 text-gray-400 hover:text-green-400 transition disabled:opacity-50"
                      title="测试发送"
                    >
                      {testingId === ch.id ? (
                        <Loader2 size={16} className="animate-spin" />
                      ) : (
                        <Play size={16} />
                      )}
                    </button>
                    <button
                      onClick={() => openEdit(ch)}
                      className="p-1 text-gray-400 hover:text-yellow-400 transition"
                      title="编辑"
                    >
                      <Edit3 size={16} />
                    </button>
                    <button
                      onClick={() => setDeleteConfirm(ch.id)}
                      className="p-1 text-gray-400 hover:text-red-400 transition"
                      title="删除"
                    >
                      <Trash2 size={16} />
                    </button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-800 border border-gray-700 rounded-xl w-full max-w-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-white">
                {editingId ? "编辑渠道" : "添加渠道"}
              </h2>
              <button
                onClick={() => {
                  setShowModal(false);
                  setEditData(null);
                }}
                className="text-gray-400 hover:text-white"
              >
                <X size={20} />
              </button>
            </div>
            <form key={editData?.webhook_url || editingId || "new"} onSubmit={handleSubmit} className="space-y-3">
              <InputField
                label="名称"
                name="name"
                required
                defaultValue={editData?.name}
              />
              <div>
                <label className="block text-sm text-gray-300 mb-1">
                  渠道类型
                </label>
                <select
                  name="channel_type"
                  required
                  defaultValue={editData?.channel_type || "wecom"}
                  className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
                >
                  {CHANNEL_TYPE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
              <InputField
                label="Webhook URL"
                name="webhook_url"
                required
                defaultValue={editData?.webhook_url}
              />
              <InputField
                label="加签密钥（选填，钉钉/飞书安全设置）"
                name="sign_secret"
                type="password"
                placeholder={editData?.has_sign_secret ? "留空则不修改" : "可选"}
              />
              <div>
                <label className="block text-sm text-gray-300 mb-1">
                  状态
                </label>
                <select
                  name="enabled"
                  defaultValue={
                    editData ? String(editData.enabled) : "true"
                  }
                  className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
                >
                  <option value="true">启用</option>
                  <option value="false">禁用</option>
                </select>
              </div>
              {formError && (
                <p className="text-red-400 text-sm bg-red-600/10 border border-red-600/30 rounded p-2">
                  {formError}
                </p>
              )}
              <button
                type="submit"
                disabled={submitting}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white py-2 rounded-lg text-sm font-medium flex items-center justify-center gap-2"
              >
                {submitting && <Loader2 size={16} className="animate-spin" />}
                {submitting
                  ? "提交中..."
                  : editingId
                  ? "保存修改"
                  : "确认添加"}
              </button>
            </form>
          </div>
        </div>
      )}

      {deleteConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-800 border border-gray-700 rounded-xl p-6 max-w-sm">
            <p className="text-white mb-4">确认删除此通知渠道？</p>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setDeleteConfirm(null)}
                className="px-4 py-2 rounded-lg bg-gray-700 text-white text-sm"
              >
                取消
              </button>
              <button
                onClick={() => handleDelete(deleteConfirm)}
                disabled={deleting}
                className="px-4 py-2 rounded-lg bg-red-600 text-white text-sm disabled:opacity-50"
              >
                {deleting ? "删除中..." : "确认删除"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function InputField({
  label,
  name,
  required,
  type = "text",
  defaultValue,
  placeholder,
}: {
  label: string;
  name: string;
  required?: boolean;
  type?: string;
  defaultValue?: string;
  placeholder?: string;
}) {
  return (
    <div>
      <label className="block text-sm text-gray-300 mb-1">{label}</label>
      <input
        name={name}
        type={type}
        required={required}
        defaultValue={defaultValue}
        placeholder={placeholder}
        className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
      />
    </div>
  );
}
