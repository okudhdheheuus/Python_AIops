"use client";

import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import {
  Bot, Cpu, Stethoscope, Wrench, Bell, ScrollText,
  GitBranch, FileText, ShieldCheck, Terminal, Globe, Send, Server,
  type LucideIcon,
} from "lucide-react";
import { getAgentDef, type AgentNodeData } from "@/lib/agentTypes";

const iconMap: Record<string, LucideIcon> = {
  Bot, Cpu, Stethoscope, Wrench, Bell, ScrollText, GitBranch, FileText, ShieldCheck,
  Terminal, Globe, Send,
};

const STATUS_GLOW: Record<string, string> = {
  success: "#22c55e",
  failed: "#ef4444",
  blocked: "#ef4444",
  timeout: "#eab308",
  skipped: "#eab308",
  running: "#3b82f6",
  partial: "#eab308",
};

function AgentNode({ data, selected }: NodeProps) {
  const d = data as unknown as AgentNodeData;
  const def = getAgentDef(d.agent_type);
  const Icon = def ? iconMap[def.icon] || Bot : Bot;
  const accentColor = def?.color || "#6b7280";
  const statusColor = d.run_status ? STATUS_GLOW[d.run_status] : null;

  return (
    <div
      className="bg-gray-800 border border-gray-700 rounded-xl w-[220px] shadow-lg transition-shadow"
      style={{
        borderLeft: `4px solid ${statusColor || accentColor}`,
        boxShadow: statusColor
          ? `0 0 0 2px ${statusColor}80, 0 4px 12px ${statusColor}30`
          : selected
          ? `0 0 0 2px ${accentColor}80, 0 4px 12px ${accentColor}30`
          : undefined,
      }}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!bg-gray-500 !border-gray-700 !w-3 !h-3"
      />
      <div className="p-3">
        <div className="flex items-center gap-2 mb-2">
          <Icon size={18} style={{ color: accentColor }} />
          <span className="text-white text-sm font-medium truncate">
            {def?.name || d.agent_type}
          </span>
          {def?.needsServer && (
            <Server size={12} className="text-yellow-500 ml-auto shrink-0" />
          )}
        </div>
        <div className="text-xs text-gray-500 leading-relaxed line-clamp-2">
          {d.prompt ? d.prompt.slice(0, 80) : "未配置提示词"}
        </div>
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        className="!bg-blue-500 !border-gray-700 !w-3 !h-3"
      />
    </div>
  );
}

export default memo(AgentNode);
export const nodeTypes = { agentNode: AgentNode };
