"use client";

import type { DragEvent } from "react";
import { Bot, Cpu, Stethoscope, Wrench, Bell, ScrollText, GitBranch, FileText, ShieldCheck, Terminal, Globe, Send } from "lucide-react";
import { AGENT_TYPES, getAgentDef } from "@/lib/agentTypes";

const iconMap: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  Bot, Cpu, Stethoscope, Wrench, Bell, ScrollText, GitBranch, FileText, ShieldCheck,
  Terminal, Globe, Send,
};

export default function AgentPalette() {
  function onDragStart(event: DragEvent, agentType: string) {
    // 同时写入自定义类型和 text/plain，兼容部分浏览器对自定义 MIME 类型读取的差异
    event.dataTransfer.setData("application/reactflow-agent-type", agentType);
    event.dataTransfer.setData("text/plain", agentType);
    event.dataTransfer.effectAllowed = "move";
  }

  return (
    <div className="w-[210px] bg-gray-900/60 border-r border-gray-700 overflow-y-auto shrink-0 p-3">
      <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3 px-1">
        Agent 类型
      </h3>
      <div className="space-y-1.5">
        {AGENT_TYPES.map((agent) => {
          const def = getAgentDef(agent.type);
          const Icon = def ? iconMap[def.icon] || Bot : Bot;
          const color = def?.color || "#6b7280";
          return (
            <div
              key={agent.type}
              draggable
              onDragStart={(e) => onDragStart(e, agent.type)}
              className="flex items-center gap-2 p-2.5 rounded-lg cursor-grab active:cursor-grabbing border border-gray-700/50 hover:border-gray-500 transition-colors group"
              style={{ backgroundColor: `${color}15` }}
            >
              <Icon size={16} style={{ color }} />
              <div className="flex-1 min-w-0">
                <div className="text-white text-xs font-medium truncate">{agent.name}</div>
                <div className="text-gray-500 text-[10px] truncate">{agent.description}</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
