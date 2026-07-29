from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import KnowledgeBase, User
from ..services.knowledge_service import search_knowledge, seed_preset_knowledge
from ..utils.security import get_current_active_user

router = APIRouter()


@router.get("/search")
async def search(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """检索知识库"""
    items = await search_knowledge(q, limit)
    return {"total": len(items), "items": items}


@router.get("/entries")
async def list_entries(
    db: AsyncSession = Depends(get_db),
    category: str | None = None,
    tag: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
):
    """列出知识库条目"""
    stmt = select(KnowledgeBase).order_by(KnowledgeBase.created_at.desc())
    if category:
        stmt = stmt.where(KnowledgeBase.category == category)
    if tag:
        stmt = stmt.where(KnowledgeBase.tags.contains(tag))

    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    entries = (await db.execute(stmt)).scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": e.id,
                "title": e.title,
                "content": e.content[:200],
                "category": e.category,
                "tags": e.tags,
                "source": e.source,
                "enabled": e.enabled,
                "created_at": str(e.created_at) if e.created_at else None,
            }
            for e in entries
        ]
    }


@router.post("/seed", status_code=201)
async def seed_knowledge(
    current_user: User = Depends(get_current_active_user),
):
    """写入预设的22条运维知识（幂等）"""
    if current_user.role not in ["admin"]:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="仅管理员可执行")
    await seed_preset_knowledge()
    return {"status": "seeded", "count": 22}
