export interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  nodes: Array<Record<string, unknown>>;
  edges: Array<{ source: string; target: string }>;
}

export const WORKFLOW_TEMPLATES: WorkflowTemplate[] = [
  {
    id: "health-monitor",
    name: "服务健康监控",
    description: "HTTP健康检查 → 结果推送到Webhook（不需SSH、不需AI Key）",
    nodes: [
      {
        id: "health-node",
        agent_type: "health_check",
        position: { x: 0, y: 0 },
        prompt: "https://www.baidu.com",
        timeout: 30,
        max_retries: 1,
      },
      {
        id: "notify-node",
        agent_type: "webhook",
        position: { x: 360, y: 0 },
        prompt: "https://your-webhook-url.example",
        timeout: 15,
        max_retries: 1,
      },
    ],
    edges: [{ source: "health-node", target: "notify-node" }],
  },
  {
    id: "disk-patrol",
    name: "磁盘巡检告警",
    description: "SSH查看磁盘 → 发送告警（需要服务器SSH，不需AI Key）",
    nodes: [
      {
        id: "disk-node",
        agent_type: "shell_command",
        position: { x: 0, y: 0 },
        prompt: "echo '磁盘使用情况:'; df -h / | awk 'NR==2{print \"  使用率: \"$5\", 已用: \"$3\", 总量: \"$2}'",
        timeout: 30,
        max_retries: 1,
        condition: "",
      },
      {
        id: "alert-node",
        agent_type: "webhook",
        position: { x: 360, y: 0 },
        prompt: "https://your-webhook-url.example",
        timeout: 15,
        max_retries: 1,
      },
    ],
    edges: [{ source: "disk-node", target: "alert-node" }],
  },
  {
    id: "log-scan",
    name: "日志错误扫描",
    description: "SSH抓取错误日志 → AI分析 → 报告推送（需SSH + AI Key）",
    nodes: [
      {
        id: "grep-node",
        agent_type: "shell_command",
        position: { x: 0, y: 0 },
        prompt: "grep -i 'error\|failed\|fatal' /var/log/syslog 2>/dev/null | tail -30 || echo '无系统日志'",
        timeout: 30,
        max_retries: 1,
      },
      {
        id: "analyze-node",
        agent_type: "log_analyzer",
        position: { x: 360, y: 0 },
        prompt: "分析上游命令输出中的错误日志，找出最严重的问题并给出处理建议",
        timeout: 120,
        max_retries: 2,
      },
      {
        id: "report-node",
        agent_type: "webhook",
        position: { x: 720, y: 0 },
        prompt: "https://your-webhook-url.example",
        timeout: 15,
        max_retries: 1,
      },
    ],
    edges: [
      { source: "grep-node", target: "analyze-node" },
      { source: "analyze-node", target: "report-node" },
    ],
  },
  {
    id: "full-inspection",
    name: "服务器全量巡检",
    description: "指标采集 → AI分析 → 自动生成巡检报告（需SSH + AI Key）",
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
];
