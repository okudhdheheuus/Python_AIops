"use client";

import { useState, useCallback, useRef, type DragEvent } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  type Node,
  type Edge,
  type Connection,
  type ReactFlowInstance,
} from "@xyflow/react";
import { Play, Loader2, Save, X, Workflow } from "lucide-react";
import { nodeTypes } from "@/components/AgentNode";
import AgentPalette from "@/components/AgentPalette";
import NodeConfigPanel from "@/components/NodeConfigPanel";
import { getAgentDef, type AgentNodeData, type ApiWorkflowNode, type ApiWorkflowEdge } from "@/lib/agentTypes";

interface WorkflowItem {
  id: string;
  name: string;
  description?: string;
  nodes: unknown[];
  edges: unknown[];
  is_template: boolean;
  created_at: string;
  updated_at?: string;
}

interface ServerOption {
  id: string;
  name: string;
  host: string;
}

interface Props {
  workflow: WorkflowItem | null;
  servers: ServerOption[];
  authFetch: (url: string, options?: RequestInit) => Promise<Response>;
  onSaved: () => void;
  onCancel: () => void;
}

function apiToFlowNodes(nodes: unknown[]): Node[] {
  return (nodes as Array<Record<string, unknown>>).map((n, i) => ({
    id: (n.id as string) || `node-${i}`,
    type: "agentNode",
    position: (n.position as Node["position"]) || {
      x: 250 + (i % 3) * 280,
      y: 100 + Math.floor(i / 3) * 180,
    },
    data: {
      agent_type: (n.agent_type as string) || (n.config as Record<string, unknown>)?.agent_type as string || "generic",
      prompt: (n.prompt as string) || (n.config as Record<string, unknown>)?.prompt as string || "",
      server_id: (n.server_id as string) || (n.config as Record<string, unknown>)?.server_id as string || null,
      timeout: (n.timeout as number) || (n.config as Record<string, unknown>)?.timeout as number || 60,
      max_retries: (n.max_retries as number) || (n.config as Record<string, unknown>)?.max_retries as number || 2,
      condition: (n.condition as string) || (n.config as Record<string, unknown>)?.condition as string || "",
      config: (n.config as Record<string, unknown>) || {},
    },
  }));
}

function apiToFlowEdges(edges: unknown[]): Edge[] {
  return (edges as Array<Record<string, unknown>>).map((e, i) => ({
    id: `edge-${i}`,
    source: e.source as string,
    target: e.target as string,
    animated: true,
    style: { stroke: "#6b7280", strokeWidth: 2 },
  }));
}

function serializeWorkflow(nodes: Node[], edges: Edge[]) {
  const apiNodes: ApiWorkflowNode[] = nodes.map((n) => {
    const d = n.data as AgentNodeData;
    return {
      id: n.id,
      agent_type: d.agent_type,
      prompt: d.prompt || undefined,
      server_id: d.server_id || undefined,
      timeout: d.timeout || undefined,
      max_retries: d.max_retries || undefined,
      condition: d.condition || undefined,
      config: d.config || undefined,
    };
  });
  const apiEdges: ApiWorkflowEdge[] = edges.map((e) => ({
    source: e.source,
    target: e.target,
  }));
  return { nodes: apiNodes, edges: apiEdges };
}

