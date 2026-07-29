from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from ..database import get_db
from ..models import AuditLog, User
from ..utils.security import get_current_active_user

router = APIRouter()


@router.get("/logs")
async def list_audit_logs(
    db: AsyncSession = Depends(get_db),
    username: str = None,
    action: str = None,
    resource_type: str = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_active_user),
):
    """查询审计日志，支持按用户/操作/资源类型筛选"""
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
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
