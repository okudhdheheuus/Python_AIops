import enum
import uuid  # 生成唯一随机串

from sqlalchemy import (  # 定义字段类型
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
)
from sqlalchemy.sql import func  # 调用当前时间生成函数

from .database import Base  # 继承数据表基类


def gen_uuid(): # 用于表唯一ID
    return str(uuid.uuid4())
class User(Base):
    __tablename__= "users" # 对应表名
    id = Column(String(36),primary_key=True,default=gen_uuid) # 这里传入gen_uuid函数，用于生成唯一ID
    username = Column(String(50),unique=True,nullable=False)
    email = Column(String(100),nullable=True)
    hashed_password = Column(String(200),nullable=False)
    role = Column(String(20),default="viewer")
    is_active = Column(Boolean,default=True)
    created_at = Column(DateTime(timezone=True),server_default=func.now())
    updated_at = Column(DateTime(timezone=True),onupdate=func.now())
class Server(Base):
    __tablename__ = "servers"
    id = Column(String(36),primary_key=True,default=gen_uuid)
    name = Column(String(100),nullable=False)
    host = Column(String(100),nullable=False)
    port = Column(Integer,default=22)
    username = Column(String(50),nullable=False)

    password = Column(String(200),nullable=True)
    use_ssh_key = Column(Boolean,default=False)
    private_key = Column(Text,nullable=True)
    description = Column(Text,nullable=True)
    tags = Column(String(200),nullable=True)
    enabled = Column(Boolean,default=True)
    owner_id = Column(String(36), nullable=True)  # 多租户隔离，NULL=管理员
    created_at = Column(DateTime(timezone=True),server_default=func.now())
    updated_at = Column(DateTime(timezone=True),onupdate=func.now())

class Workflow(Base):
    __tablename__ = "workflows"
    id = Column(String(36),primary_key=True,default=gen_uuid)
    name = Column(String(100),nullable=False)
    description = Column(Text,nullable=True)
    nodes = Column(Text,nullable=False) # JSON 字符串 存储节点列表
    edges = Column(Text,nullable=False) # JSON 字符串, 存储边
    is_template = Column(Boolean,default=False)
    owner_id = Column(String(36), nullable=True)  # 多租户隔离，模板为 NULL
    created_at = Column(DateTime(timezone=True),server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class WorkflowExecution(Base):
    """工作流执行历史"""
    __tablename__ = "workflow_executions"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    workflow_id = Column(String(36), nullable=False)
    workflow_name = Column(String(100), nullable=True)
    status = Column(String(20), default="running")
    node_count = Column(Integer, default=0)
    completed_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    results = Column(Text, nullable=True)  # JSON
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)


class AlertStatus(str,enum.Enum):
    firing = "firing"
    acknowledged = "acknowledged"
    resolved = "resolved"

class AlertSeverity(str, enum.Enum):
    critical = "critical"
    warning = "warning"
    info = "info"

class Alert(Base):
    """告警记录 - 持久化存储，替代内存中的alert_store"""
    __tablename__ = "alerts"
    id = Column(String(36),primary_key=True,default=gen_uuid)
    alert_name = Column(String(200),nullable=False)
    severity = Column(String(20),default="warning")
    status = Column(String(20),default="firing") # firing/acknowledged/resolved
    instance = Column(String(100),default="")
    server_id = Column(String(36),nullable=True) # 关联server表
    summary = Column(Text,default="")
    source = Column(String(20),default="webhook")  # webhook/patrol
    started_at = Column(DateTime(timezone=True),server_default=func.now())
    resolved_at = Column(DateTime(timezone=True),nullable=True)
    created_at = Column(DateTime(timezone=True),server_default=func.now())

class PatrolStatus(str,enum.Enum):
    success="success"
    warning = "warning"
    error = "error"

class PatrolRecord(Base):
    """巡检记录-每次巡检的结果"""
    __tablename__ = "patrol_records"
    id = Column(String(36),primary_key=True,default=gen_uuid)
    server_id = Column(String(36),nullable=False)  # 关联server.id
    server_name = Column(String(100),default="")
    status = Column(String(20),default="success")  # success/warning/error
    cpu_usage=Column(Float,default=0.0)
    memory_usage=Column(Float,default=0.0)
    disk_usage=Column(Float,default=0.0)
    details = Column(Text,nullable=True)  # 原始输出Json
    checked_at = Column(DateTime(timezone=True),server_default=func.now())

