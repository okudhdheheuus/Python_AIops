from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Alert, Server, User, Workflow
from ..schemas import DashboardStats
from ..utils.security import get_current_active_user

router = APIRouter()

@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    is_admin = current_user.role == "admin"

    # 服务器数量（非 admin 只看自己的）
    server_q = select(func.count(Server.id))
    if not is_admin:
        server_q = server_q.where(Server.owner_id == current_user.id)
    server_count = (await db.execute(server_q)).scalar() or 0

    agent_count = 12  # 实际 Agent 类型数量

    # 工作流数量（非 admin 看模板+自己的）
    wf_q = select(func.count(Workflow.id))
    if not is_admin:
        wf_q = wf_q.where(
            (Workflow.is_template == True) | (Workflow.owner_id == current_user.id)
        )
    workflow_count = (await db.execute(wf_q)).scalar() or 0

    # 告警统计（非 admin 只看自己服务器的）
    alert_base = select(Alert)
    if not is_admin:
        user_server_ids = select(Server.id).where(Server.owner_id == current_user.id)
        alert_base = alert_base.where(
            (Alert.server_id == None) | (Alert.server_id.in_(user_server_ids))
        )
    total_alerts = (await db.execute(select(func.count()).select_from(alert_base.subquery()))).scalar() or 0
    firing_alerts = (await db.execute(
        select(func.count()).select_from(
            alert_base.where(Alert.status == "firing").subquery()
        )
    )).scalar() or 0

    return DashboardStats(
        servers=server_count,
        agents=agent_count,
        workflows=workflow_count,
        total_alerts=total_alerts,
        firing_alerts=firing_alerts
    )
