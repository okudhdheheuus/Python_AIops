from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..database import get_db
from ..models import Server, Workflow, User, Alert
from ..schemas import DashboardStats
from ..utils.security import get_current_active_user

router = APIRouter()

@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # 服务器数量
    result = await db.execute(select(func.count(Server.id)))
    server_count = result.scalar() or 0

    # Agent 类型数量（当前代码中硬编码了 generic 和 diagnostic）
    agent_count = 2

    # 工作流数量（作为"任务"的代理指标）
    result = await db.execute(select(func.count(Workflow.id)))
    workflow_count = result.scalar() or 0

    # 告警统计
    total_alerts = await db.scalar(select(func.count(Alert.id))) or 0
    firing_alerts = await db.scalar(
        select(func.count(Alert.id)).where(Alert.status=="firing")) or 0
    return DashboardStats(
        servers=server_count,
        agents=agent_count,
        workflows=workflow_count,
        total_alerts=total_alerts,
        firing_alerts=firing_alerts
    )
