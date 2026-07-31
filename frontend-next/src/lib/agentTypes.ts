export interface AgentTypeDef {
  type: string;
  name: string;
  description: string;
  color: string;
  icon: string;
  needsServer: boolean;
}

export const AGENT_TYPES: AgentTypeDef[] = [
  { type: "generic",            name: "通用助手",   description: "自动识别意图并路由",     color: "#6b7280", icon: "Bot",           needsServer: false },
  { type: "monitor",            name: "指标采集",   description: "采集CPU/内存/磁盘/网络指标", color: "#3b82f6", icon: "Cpu",            needsServer: true  },
  { type: "diagnostic",         name: "故障诊断",   description: "深挖根因，检查瓶颈和异常",   color: "#f59e0b", icon: "Stethoscope",   needsServer: true  },
  { type: "remediation",        name: "自动修复",   description: "执行修复操作，重启服务等",   color: "#ef4444", icon: "Wrench",        needsServer: true  },
  { type: "alert_analyzer",     name: "告警分析",   description: "评估告警严重程度和优先级",   color: "#ec4899", icon: "Bell",          needsServer: false },
  { type: "log_analyzer",       name: "日志分析",   description: "拉取并分析系统日志",        color: "#8b5cf6", icon: "ScrollText",    needsServer: true  },
  { type: "change_executor",    name: "变更执行",   description: "生成变更计划和回滚方案",     color: "#10b981", icon: "GitBranch",     needsServer: false },
  { type: "doc_generator",      name: "文档生成",   description: "生成运维文档和报告",        color: "#14b8a6", icon: "FileText",      needsServer: false },
  { type: "compliance_checker", name: "合规检查",   description: "安全基线审计和合规评分",     color: "#f97316", icon: "ShieldCheck",   needsServer: true  },
  { type: "shell_command",     name: "命令执行",   description: "直接在服务器上执行Shell命令",   color: "#06b6d4", icon: "Terminal",      needsServer: true  },
  { type: "health_check",      name: "健康检查",   description: "HTTP GET检查服务是否正常",      color: "#22c55e", icon: "Globe",         needsServer: false },
  { type: "webhook",           name: "通知推送",   description: "将结果POST到Webhook/机器人",    color: "#a855f7", icon: "Send",          needsServer: false },
];

export function getAgentDef(type: string): AgentTypeDef | undefined {
  return AGENT_TYPES.find(a => a.type === type);
}

export interface ApiWorkflowNode {
  id: string;
  agent_type: string;
  position?: { x: number; y: number };
  prompt?: string;
  server_id?: string;
  timeout?: number;
  max_retries?: number;
  condition?: string;
  config?: Record<string, unknown>;
}

export interface ApiWorkflowEdge {
  source: string;
  target: string;
}

export type AgentNodeData = {
  agent_type: string;
  prompt: string;
  server_id: string | null;
  timeout: number;
  max_retries: number;
  condition: string;
  config: Record<string, unknown>;
  run_status?: string;
} & { [key: string]: unknown };
