"use client";

import { useEffect, useState, useRef } from "react";
import { BookOpen, Search, Tag, Database, ChevronLeft, ChevronRight } from "lucide-react";
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

export default function KnowledgePage() {
  const { token, user, authFetch } = useAuth();
  const [entries, setEntries] = useState<KnowledgeEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<{ title: string; content: string; score: number }[]>([]);
  const [searching, setSearching] = useState(false);

  const [category, setCategory] = useState("");
  const [tag, setTag] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const pageSize = 20;

  const [seeding, setSeeding] = useState(false);
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

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
        <h1 className="text-2xl font-bold text-white">知识库</h1>
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
      </div>

      <div className="mb-6 space-y-3">
        <div className="relative">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
          <input
            value={searchQuery}
            onChange={(e) => handleSearch(e.target.value)}
            placeholder="搜索运维知识..."
            className="w-full bg-gray-800/50 border border-gray-700 rounded-lg pl-10 pr-4 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
          />
        </div>

        {searchResults.length > 0 && (
          <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-4 space-y-3">
            <h3 className="text-sm font-semibold text-gray-300">搜索结果 ({searchResults.length})</h3>
            {searchResults.map((r, i) => (
              <div key={i} className="bg-gray-900/50 rounded-lg p-3">
                <div className="text-white font-medium text-sm">{r.title}</div>
                <div className="text-gray-400 text-xs mt-1">{r.content?.slice(0, 300)}</div>
                <div className="text-gray-500 text-xs mt-1">相关度: {(r.score * 100).toFixed(0)}%</div>
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
        </div>
      ) : (
        <>
          <div className="grid gap-3">
            {entries.map((e) => (
              <div key={e.id} className="bg-gray-800/50 border border-gray-700 rounded-xl p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <BookOpen size={16} className="text-blue-400" />
                    <span className="text-white font-medium">{e.title}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {e.category && (
                      <span className="text-xs bg-blue-600/20 text-blue-400 px-2 py-1 rounded">{e.category}</span>
                    )}
                    {e.source && (
                      <span className="text-xs bg-gray-700 px-2 py-1 rounded text-gray-400">{e.source}</span>
                    )}
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
          )}
        </>
      )}
    </div>
  );
}
