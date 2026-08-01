"use client";

import { useAuth } from "@/lib/auth";
import { AlertTriangle } from "lucide-react";

export default function DemoBanner() {
  const { user } = useAuth();

  // 仅对非 admin 用户显示
  if (!user || user.role === "admin") return null;

  return (
    <div className="bg-blue-600/10 border-b border-blue-500/30 px-4 py-1.5 text-xs text-blue-400 flex items-center gap-2">
      <AlertTriangle size={12} />
      <span>演示环境 — 数据与其他用户隔离。建议自行部署以获得完整控制权：</span>
      <a
        href="https://github.com/okudhdheheuus/Python_AIops"
        target="_blank"
        rel="noopener noreferrer"
        className="text-blue-300 hover:text-blue-200 underline"
      >
        GitHub
      </a>
    </div>
  );
}
