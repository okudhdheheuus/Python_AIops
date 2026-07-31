from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import KnowledgeBase, User
from ..services.knowledge_service import (
    create_entry,
    delete_entry,
    rebuild_embedding_cache,
    search_knowledge,
    seed_preset_knowledge,
    update_entry,
)
from ..utils.security import get_current_active_user

router = APIRouter()


class KnowledgeCreate(BaseModel):
    title: str
    content: str
    category: str = ""
    tags: str = ""


class KnowledgeUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    category: str | None = None
    tags: str | None = None
    enabled: bool | None = None


@router.get("/search")
async def search(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    limit: int = Query(5, ge=1, le=20),
    current_user: User = Depends(get_current_active_user),
):
    """语义搜索知识库"""
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


@router.post("/entries", status_code=201)
async def create(
    body: KnowledgeCreate,
    current_user: User = Depends(get_current_active_user),
):
    """新增知识条目"""
    entry = await create_entry(
        title=body.title,
        content=body.content,
        category=body.category,
        tags=body.tags,
    )
    return entry


@router.put("/entries/{entry_id}")
async def update(
    entry_id: str,
    body: KnowledgeUpdate,
    current_user: User = Depends(get_current_active_user),
):
    """更新知识条目"""
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="无更新字段")
    entry = await update_entry(entry_id, **fields)
    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")
    return entry


@router.delete("/entries/{entry_id}")
async def delete(
    entry_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """删除知识条目"""
    ok = await delete_entry(entry_id)
    if not ok:
        raise HTTPException(status_code=404, detail="条目不存在")
    return {"status": "deleted"}


@router.get("/entries/{entry_id}")
async def get_entry(
    entry_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取单条知识详情"""
    entry = await db.get(KnowledgeBase, entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="条目不存在")
    return {
        "id": entry.id,
        "title": entry.title,
        "content": entry.content,
        "category": entry.category,
        "tags": entry.tags,
        "source": entry.source,
        "enabled": entry.enabled,
        "created_at": str(entry.created_at) if entry.created_at else None,
    }


@router.post("/rebuild-cache", status_code=200)
async def rebuild_cache(
    current_user: User = Depends(get_current_active_user),
):
    """手动重建 embedding 缓存"""
    if current_user.role not in ["admin"]:
        raise HTTPException(status_code=403, detail="仅管理员可执行")
    await rebuild_embedding_cache()
    return {"status": "ok"}


@router.post("/seed", status_code=201)
async def seed_knowledge(
    current_user: User = Depends(get_current_active_user),
):
    """写入预设的22条运维知识（幂等）"""
    if current_user.role not in ["admin"]:
        raise HTTPException(status_code=403, detail="仅管理员可执行")
    await seed_preset_knowledge()
    return {"status": "seeded", "count": 22}
