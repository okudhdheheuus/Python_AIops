// ===== 服务器 =====
export interface Server {
  id: string;
  name: string;
  host: string;
  port: number;
  username: string;
  tags?: string;
  enabled: boolean;
  created_at: string;
}

// ===== 告警 =====
export interface Alert {
  id: string;
  alert_name: string;
  severity: "critical" | "warning" | "info";
  status: "firing" | "acknowledged" | "resolved";
  instance: string;
  summary: string;
  created_at: string;
}

// ===== 巡检 =====
export interface PatrolRecord {
  id: string;
  server_name: string;
  status: "success" | "warning" | "error";
  cpu_usage: number;
  memory_usage: number;
  disk_usage: number;
  checked_at: string;
}

// ===== 聊天 =====
export interface ChatSession {
  session_id: string;
  title: string;
  message_count: number;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}