export default function WorkflowEditor({ workflow, servers, authFetch, onSaved, onCancel }: Props) {
  const [nodes, setNodes, onNodesChange] = useNodesState(
    workflow ? apiToFlowNodes(workflow.nodes) : []
  );
  const [edges, setEdges, onEdgesChange] = useEdgesState(
    workflow ? apiToFlowEdges(workflow.edges) : []
  );

  const [name, setName] = useState(workflow?.name || "");
  const [description, setDescription] = useState(workflow?.description || "");
  const [isTemplate, setIsTemplate] = useState(workflow?.is_template || false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<string | null>(null);

  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const rfInstance = useRef<ReactFlowInstance | null>(null);

  const selectedNode = nodes.find((n) => n.id === selectedNodeId);

  const onConnect = useCallback(
    (conn: Connection) => setEdges((eds) => addEdge({ ...conn, animated: true, style: { stroke: "#6b7280", strokeWidth: 2 } }, eds)),
    [setEdges]
  );

  function onDragOver(event: DragEvent) {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    const agentType = event.dataTransfer.getData("application/reactflow-agent-type");
    if (!agentType || !rfInstance.current) return;
    const position = rfInstance.current.screenToFlowPosition({
      x: event.clientX,
      y: event.clientY,
    });
    const newNode: Node = {
      id: crypto.randomUUID(),
      type: "agentNode",
      position,
      data: {
        agent_type: agentType,
        prompt: "",
        server_id: null,
        timeout: 60,
        max_retries: 2,
        condition: "",
        config: {},
      },
    };
    setNodes((nds) => [...nds, newNode]);
  }

  function handleUpdateNode(d: AgentNodeData) {
    if (!selectedNodeId) return;
    setNodes((nds) =>
      nds.map((n) => (n.id === selectedNodeId ? { ...n, data: d } : n))
    );
  }

  function handleDeleteNode() {
    if (!selectedNodeId) return;
    setNodes((nds) => nds.filter((n) => n.id !== selectedNodeId));
    setEdges((eds) => eds.filter((e) => e.source !== selectedNodeId && e.target !== selectedNodeId));
    setSelectedNodeId(null);
  }

  async function handleSave() {
    setSaving(true);
    setSaveError(null);
    const { nodes: apiNodes, edges: apiEdges } = serializeWorkflow(nodes, edges);
    const body: Record<string, unknown> = {
      name,
      description: description || undefined,
      nodes: apiNodes,
      edges: apiEdges,
      is_template: isTemplate,
    };
    try {
      const isEdit = workflow?.id;
      const url = isEdit ? `/api/workflows/${workflow.id}` : "/api/workflows";
      const method = isEdit ? "PUT" : "POST";
      const resp = await authFetch(url, { method, body: JSON.stringify(body) });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error((err as { detail?: string }).detail || `HTTP ${resp.status}`);
      }
      onSaved();
    } catch (e: unknown) {
      setSaveError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  }

  async function handleRun() {
    setRunning(true);
    setRunResult(null);
    try {
      if (!workflow?.id) {
        setRunResult("请先保存工作流后再运行");
        return;
      }
      const resp = await authFetch(`/api/workflows/${workflow.id}/run`, { method: "POST" });
      const data = await resp.json();
      setRunResult(
        `状态: ${data.status} | 节点: ${data.completed_count}/${data.node_count} | 耗时: ${data.duration_ms}ms`
      );
    } catch (e: unknown) {
      setRunResult(`运行失败: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="h-full flex flex-col bg-gray-950">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-4 py-2.5 bg-gray-800 border-b border-gray-700 shrink-0">
        <Workflow size={18} className="text-blue-400 shrink-0" />
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="工作流名称"
          className="bg-gray-900 border border-gray-600 rounded-lg px-3 py-1.5 text-white text-sm w-48 focus:border-blue-500 focus:outline-none"
        />
        <input
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="描述 (可选)"
          className="bg-gray-900 border border-gray-600 rounded-lg px-3 py-1.5 text-gray-300 text-sm w-56 focus:border-blue-500 focus:outline-none"
        />
        <label className="flex items-center gap-1.5 text-gray-400 text-xs cursor-pointer select-none">
          <input
            type="checkbox"
            checked={isTemplate}
            onChange={(e) => setIsTemplate(e.target.checked)}
            className="rounded"
          />
          模板
        </label>
        <div className="flex-1" />
        {runResult && (
          <span className="text-xs text-gray-400 bg-gray-900 px-3 py-1 rounded-lg max-w-xs truncate">
            {runResult}
          </span>
        )}
        <button onClick={handleRun} disabled={running || !workflow?.id} className="flex items-center gap-1.5 bg-green-600 hover:bg-green-700 disabled:opacity-50 px-3 py-1.5 rounded-lg text-white text-xs transition">
          {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
          运行
        </button>
        <button onClick={handleSave} disabled={saving || !name.trim()} className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 px-3 py-1.5 rounded-lg text-white text-xs transition">
          {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
          保存
        </button>
        <button onClick={onCancel} className="flex items-center gap-1.5 bg-gray-700 hover:bg-gray-600 px-3 py-1.5 rounded-lg text-gray-300 text-xs transition">
          <X size={14} />
          取消
        </button>
      </div>

      {saveError && (
        <div className="px-4 py-2 bg-red-600/10 border-b border-red-600/30 text-red-400 text-xs">{saveError}</div>
      )}

      {/* Main area */}
      <div className="flex-1 flex min-h-0">
        <AgentPalette />
        <div className="flex-1 relative">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onDrop={onDrop}
            onDragOver={onDragOver}
            onNodeClick={(_, node) => setSelectedNodeId(node.id)}
            onPaneClick={() => setSelectedNodeId(null)}
            onInit={(instance) => { rfInstance.current = instance; }}
            nodeTypes={nodeTypes}
            fitView
            snapToGrid
            snapGrid={[20, 20]}
            connectionLineStyle={{ stroke: "#3b82f6", strokeWidth: 2 }}
            defaultEdgeOptions={{ animated: true, style: { stroke: "#6b7280", strokeWidth: 2 } }}
            deleteKeyCode={["Backspace", "Delete"]}
            multiSelectionKeyCode="Shift"
          >
            <Background gap={20} size={1} color="#374151" />
            <Controls className="!bg-gray-800 !border-gray-700 !rounded-lg" />
            <MiniMap
              nodeColor={(n) => {
                const def = getAgentDef((n.data as AgentNodeData)?.agent_type);
                return def?.color || "#6b7280";
              }}
              style={{ backgroundColor: "#1f2937" }}
              className="!rounded-lg !overflow-hidden"
            />
          </ReactFlow>
        </div>
        {selectedNode && (
          <NodeConfigPanel
            key={selectedNode.id}
            nodeId={selectedNode.id}
            nodeData={selectedNode.data as AgentNodeData}
            serverOptions={servers}
            onUpdate={handleUpdateNode}
            onDelete={handleDeleteNode}
            onClose={() => setSelectedNodeId(null)}
          />
        )}
      </div>
    </div>
  );
}
