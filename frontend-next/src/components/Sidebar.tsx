"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Server, Bell, MessageSquare, Activity, LogOut, User, Bot, Workflow, BookOpen, FileText, BellRing, ShieldCheck } from "lucide-react";
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

  return (
    <aside className="w-56 bg-gray-800/50 border-r border-gray-700 flex flex-col p-4">
      <div className="text-lg font-bold text-blue-400 mb-8 px-3">ITOps</div>
      <nav className="flex flex-col gap-1 flex-1">
        {links.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition ${
              pathname === href
                ? "bg-blue-600/20 text-blue-400"
                : "text-gray-400 hover:text-white hover:bg-gray-700/50"
            }`}
          >
            <Icon size={18} />
            {label}
          </Link>
        ))}
      </nav>

      <div className="border-t border-gray-700 pt-3 mt-auto">
        {isAuthenticated ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2 px-3 text-sm text-gray-400">
              <User size={16} />
              {user?.username}
            </div>
            <button
              onClick={logout}
              className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-gray-400 hover:text-red-400 hover:bg-gray-700/50 w-full transition"
            >
              <LogOut size={16} />
              退出登录
            </button>
          </div>
        ) : (
          <Link
            href="/login"
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-gray-400 hover:text-white hover:bg-gray-700/50 transition"
          >
            <User size={16} />
            登录
          </Link>
        )}
      </div>
    </aside>
  );
}
