"use client";

import { useEffect, useState } from "react";
import { Server, Activity, Bell, Cpu } from "lucide-react";
import { useAuth } from "@/lib/auth";

interface DashboardData {
  servers: number;
  agents: number;
  workflows: number;
  total_alerts: number;
  firing_alerts: number;
}

interface PatrolSummary {
  total: number;
  success: number;
  warning: number;
  error: number;
  avg_cpu: number;
  avg_memory: number;
  avg_disk: number;
}

export default function DashboardPage() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [patrol, setPatrol] = useState<PatrolSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { token, authFetch } = useAuth();

  useEffect(() => {
    if (!token) return;

    async function fetchData() {
      try {
        setLoading(true);
        setError(null);
        const [dashRes, patrolRes] = await Promise.all([
          authFetch(`/api/dashboard/stats`),
          authFetch(`/api/patrol/summary?days=7`),
        ]);
        if (!dashRes.ok) throw new Error(`仪表盘 API 返回 ${dashRes.status}`);
        if (!patrolRes.ok) throw new Error(`巡检 API 返回 ${patrolRes.status}`);
        setDashboard(await dashRes.json());
        setPatrol(await patrolRes.json());
      } catch (error: unknown) {
        setError(error instanceof Error ? error.message : String(error));
      } finally {
        setLoading(false);
      }
    }
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [token, authFetch]);

  if (!token) return <LoginPrompt />;
  if (loading) return <div className="p-8 text-gray-400">加载中...</div>;
  if (error) return <div className="p-8 text-red-500">{error}</div>;

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <h1 className="text-2xl font-bold text-white mb-6">运维仪表盘</h1>

      {dashboard?.servers === 0 && (
        <div className="bg-yellow-600/10 border border-yellow-600/30 rounded-xl p-4 mb-6 text-sm text-yellow-300">
          <strong>尚无服务器</strong> — 请先前往
          <a href="/servers" className="text-blue-400 hover:underline mx-1">服务器管理</a>
          添加至少一台服务器并配置 SSH 凭据，巡检调度器才会采集指标数据。巡检每 5 分钟自动运行一次。
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <MetricCard icon={<Server />} label="管理服务器" value={dashboard?.servers ?? 0} />
        <MetricCard icon={<Bell />} label="告警总数" value={dashboard?.total_alerts ?? 0} />
        <MetricCard icon={<Activity />} label="活跃告警" value={dashboard?.firing_alerts ?? 0} color="text-red-400" />
      </div>

      {patrol && patrol.total === 0 ? (
        <div className="bg-gray-800/50 rounded-xl border border-gray-700 p-6 text-sm text-gray-400">
          <h2 className="text-lg font-semibold text-white mb-2 flex items-center gap-2">
            <Cpu size={20} /> 近7日巡检概览
          </h2>
          暂无巡检记录 — 添加服务器后，巡检调度器每 5 分钟自动采集一次数据。
        </div>
      ) : patrol ? (
        <div className="bg-gray-800/50 rounded-xl border border-gray-700 p-6">
          <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Cpu size={20} /> 近7日巡检概览
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <MiniStat label="巡检次数" value={patrol.total} />
            <MiniStat label="正常" value={patrol.success} color="text-green-400" />
            <MiniStat label="警告" value={patrol.warning} color="text-yellow-400" />
            <MiniStat label="失败" value={patrol.error} color="text-red-400" />
          </div>
          <div className="text-sm text-gray-400">
            平均资源: CPU {patrol.avg_cpu}% / 内存 {patrol.avg_memory}% / 磁盘 {patrol.avg_disk}%
          </div>
        </div>
      ) : null}
    </div>
  );
}

function LoginPrompt() {
  return (
    <div className="flex items-center justify-center h-full">
      <div className="text-center text-gray-500">
        <Server size={48} className="mx-auto mb-4 opacity-50" />
        <p className="mb-2">请先登录以查看仪表盘</p>
        <a href="/login" className="text-blue-400 hover:underline text-sm">前往登录</a>
      </div>
    </div>
  );
}

function MetricCard({ icon, label, value, color = "text-blue-400" }: {
  icon: React.ReactNode; label: string; value: number; color?: string;
}) {
  return (
    <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-4 flex items-center gap-4">
      <div className={color}>{icon}</div>
      <div>
        <div className="text-sm text-gray-400">{label}</div>
        <div className={`text-2xl font-bold ${color}`}>{value}</div>
      </div>
    </div>
  );
}

function MiniStat({ label, value, color = "text-white" }: {
  label: string; value: number; color?: string;
}) {
  return (
    <div className="text-center">
      <div className="text-xs text-gray-400">{label}</div>
      <div className={`text-xl font-bold ${color}`}>{value}</div>
    </div>
  );
}
