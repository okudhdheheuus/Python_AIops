"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Server, Bell, MessageSquare, Activity, LogOut, User, Bot, Workflow, BookOpen, FileText, BellRing, ShieldCheck, Settings, ChevronLeft, ChevronRight } from "lucide-react";
import { useAuth } from "@/lib/auth";

const links = [
  { href: "/", label: "仪表盘", icon: LayoutDashboard },
  { href: "/servers", label: "服务器", icon: Server },
  { href: "/alerts", label: "告警中心", icon: Bell },
  { href: "/chat", label: "AI 助手", icon: MessageSquare },
  { href: "/patrol", label: "巡检记录", icon: Activity },
  { href: "/agents", label: "智能代理", icon: Bot },
  { href: "/workflows", label: "工作流", icon: Workflow },
  { href: "/knowledge", label: "知识库", icon: BookOpen },
  { href: "/audit", label: "审计日志", icon: FileText },
  { href: "/notifications", label: "通知管理", icon: BellRing },
  { href: "/remediation", label: "自动修复", icon: ShieldCheck },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { user, logout, isAuthenticated } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("sidebarCollapsed");
    if (saved === "1") setCollapsed(true);
    setMounted(true);
  }, []);

  function toggle() {
    setCollapsed((v) => {
      localStorage.setItem("sidebarCollapsed", v ? "0" : "1");
      return !v;
    });
  }

  if (!mounted) {
    return <aside className="w-56 bg-gray-800/50 border-r border-gray-700 shrink-0" />;
  }

  return (
    <aside
      className={`bg-gray-800/50 border-r border-gray-700 flex flex-col shrink-0 transition-all duration-200 ${
        collapsed ? "w-[60px] px-2 py-4" : "w-56 p-4"
      }`}
    >
      <div className={`font-bold text-blue-400 mb-8 flex items-center ${collapsed ? "justify-center" : "px-3"}`}>
        {collapsed ? <span className="text-sm">IT</span> : <span className="text-lg">ITOps</span>}
      </div>

      <nav className="flex flex-col gap-1 flex-1">
        {links.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              title={collapsed ? label : undefined}
              className={`flex items-center gap-3 rounded-lg text-sm transition ${
                collapsed ? "justify-center p-2" : "px-3 py-2"
              } ${
                active
                  ? "bg-blue-600/20 text-blue-400"
                  : "text-gray-400 hover:text-white hover:bg-gray-700/50"
              }`}
            >
              <Icon size={18} className="shrink-0" />
              {!collapsed && label}
            </Link>
          );
        })}
      </nav>

      <div className={`border-t border-gray-700 pt-3 ${collapsed ? "px-1" : ""}`}>
        {isAuthenticated ? (
          <div className={`space-y-2 ${collapsed ? "flex flex-col items-center" : ""}`}>
            <div className={`text-sm text-gray-400 ${collapsed ? "flex justify-center" : "flex items-center gap-2 px-3"}`}>
              <User size={16} />
              {!collapsed && user?.username}
            </div>
            <Link
              href="/settings"
              title={collapsed ? "用户设置" : undefined}
              className={`flex items-center rounded-lg text-sm transition ${
                collapsed ? "justify-center p-2" : "gap-2 px-3 py-2"
              } ${
                pathname === "/settings"
                  ? "bg-blue-600/20 text-blue-400"
                  : "text-gray-400 hover:text-white hover:bg-gray-700/50"
              }`}
            >
              <Settings size={16} />
              {!collapsed && "用户设置"}
            </Link>
            <button
              onClick={logout}
              title={collapsed ? "退出登录" : undefined}
              className={`flex items-center rounded-lg text-sm text-gray-400 hover:text-red-400 hover:bg-gray-700/50 w-full transition ${
                collapsed ? "justify-center p-2" : "gap-2 px-3 py-2"
              }`}
            >
              <LogOut size={16} />
              {!collapsed && "退出登录"}
            </button>
          </div>
        ) : (
          <Link
            href="/login"
            className={`flex items-center rounded-lg text-sm text-gray-400 hover:text-white hover:bg-gray-700/50 transition ${
              collapsed ? "justify-center p-2" : "gap-2 px-3 py-2"
            }`}
          >
            <User size={16} />
            {!collapsed && "登录"}
          </Link>
        )}
      </div>

      {/* Toggle button */}
      <button
        onClick={toggle}
        className={`mt-3 flex items-center justify-center text-gray-600 hover:text-gray-300 transition-colors ${
          collapsed ? "" : "border-t border-gray-700 pt-2"
        }`}
        title={collapsed ? "展开导航栏" : "收起导航栏"}
      >
        {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
      </button>
    </aside>
  );
}
