import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


# 创建用户请求模型
class UserCreate(BaseModel):
    username: str
    email:EmailStr | None = None
    password: str
    role: str = "viewer"
# 查询返回用户信息模型
class UserOut(BaseModel):
    id: str
    username: str
    email: str | None
    role: str
    is_active: bool
    model_config = ConfigDict(from_attributes=True)
# 登陆返回Token模型（整合access_token和用户信息）
# 定义一个Token类，继承自BaseModel
class Token(BaseModel):
    # 定义access_token属性，类型为字符串，表示访问令牌
    access_token: str
    # 定义token_type属性，类型为字符串，默认值为"bearer"，表示令牌类型
    token_type: str = "bearer"
    model_config = ConfigDict(from_attributes=True)
# 登陆表单请求模型
class LoginRequest(BaseModel):
    username: str
    password: str

# 定义服务器模型基类
class ServerBase(BaseModel):
    name: str
    host: str
    port: int=22
    username: str
    password: str | None = None
    use_ssh_key: bool = False
    private_key: str | None = None
    description: str | None = None
    tags: str | None = None
    enabled: bool = True

# 定义服务器模型创建类
class ServerCreate(ServerBase):
    pass
# 定义服务器模型更新类：
class ServerUpdate(BaseModel):
    name: str | None = None
    host: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = None
    use_ssh_key: bool | None = None
    private_key: str | None = None
    description: str | None = None
    tags: str | None = None
    enabled: bool | None = None
# 定义服务器模型输出类：
# 定义服务器模型输出类，继承自ServerBase
class ServerOut(ServerBase):
    # 服务器唯一标识ID
    id: str
    # 服务器创建时间
    created_at: datetime
    # 服务器最后更新时间
    updated_at: datetime | None
    # 配置ORM模式，支持从ORM对象直接转换
    model_config = ConfigDict(from_attributes=True)

# 定义agent模型
class AgentExecuteRequest(BaseModel):
    agent_type: str = "generic"
    input_text: str
    server_id: str | None = None
    server_msg: str | None = None

# 仪表盘统计
class DashboardStats(BaseModel):
    servers: int
    agents: int
    workflows: int
    total_alerts: int = 0
    firing_alerts: int = 0
# 告警推送模型(适配Prometheus)
class AlertPayload(BaseModel):
    status: str = "firing"
    labels: dict={}
    annotations: dict = {}
    startsAt: str | None = None
class WebhookPayload(BaseModel):
    alerts: list[AlertPayload] = []

# 告警模型
class AlertOut(BaseModel):
    id:str
    alert_name: str
    severity: str
    status: str
    instance: str
    server_id: str | None = None
    summary: str
    source: str
    started_at: datetime | None = None
    resolved_at: datetime | None = None
    created_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)

class AlertUpdate(BaseModel):
    status: str # acknowledged, resolved

# 巡检记录
class PatrolRecord(BaseModel):
    id: str
    server_id: str
    server_name: str
    status: str
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    details: str | None = None
    checked_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)

# 修复日志
class RemediationLogOut(BaseModel):
    id: str
    alert_id: str | None = None
    server_id: str | None = None
    action: str
    command: str | None = None
    triggered_by:str
    status: str
    input_text: str | None = None
    output: str | None = None
    error_output: str | None = None
    exit_code: int | None = None
    duration_ms: int | None = None
    created_at: datetime | None=None
    model_config = ConfigDict(from_attributes=True)

# ---修复策略----
class RemediationPolicyCreate(BaseModel):
    name: str
    description: str | None = None
    match_labels: dict = {}
    repair_mode: str = "ai"  # static | ai
    command: str | None = None  # repair_mode=static 时使用
    requires_approval: bool = True
    timeout_seconds: int = 30
    enabled: bool =True

class RemediationPolicyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    match_labels: dict | None = None
    repair_mode: str | None = None
    command: str | None = None
    requires_approval: bool | None = None
    timeout_seconds: int | None = None
    enabled: bool | None = None

class RemediationPolicyOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    match_labels: dict[str, Any]
    repair_mode: str = "ai"
    command: str | None = None
    requires_approval: bool = True
    timeout_seconds: int
    enabled: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)

    @field_validator("match_labels", mode="before")
    @classmethod
    def parse_match_labels(cls, value):
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (TypeError, json.JSONDecodeError):
                return {}
        return value








