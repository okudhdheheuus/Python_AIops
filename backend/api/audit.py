from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import AuditLog, Server, User
from ..utils.security import get_current_active_user

router = APIRouter()


def _audit_ownership_filter(stmt, current_user: User):
    """每个用户只看自己服务器的审计日志"""
    user_server_ids = select(Server.id).where(Server.owner_id == current_user.id)
    stmt = stmt.where(
        AuditLog.resource_type == "server",
        AuditLog.resource_id.in_(user_server_ids),
    )
    return stmt


@router.get("/logs")
async def list_audit_logs(
    db: AsyncSession = Depends(get_db),
    username: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_active_user),
):
    """查询审计日志（非管理员只看自己服务器的日志）"""
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    stmt = _audit_ownership_filter(stmt, current_user)
    if username:
        stmt = stmt.where(AuditLog.username == username)
    if action:
        stmt = stmt.where(AuditLog.action.contains(action))
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)

    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    logs = (await db.execute(stmt)).scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": log.id,
                "username": log.username,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "detail": log.detail,
                "ip_address": log.ip_address,
                "created_at": str(log.created_at) if log.created_at else None,
            }
            for log in logs
        ]
    }
