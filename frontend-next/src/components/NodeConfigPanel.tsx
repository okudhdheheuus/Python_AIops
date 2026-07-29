"use client";

import { useState } from "react";
import { X, Trash2 } from "lucide-react";
import { AGENT_TYPES, getAgentDef, type AgentNodeData } from "@/lib/agentTypes";

interface ServerOption {
  id: string;
  name: string;
  host: string;
}

interface Props {
  nodeId: string | null;
  nodeData: AgentNodeData | null;
  serverOptions: ServerOption[];
  onUpdate: (data: AgentNodeData) => void;
  onDelete: () => void;
  onClose: () => void;
}

export default function NodeConfigPanel({
  nodeId,
  nodeData,
  serverOptions,
  onUpdate,
  onDelete,
  onClose,
}: Props) {
  const [local, setLocal] = useState<AgentNodeData | null>(nodeData);

  if (!nodeId || !local) return null;

  const def = getAgentDef(local.agent_type);
  const needsServer = def?.needsServer || false;

  function update<K extends keyof AgentNodeData>(key: K, value: AgentNodeData[K]) {
    const next = { ...local, [key]: value } as AgentNodeData;
    setLocal(next);
    onUpdate(next);
  }

  return (
    <div className="w-[320px] bg-gray-800 border-l border-gray-700 overflow-y-auto shrink-0 flex flex-col">
      <div className="flex items-center justify-between p-4 border-b border-gray-700">
        <h3 className="text-sm font-semibold text-white">节点配置</h3>
        <button onClick={onClose} className="text-gray-400 hover:text-white">
          <X size={18} />
        </button>
      </div>

      <div className="flex-1 p-4 space-y-4">
        <div>
          <label className="block text-xs text-gray-400 mb-1">Agent 类型</label>
          <select
            value={local.agent_type}
            onChange={(e) => update("agent_type", e.target.value)}
            className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
          >
            {AGENT_TYPES.map((a) => (
              <option key={a.type} value={a.type}>{a.name}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs text-gray-400 mb-1">提示词 / 指令</label>
          <textarea
            value={local.prompt}
            onChange={(e) => update("prompt", e.target.value)}
            rows={4}
            placeholder="输入给 Agent 的提示词或指令..."
            className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none resize-none"
          />
        </div>

        {needsServer && (
          <div>
            <label className="block text-xs text-gray-400 mb-1">
              目标服务器 {serverOptions.length === 0 && <span className="text-yellow-400">(无可用服务器)</span>}
            </label>
            <select
              value={local.server_id || ""}
              onChange={(e) => update("server_id", e.target.value || null)}
              className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
            >
              <option value="">不指定服务器</option>
              {serverOptions.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.host})
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs text-gray-400 mb-1">超时 (秒)</label>
            <input
              type="number"
              value={local.timeout}
              onChange={(e) => update("timeout", Number(e.target.value) || 60)}
              min={5}
              max={600}
              className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">最大重试</label>
            <input
              type="number"
              value={local.max_retries}
              onChange={(e) => update("max_retries", Number(e.target.value) || 0)}
              min={0}
              max={10}
              className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
        </div>

        <div>
          <label className="block text-xs text-gray-400 mb-1">执行条件 (可选)</label>
          <input
            type="text"
            value={local.condition}
            onChange={(e) => update("condition", e.target.value)}
            placeholder='如: contains:error 或 true/false'
            className="w-full bg-gray-900 border border-gray-600 rounded-lg px-3 py-2 text-white text-sm focus:border-blue-500 focus:outline-none"
          />
        </div>
      </div>

      <div className="p-4 border-t border-gray-700">
        <button
          onClick={onDelete}
          className="w-full flex items-center justify-center gap-2 bg-red-600/10 border border-red-600/30 hover:bg-red-600/20 text-red-400 py-2 rounded-lg text-sm transition"
        >
          <Trash2 size={16} />
          删除节点
        </button>
      </div>
    </div>
  );
}
