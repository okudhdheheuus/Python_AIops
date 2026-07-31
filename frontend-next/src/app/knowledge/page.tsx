"use client";

import { useEffect, useState, useRef } from "react";
import { BookOpen, Search, Tag, Database, ChevronLeft, ChevronRight, Plus, Pencil, Trash2, X } from "lucide-react";
import { useAuth } from "@/lib/auth";

interface KnowledgeEntry {
  id: string;
  title: string;
  content: string;
  category: string;
  tags: string;
  source?: string;
  enabled: boolean;
  created_at: string;
}

interface SearchResult {
  id: string;
  title: string;
  content: string;
  category: string;
  tags: string;
  score: number;
}

export default function KnowledgePage() {
  const { token, user, authFetch } = useAuth();
  const [entries, setEntries] = useState<KnowledgeEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);

  const [category, setCategory] = useState("");
  const [tag, setTag] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const pageSize = 20;

  const [seeding, setSeeding] = useState(false);
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // CRUD modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formTitle, setFormTitle] = useState("");
  const [formContent, setFormContent] = useState("");
  const [formCategory, setFormCategory] = useState("");
  const [formTags, setFormTags] = useState("");
  const [saving, setSaving] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [detailEntry, setDetailEntry] = useState<KnowledgeEntry | null>(null);

  async function fetchEntries() {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (category) params.set("category", category);
      if (tag) params.set("tag", tag);
      params.set("page", String(page));
      params.set("page_size", String(pageSize));
      const resp = await authFetch(`/api/knowledge/entries?${params.toString()}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setEntries(data.items || []);
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
    fetchEntries();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, authFetch, category, tag, page]);

  function handleSearch(query: string) {
    setSearchQuery(query);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    if (!query.trim()) {
      setSearchResults([]);
      return;
    }
    searchTimer.current = setTimeout(async () => {
      setSearching(true);
      try {
        const resp = await authFetch(`/api/knowledge/search?q=${encodeURIComponent(query)}&limit=10`);
        if (resp.ok) {
          const data = await resp.json();
          setSearchResults(data.items || []);
        }
      } catch {
        // ignore search errors
      } finally {
        setSearching(false);
      }
    }, 400);
  }

  async function handleSeed() {
    setSeeding(true);
    try {
      const resp = await authFetch("/api/knowledge/seed", { method: "POST" });
      if (resp.ok) {
        fetchEntries();
      }
    } catch {
      // ignore
    } finally {
      setSeeding(false);
    }
  }

  function openCreate() {
    setEditingId(null);
    setFormTitle("");
    setFormContent("");
    setFormCategory("");
    setFormTags("");
    setModalOpen(true);
  }

  function openEdit(e: KnowledgeEntry) {
    setEditingId(e.id);
    setFormTitle(e.title);
    setFormContent(e.content);
    setFormCategory(e.category || "");
    setFormTags(e.tags || "");
    setModalOpen(true);
  }

  async function handleSave() {
    setSaving(true);
    try {
      const body = {
        title: formTitle,
        content: formContent,
        category: formCategory,
        tags: formTags,
      };
      const url = editingId
        ? `/api/knowledge/entries/${editingId}`
        : "/api/knowledge/entries";
      const method = editingId ? "PUT" : "POST";
      const resp = await authFetch(url, {
        method,
        body: JSON.stringify(body),
        headers: { "Content-Type": "application/json" },
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      setModalOpen(false);
      fetchEntries();
    } catch {
      // ignore
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("确定删除此知识条目？")) return;
    try {
      const resp = await authFetch(`/api/knowledge/entries/${id}`, { method: "DELETE" });
      if (resp.ok) fetchEntries();
    } catch {
      // ignore
    }
  }

  async function viewDetail(id: string) {
    try {
      const resp = await authFetch(`/api/knowledge/entries/${id}`);
      if (resp.ok) {
        const data = await resp.json();
        setDetailId(id);
        setDetailEntry(data);
      }
    } catch {
      // ignore
    }
  }

  const totalPages = Math.ceil(total / pageSize);

  if (!token)
    return (
      <div className="p-8 text-center text-gray-500 mt-20">
        <BookOpen size={48} className="mx-auto mb-4 opacity-50" />
        <p>请先登录</p>
      </div>
    );

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">知识库</h1>
          <p className="text-sm text-gray-500 mt-0.5">基于语义检索的运维知识 RAG，为 AI 助手提供专业上下文</p>
        </div>
        <div className="flex items-center gap-2">
          {user?.role === "admin" && (
            <button
              onClick={handleSeed}
              disabled={seeding}
              className="bg-green-600 hover:bg-green-700 disabled:opacity-50 px-4 py-2 rounded-lg text-white flex items-center gap-2 text-sm"
            >
              <Database size={16} />
              {seeding ? "写入中..." : "初始化预设知识"}
            </button>
          )}
          <button
            onClick={openCreate}
            className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg text-white flex items-center gap-2 text-sm"
          >
            <Plus size={16} />
            新增条目
          </button>
        </div>
      </div>

      <div className="mb-6 space-y-3">
        <div className="relative">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            value={searchQuery}
            onChange={(e) => handleSearch(e.target.value)}
            placeholder="语义搜索运维知识..."
            className="w-full bg-gray-800/50 border border-gray-700 rounded-lg pl-10 pr-4 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
          />
        </div>

        {searchResults.length > 0 && (
          <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-4 space-y-3">
            <h3 className="text-sm font-semibold text-gray-300">语义搜索结果 ({searchResults.length})</h3>
            {searchResults.map((r) => (
              <div key={r.id} className="bg-gray-900/50 rounded-lg p-3 cursor-pointer hover:bg-gray-900 transition-colors" onClick={() => viewDetail(r.id)}>
                <div className="flex items-center justify-between">
                  <div className="text-white font-medium text-sm">{r.title}</div>
                  <span className="text-xs text-blue-400">相关度 {(r.score * 100).toFixed(0)}%</span>
                </div>
                <div className="text-gray-400 text-xs mt-1">{r.content?.slice(0, 200)}</div>
                {r.category && (
                  <span className="inline-block text-xs bg-blue-600/20 text-blue-400 px-2 py-0.5 rounded mt-1">{r.category}</span>
                )}
              </div>
            ))}
          </div>
        )}

        {searching && <div className="text-sm text-gray-500">搜索中...</div>}

        <div className="flex gap-3">
          <input
            value={category}
            onChange={(e) => { setCategory(e.target.value); setPage(1); }}
            placeholder="按分类筛选..."
            className="flex-1 bg-gray-800/50 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
          />
          <input
            value={tag}
            onChange={(e) => { setTag(e.target.value); setPage(1); }}
            placeholder="按标签筛选..."
            className="flex-1 bg-gray-800/50 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
          />
        </div>
      </div>

      {loading ? (
        <div className="text-gray-400 p-8">加载中...</div>
      ) : error ? (
        <div className="text-red-500 p-8">{error}</div>
      ) : entries.length === 0 ? (
        <div className="text-center text-gray-500 mt-20">
          <BookOpen size={48} className="mx-auto mb-4 opacity-50" />
          <p>暂无知识库条目</p>
          <p className="text-sm mt-2 text-gray-600">点击「初始化预设知识」写入 22 条运维知识，或手动新增条目</p>
        </div>
      ) : (
        <>
          <div className="grid gap-3">
            {entries.map((e) => (
              <div key={e.id} className="bg-gray-800/50 border border-gray-700 rounded-xl p-4 hover:border-gray-500 transition-colors">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2 cursor-pointer" onClick={() => viewDetail(e.id)}>
                    <BookOpen size={16} className="text-blue-400" />
                    <span className="text-white font-medium hover:text-blue-400 transition-colors">{e.title}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {e.category && (
                      <span className="text-xs bg-blue-600/20 text-blue-400 px-2 py-1 rounded">{e.category}</span>
                    )}
                    {e.source && (
                      <span className="text-xs bg-gray-700 px-2 py-1 rounded text-gray-400">{e.source}</span>
                    )}
                    <button onClick={() => openEdit(e)} className="text-gray-500 hover:text-blue-400 transition-colors" title="编辑">
                      <Pencil size={14} />
                    </button>
                    <button onClick={() => handleDelete(e.id)} className="text-gray-500 hover:text-red-400 transition-colors" title="删除">
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
                <div className="text-sm text-gray-400 line-clamp-2">{e.content}</div>
                <div className="flex items-center gap-2 mt-2">
                  {e.tags &&
                    e.tags.split(",").map((t) => (
                      <span key={t} className="text-xs text-gray-500 flex items-center gap-1">
                        <Tag size={10} /> {t.trim()}
                      </span>
                    ))}
                </div>
              </div>
            ))}
          </div>

          {total > pageSize && (
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
                <span>第 {page} / {totalPages} 页</span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                  className="p-1 hover:text-white disabled:opacity-30"
                >
                  <ChevronRight size={18} />
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Create/Edit Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setModalOpen(false)}>
          <div className="bg-gray-800 border border-gray-700 rounded-xl w-full max-w-lg p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-white">{editingId ? "编辑条目" : "新增条目"}</h2>
              <button onClick={() => setModalOpen(false)} className="text-gray-500 hover:text-white">
                <X size={18} />
              </button>
            </div>
            <div className="space-y-3">
              <input
                value={formTitle}
                onChange={(e) => setFormTitle(e.target.value)}
                placeholder="标题"
                className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
              />
              <textarea
                value={formContent}
                onChange={(e) => setFormContent(e.target.value)}
                placeholder="内容（支持 Markdown）"
                rows={6}
                className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none resize-none"
              />
              <div className="flex gap-3">
                <input
                  value={formCategory}
                  onChange={(e) => setFormCategory(e.target.value)}
                  placeholder="分类（如：故障排查）"
                  className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
                />
                <input
                  value={formTags}
                  onChange={(e) => setFormTags(e.target.value)}
                  placeholder="标签（逗号分隔）"
                  className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-4">
              <button onClick={() => setModalOpen(false)} className="bg-gray-700 hover:bg-gray-600 px-4 py-2 rounded-lg text-gray-300 text-sm transition-colors">取消</button>
              <button onClick={handleSave} disabled={saving || !formTitle.trim() || !formContent.trim()} className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 px-4 py-2 rounded-lg text-white text-sm transition-colors">
                {saving ? "保存中..." : "保存"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Detail Modal */}
      {detailId && detailEntry && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => { setDetailId(null); setDetailEntry(null); }}>
          <div className="bg-gray-800 border border-gray-700 rounded-xl w-full max-w-2xl max-h-[80vh] overflow-y-auto p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-white">{detailEntry.title}</h2>
              <button onClick={() => { setDetailId(null); setDetailEntry(null); }} className="text-gray-500 hover:text-white">
                <X size={18} />
              </button>
            </div>
            <div className="flex items-center gap-2 mb-3">
              {detailEntry.category && <span className="text-xs bg-blue-600/20 text-blue-400 px-2 py-1 rounded">{detailEntry.category}</span>}
              {detailEntry.tags && detailEntry.tags.split(",").map((t) => (
                <span key={t} className="text-xs text-gray-500 flex items-center gap-1"><Tag size={10} /> {t.trim()}</span>
              ))}
            </div>
            <div className="text-gray-300 text-sm whitespace-pre-wrap leading-relaxed">{detailEntry.content}</div>
          </div>
        </div>
      )}
    </div>
  );
}
