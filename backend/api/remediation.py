import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import RemediationLog, RemediationPolicy, Server, User
from ..schemas import (
    RemediationLogOut,
    RemediationPolicyCreate,
    RemediationPolicyOut,
    RemediationPolicyUpdate,
)
from ..utils.security import get_current_active_user

router = APIRouter()


def _remediation_log_ownership_filter(stmt, current_user: User):
    """非 admin 用户只看自己服务器的修复日志"""
    if current_user.role != "admin":
        user_server_ids = select(Server.id).where(Server.owner_id == current_user.id)
        stmt = stmt.where(RemediationLog.server_id.in_(user_server_ids))
    return stmt


# ====修复策略 CRUD（仅管理员） =====
@router.get("/policies")
async def list_policies(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    stmt = select(RemediationPolicy).order_by(RemediationPolicy.created_at.desc())
    policies = (await db.execute(stmt)).scalars().all()
    return {"total":len(policies),"items":[RemediationPolicyOut.model_validate(p).model_dump() for p in policies]}

@router.post("/policies",status_code=201)
async def create_policy(
    body: RemediationPolicyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    policy = RemediationPolicy(
        name=body.name,description=body.description,
        match_labels=json.dumps(body.match_labels,ensure_ascii=False),
        repair_mode=body.repair_mode,
        command=body.command,
        requires_approval=body.requires_approval,
        timeout_seconds=body.timeout_seconds,enabled=body.enabled,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return RemediationPolicyOut.model_validate(policy).model_dump()

@router.get("/policies/{policy_id}")
async def get_policy(
    policy_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    policy = (await db.execute(select(RemediationPolicy).where(RemediationPolicy.id==policy_id))).scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404,detail="策略不存在")
    return RemediationPolicyOut.model_validate(policy).model_dump()
@router.put("/policies/{policy_id}")
async def update_policy(
    policy_id: str,
    body: RemediationPolicyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    policy = (await
    db.execute(select(RemediationPolicy).where(RemediationPolicy.id==policy_id))
    ).scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404,detail="策略不存在")
    data = body.model_dump(exclude_unset=True)
    if "match_labels" in data and data["match_labels"] is not None:
        data["match_labels"] = json.dumps(data["match_labels"],
        ensure_ascii=False)
    for field,value in data.items():
        setattr(policy,field,value)
    await db.commit()
    await db.refresh(policy)
    return RemediationPolicyOut.model_validate(policy).model_dump()

@router.delete("/policies/{policy_id}")
async def delete_policy(
    policy_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    policy = (await db.execute(select(RemediationPolicy).where(RemediationPolicy.id== policy_id))).scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404,detail="策略不存在")
    await db.delete(policy)
    await db.commit()
    return {"status": "deleted"}

@router.post("/policies/test-match")
async def test_match(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """测试告警会匹配哪些策略（仅管理员）"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    policies = (await
    db.execute(select(RemediationPolicy).where(RemediationPolicy.enabled==True))).scalars().all()
    matched = []
    for p in policies:
        try:
            labels=json.loads(p.match_labels)
        except (json.JSONDecodeError,TypeError):
            continue
        if all(body.get(k) == v for k,v in labels.items()):
            matched.append(RemediationPolicyOut.model_validate(p).model_dump())
    return {"matched_count":len(matched),"items":matched}
# ====修复日志=====
@router.get("/logs")
async def list_logs(
    db: AsyncSession = Depends(get_db),
    status: str | None = None,
    server_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
):
    stmt = _remediation_log_ownership_filter(select(RemediationLog), current_user)
    stmt = stmt.order_by(RemediationLog.created_at.desc())
    if status:
        stmt = stmt.where(RemediationLog.status==status)
    if server_id:
        stmt = stmt.where(RemediationLog.server_id==server_id)
    total = (await
        db.execute(select(func.count()).select_from(stmt.subquery()))

    ).scalar() or 0
    stmt = stmt.offset((page-1)*page_size).limit(page_size)
    logs=(await db.execute(stmt)).scalars().all()
    return {
        "total":total,
        "page": page,
        "page_size":page_size,
        "items":[RemediationLogOut.model_validate(l).model_dump() for l in logs]
    }
@router.get("/logs/{log_id}")
async def get_log(
    log_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    log = (await db.execute(select(RemediationLog).where(RemediationLog.id==log_id))).scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="日志不存在")
    if current_user.role != "admin" and log.server_id:
        owner_check = await db.execute(
            select(Server).where(Server.id == log.server_id, Server.owner_id == current_user.id)
        )
        if not owner_check.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="日志不存在")
    return RemediationLogOut.model_validate(log).model_dump()