class RemediationLog(Base):
    """修复操作日志-审计追踪"""
    __tablename__ = "remediation_logs"
    id = Column(String(36),primary_key=True,default=gen_uuid)
    alert_id = Column(String(36),nullable=True) # 关联alerts.id
    server_id = Column(String(36),nullable=True) # 关联servers.id
    action = Column(String(500),default="") # 执行的命令
    command = Column(Text,nullable=True)  # 实际执行的shell命令
    triggered_by = Column(String(20),default="auto") # auto/manual
    status = Column(String(20),default="pending") # pending/runing/success/failed/timeout/skipped
    input_text = Column(Text,nullable=True) # 传入的提示词
    output = Column(Text,nullable=True) # 命令输出(stdout)
    error_output = Column(Text,nullable=True) # 错误输出(stderr)
    exit_code = Column(Integer,nullable=True)
    duration_ms = Column(Integer,nullable=True) # 执行时间(毫秒)
    created_at = Column(DateTime(timezone=True),server_default=func.now())

class RemediationPolicy(Base):
    """修复策略配置——文件"""
    __tablename__ = "remediation_policies"
    id = Column(String(36),primary_key=True,default=gen_uuid)
    name = Column(String(100),nullable=False)
    description = Column(Text,nullable=True)
    match_labels = Column(Text,nullable=True) # JSON 字符串,匹配标签 {"severity":"critical","alertname":"HighCPU"}
    repair_mode = Column(String(20),default="ai")  # static=固定命令 / ai=AI生成修复指令
    command = Column(Text,nullable=True)  # repair_mode=static 时使用的固定命令
    requires_approval = Column(Boolean,default=True)  # AI修复是否需要人工审批
    timeout_seconds = Column(Integer,default=30)
    enabled = Column(Boolean,default=True)
    created_at = Column(DateTime(timezone=True),server_default=func.now())
    updated_at = Column(DateTime(timezone=True),onupdate=func.now())

class SilenceRule(Base):
    """告警静默规则"""
    __tablename__ = "silence_rules"
    id = Column(String(36),primary_key=True,default=gen_uuid)
    name = Column(String(36),nullable=False)
    match_labels = Column(Text,nullable=True) # Json
    duration_minutes = Column(Integer,default=60)
    comment = Column(Text,nullable=True)
    enabled = Column(Boolean,default=True)
    created_by = Column(String(50),nullable=True)
    created_at = Column(DateTime(timezone=True),server_default=func.now())


class AuditLog(Base):
    """操作审计日志 —— 记录所有关键操作"""
    __tablename__ = "audit_logs"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    username = Column(String(50), nullable=False)
    action = Column(String(200), nullable=False)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(36), nullable=True)
    detail = Column(Text, nullable=True)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class KnowledgeBase(Base):
    """知识库条目 —— 用于RAG检索增强生成"""
    __tablename__ = "knowledge_base"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(50), nullable=True)
    tags = Column(String(200), nullable=True)
    source = Column(String(100), nullable=True)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class NotificationChannel(Base):
    """通知渠道配置"""
    __tablename__ = "notification_channels"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    name = Column(String(100), nullable=False)
    channel_type = Column(String(20), nullable=False)
    webhook_url = Column(String(500), nullable=False)
    sign_secret = Column(String(200), nullable=True)  # 钉钉/飞书加签密钥
    enabled = Column(Boolean, default=True)
    owner_id = Column(String(36), nullable=True)  # 多租户隔离，NULL=管理员
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UserLLMConfig(Base):
    """用户 LLM 配置 —— 留空字段回退到全局设置"""
    __tablename__ = "user_llm_configs"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    user_id = Column(String(36), nullable=False, unique=True)
    provider = Column(String(20), default="deepseek")
    api_key = Column(String(200), nullable=True)
    api_base = Column(String(300), nullable=True)
    model = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class UserAgentConfig(Base):
    """用户 Agent 偏好"""
    __tablename__ = "user_agent_configs"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    user_id = Column(String(36), nullable=False, unique=True)
    active_agents = Column(Text, nullable=True)  # JSON array
    default_agent = Column(String(50), default="generic")
    preferences = Column(Text, nullable=True)  # JSON object
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())