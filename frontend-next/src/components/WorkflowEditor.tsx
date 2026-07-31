"use client";

import { useState, useCallback, useEffect, useRef } from "react";
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
  id?: string;
  name: string;
  description?: string;
  nodes: unknown[];
  edges: unknown[];
  is_template: boolean;
  created_at: string;
  updated_at?: string;
}

export interface NodeRunResult {
  status: string;
  output: string;
  duration_ms: number;
  retries: number;
  error?: string | null;
  commands?: string;
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
  onWorkflowCreated?: (id: string) => void;
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
      position: n.position,
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

export default function WorkflowEditor({ workflow, servers, authFetch, onSaved, onCancel, onWorkflowCreated }: Props) {
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
  const [runResults, setRunResults] = useState<Record<string, NodeRunResult> | null>(null);
  // 已保存的工作流 id；未保存时为 null，运行时会先自动保存
  const [wfId, setWfId] = useState<string | null>(workflow?.id || null);

  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const rfInstance = useRef<ReactFlowInstance | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const selectedNode = nodes.find((n) => n.id === selectedNodeId);

  const onConnect = useCallback(
    (conn: Connection) => setEdges((eds) => addEdge({ ...conn, animated: true, style: { stroke: "#6b7280", strokeWidth: 2 } }, eds)),
    [setEdges]
  );

  // 拖放: 用原生 DOM 事件绕过 ReactFlow 内部 SyntheticEvent 拦截
  useEffect(() => {
    const el = wrapperRef.current;
    if (!el) return;

    function handleDragOver(e: Event) {
      e.preventDefault();
      (e as globalThis.DragEvent).dataTransfer!.dropEffect = "move";
    }

    function handleDrop(e: Event) {
      e.preventDefault();
      const de = e as globalThis.DragEvent;
      const agentType = de.dataTransfer?.getData("application/reactflow-agent-type");
      if (!agentType || !rfInstance.current) return;
      const position = rfInstance.current.screenToFlowPosition({
        x: de.clientX,
        y: de.clientY,
      });
      setNodes((nds) => [
        ...nds,
        {
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
        },
      ]);
    }

    el.addEventListener("dragover", handleDragOver, true);
    el.addEventListener("drop", handleDrop, true);
    return () => {
      el.removeEventListener("dragover", handleDragOver, true);
      el.removeEventListener("drop", handleDrop, true);
    };
  }, [setNodes]);

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
      const isEdit = wfId;
      const url = isEdit ? `/api/workflows/${wfId}` : "/api/workflows";
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
    setRunResults(null);
    try {
      if (nodes.length === 0) {
        setRunResult("请先添加节点再运行");
        return;
      }
      // 未保存的工作流先自动保存，保证有执行历史
      let runWorkflowId = wfId;
      if (!runWorkflowId) {
        const { nodes: apiNodes, edges: apiEdges } = serializeWorkflow(nodes, edges);
        const resp = await authFetch("/api/workflows", {
          method: "POST",
          body: JSON.stringify({
            name: name.trim() || "未命名工作流",
            description: description || undefined,
            nodes: apiNodes,
            edges: apiEdges,
            is_template: isTemplate,
          }),
        });
        if (!resp.ok) {
          const err = await resp.json().catch(() => ({}));
          throw new Error((err as { detail?: string }).detail || `保存失败 HTTP ${resp.status}`);
        }
        const created = await resp.json();
        runWorkflowId = created.id as string;
        setWfId(runWorkflowId);
        onWorkflowCreated?.(runWorkflowId);
      }
      const resp = await authFetch(`/api/workflows/${runWorkflowId}/run`, { method: "POST" });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error((err as { detail?: string }).detail || `运行失败 HTTP ${resp.status}`);
      }
      const data = await resp.json();
      setRunResult(
        `状态: ${data.status} | 节点: ${data.completed_count}/${data.node_count} | 耗时: ${data.duration_ms}ms`
      );
      if (data.results) {
        setRunResults(data.results as Record<string, NodeRunResult>);
        setNodes((nds) =>
          nds.map((n) => {
            const status = (data.results as Record<string, { status?: string }>)[n.id]?.status;
            return status ? { ...n, data: { ...(n.data as AgentNodeData), run_status: status } } : n;
          })
        );
      }
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
        <button
          onClick={handleRun}
          disabled={running || nodes.length === 0}
          title={nodes.length === 0 ? "请先在画布中添加节点" : "运行工作流"}
          className="flex items-center gap-1.5 bg-green-600 hover:bg-green-700 disabled:opacity-50 px-3 py-1.5 rounded-lg text-white text-xs transition"
        >
          {running ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
          {wfId ? "运行" : "保存并运行"}
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

      {/* 逐节点运行结果 */}
      {runResults && (
        <div className="px-4 py-2 bg-gray-900/80 border-b border-gray-700 max-h-40 overflow-y-auto shrink-0">
          {nodes.map((n) => {
            const d = n.data as AgentNodeData;
            const r = runResults[n.id];
            if (!r) return null;
            const def = getAgentDef(d.agent_type);
            const statusColor =
              r.status === "success"
                ? "text-green-400"
                : r.status === "failed" || r.status === "blocked"
                ? "text-red-400"
                : r.status === "timeout" || r.status === "skipped"
                ? "text-yellow-400"
                : "text-gray-400";
            return (
              <div key={n.id} className="text-xs py-1.5 border-b border-gray-800 last:border-0">
                <div className="flex items-center gap-2">
                  <span className={`font-medium ${statusColor}`}>{def?.name || d.agent_type}</span>
                  <span className="text-gray-500">
                    {r.status} · {r.duration_ms}ms{r.retries ? ` · 重试${r.retries}次` : ""}
                  </span>
                </div>
                {r.error && <div className="text-red-400 mt-0.5">{r.error}</div>}
                {r.commands && (
                  <details className="mt-1">
                    <summary className="text-gray-500 cursor-pointer hover:text-gray-400">生成命令</summary>
                    <pre className="text-gray-400 mt-0.5 bg-gray-950 px-2 py-1 rounded text-[10px] overflow-x-auto whitespace-pre-wrap">{r.commands}</pre>
                  </details>
                )}
                {r.output && (
                  <div className="text-gray-400 mt-0.5 line-clamp-3 whitespace-pre-wrap">{r.output}</div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Main area */}
      <div className="flex-1 flex min-h-0">
        <AgentPalette />
        <div className="flex-1 relative" ref={wrapperRef}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
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
