"""审计日志服务 —— 记录所有关键操作到 audit_logs 表"""

from ..database import AsyncSessionLocal
from ..models import AuditLog


async def log_audit(
    username: str,
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: str | None = None,
    ip_address: str | None = None,
):
    """异步写入审计日志（不阻塞主流程）"""
    try:
        async with AsyncSessionLocal() as db:
            log_entry = AuditLog(
                username=username,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                detail=detail,
                ip_address=ip_address,
            )
            db.add(log_entry)
            await db.commit()
    except Exception:
        pass  # 审计失败不影响主流程
