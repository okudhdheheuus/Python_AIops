from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import PatrolRecord, User
from ..schedulers import patrol_job
from ..schemas import PatrolRecord as PatrolRecordSchema
from ..utils.security import get_current_active_user

router = APIRouter()


@router.post("/run", status_code=200)
async def trigger_patrol(
    current_user: User = Depends(get_current_active_user),
):
    """手动触发一次完整巡检（含指标采集 + 日志事件检测）"""
    try:
        await patrol_job()
        return {"status": "completed"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@router.get("/records")
async def list_patrol_records(
    db: AsyncSession = Depends(get_db),
    server_id: str | None=None,
    status: str | None=None,
    days: int = Query(7,ge=1,le=90),
    page: int = Query(1,ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
):
    """查询巡检查，最近7天默认"""
    stmt = select(PatrolRecord).order_by(PatrolRecord.checked_at.desc())
    since = datetime.now(tz=timezone.utc)-timedelta(days=days)
    stmt = stmt.where(PatrolRecord.checked_at>=since)
    if server_id:
        stmt = stmt.where(PatrolRecord.server_id == server_id)
    if status:
        stmt = stmt.where(PatrolRecord.status == status)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar()
    stmt = stmt.offset((page-1)*page_size).limit(page_size)
    records = (await db.execute(stmt)).scalars().all()
    return {
        "total":total or 0,
        "page": page,
        "page_size":page_size,
        "items":[PatrolRecordSchema.model_validate(r).model_dump() for r in records]
    }

@router.get("/summary")
async def patrol_summary(
    db:AsyncSession = Depends(get_db),
    days: int= Query(7,ge=1,le=90),
    current_user: User = Depends(get_current_active_user),
):
    """巡检统计摘要：总次数、成功率、资源使用率趋势"""
    since = datetime.now(tz=timezone.utc)-timedelta(days=days)
    # 总巡检次数
    total = await db.scalar(
                    select(func.count()).
                    where(PatrolRecord.checked_at>=since)
                ) or 0
    warning = await db.scalar(
        select(func.count()).
        where(PatrolRecord.status == "warning",
        PatrolRecord.checked_at>=since)
    ) or 0
    error = await db.scalar(
        select(func.count()).
        where(PatrolRecord.status == "error",
            PatrolRecord.checked_at>=since)
    ) or 0
    # 平均CPU/内存/磁盘使用率
    avg_row = await db.execute(
        select(
            func.avg(PatrolRecord.cpu_usage),
            func.avg(PatrolRecord.memory_usage),
            func.avg(PatrolRecord.disk_usage),
        ).where(PatrolRecord.checked_at>=since)
    )
    avg_cpu, avg_memory, avg_disk = avg_row.one()
    return {
        "total": total,
        "success": total - warning - error,
        "warning": warning,
        "error": error,
        "avg_cpu": round(avg_cpu or 0, 1),
        "avg_memory": round(avg_memory or 0, 1),
        "avg_disk": round(avg_disk or 0, 1),
    }

