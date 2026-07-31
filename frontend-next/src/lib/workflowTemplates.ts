export interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  nodes: Array<Record<string, unknown>>;
  edges: Array<{ source: string; target: string }>;
}

export const WORKFLOW_TEMPLATES: WorkflowTemplate[] = [
  {
    id: "server-inspection",
    name: "服务器巡检",
    description: "指标采集 → 日志分析 → 自动生成巡检报告（串行链，演示上游输出串联）",
    nodes: [
      {
        id: "monitor-node",
        agent_type: "monitor",
        position: { x: 0, y: 0 },
        prompt: "采集服务器 CPU / 内存 / 磁盘使用率和负载情况",
        timeout: 60,
        max_retries: 2,
      },
      {
        id: "log-node",
        agent_type: "log_analyzer",
        position: { x: 340, y: 0 },
        prompt: "检查最近 2 小时系统日志中的错误和警告，找出异常事件",
        timeout: 60,
        max_retries: 2,
      },
      {
        id: "doc-node",
        agent_type: "doc_generator",
        position: { x: 680, y: 0 },
        prompt: "根据上游的指标和日志分析结果，生成一份完整的服务器巡检报告",
        timeout: 60,
        max_retries: 2,
      },
    ],
    edges: [
      { source: "monitor-node", target: "log-node" },
      { source: "log-node", target: "doc-node" },
    ],
  },
  {
    id: "diagnose-and-repair",
    name: "故障诊断与修复",
    description: "故障诊断 → 自动修复（需要在节点配置中选择目标服务器，演示条件分支）",
    nodes: [
      {
        id: "diag-node",
        agent_type: "diagnostic",
        position: { x: 0, y: 0 },
        prompt: "服务器响应缓慢，请排查 CPU / 内存 / 磁盘 / 网络瓶颈，找出根因",
        timeout: 60,
        max_retries: 2,
      },
      {
        id: "repair-node",
        agent_type: "remediation",
        position: { x: 360, y: 0 },
        prompt: "根据诊断结果执行最安全的修复操作，并验证修复效果",
        condition: "contains:建议",
        timeout: 90,
        max_retries: 2,
      },
    ],
    edges: [{ source: "diag-node", target: "repair-node" }],
  },
  {
    id: "alert-analysis",
    name: "告警分析与交接报告",
    description: "分析当前活跃告警 → 生成值班交接报告（纯 LLM 节点，无需 SSH）",
    nodes: [
      {
        id: "alert-node",
        agent_type: "alert_analyzer",
        position: { x: 0, y: 0 },
        prompt: "分析当前最严重的活跃告警，评估紧急程度（P0-P4）并给出处理建议",
        timeout: 60,
        max_retries: 2,
      },
      {
        id: "report-node",
        agent_type: "doc_generator",
        position: { x: 360, y: 0 },
        prompt: "将告警分析结果整理成一份值班交接报告",
        timeout: 60,
        max_retries: 2,
      },
    ],
    edges: [{ source: "alert-node", target: "report-node" }],
  },
];
