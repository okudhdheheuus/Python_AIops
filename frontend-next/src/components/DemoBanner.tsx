"use client";

import { useAuth } from "@/lib/auth";
import { AlertTriangle } from "lucide-react";

export default function DemoBanner() {
  const { user } = useAuth();

  // 仅对非 admin 用户显示
  if (!user || user.role === "admin") return null;

  return (
    <div className="bg-yellow-600/10 border-b border-yellow-600/30 px-4 py-1.5 text-xs text-yellow-400 flex items-center gap-2">
      <AlertTriangle size={12} />
      <span>演示环境 — 服务器信息已隐藏。完整功能请自行部署：</span>
      <a
        href="https://github.com/okudhdheheuus/Python_AIops"
        target="_blank"
        rel="noopener noreferrer"
        className="text-blue-400 hover:text-blue-300 underline"
      >
        GitHub
      </a>
    </div>
  );
}
