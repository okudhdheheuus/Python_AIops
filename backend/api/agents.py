from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..models import User, Server
from ..schemas import AgentExecuteRequest
from ..utils.security import get_current_active_user
from ..services.agent_executor import AgentExecutor
from sqlalchemy import select

router = APIRouter()

SUPPORTED_AGENTS = [
    {"type": "generic", "name": "通用助手", "description": "通用IT运维AI助手，自动识别意图并路由到合适的专用Agent"},
    {"type": "monitor", "name": "指标采集", "description": "[只读] 远程采集硬件指标：CPU温度/使用率、内存、磁盘、网络、负载等"},
    {"type": "diagnostic", "name": "故障诊断", "description": "[只读] 根据故障现象深挖根因：检查瓶颈、分析日志、追踪异常进程"},
    {"type": "remediation", "name": "自动修复", "description": "[可写] 执行修复操作：重启服务、关闭进程、清理资源、变更配置"},
    {"type": "alert_analyzer", "name": "告警分析", "description": "评估告警严重程度与优先级，结合活跃告警关联分析"},
    {"type": "log_analyzer", "name": "日志分析", "description": "[只读] 拉取并过滤系统日志：错误、警告、安全事件、异常模式"},
    {"type": "change_executor", "name": "变更执行", "description": "生成变更计划、预检步骤和回滚方案（不直接执行）"},
    {"type": "doc_generator", "name": "文档生成", "description": "根据需求和服务器信息生成运维文档和报告"},
    {"type": "compliance_checker", "name": "合规检查", "description": "[只读] 安全基线审计：SSH配置、防火墙、密码策略、权限、端口"},
]


@router.get("")
async def list_agents():
    """列出所有可用的Agent类型"""
    return {"agents": SUPPORTED_AGENTS}


@router.post("/execute")
async def execute_agent(
    req: AgentExecuteRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """执行指定的Agent"""
    executor = AgentExecutor()

    # 如果指定了server_msg(instance格式)，自动查找server_id
    server_id = req.server_id
    if not server_id and req.server_msg:
        parts = req.server_msg.split(":")
        if len(parts) == 2:
            ip, port_str = parts
            try:
                port = int(port_str)
                result = await db.execute(
                    select(Server).where(Server.host == ip, Server.port == port)
                )
                server = result.scalar_one_or_none()
                if server:
                    server_id = server.id
            except ValueError:
                pass

    result = await executor.execute(
        agent_type=req.agent_type,
        input_text=req.input_text,
        server_id=server_id,
        server_msg=req.server_msg,
    )

    return result
