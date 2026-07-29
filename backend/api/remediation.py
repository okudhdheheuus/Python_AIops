import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from sqlalchemy import select,func
from ..models import RemediationPolicy,RemediationLog
from ..schemas import RemediationPolicyOut, RemediationPolicyCreate,\
    RemediationPolicyUpdate,RemediationLogOut

router = APIRouter()


# ====修复策略 CRUD =====
@router.get("/policies")
async def list_policies(db: AsyncSession = Depends(get_db)):
    stmt = select(RemediationPolicy).order_by(RemediationPolicy.created_at.desc())
    policies = (await db.execute(stmt)).scalars().all()
    return {"total":len(policies),"items":[RemediationPolicyOut.model_validate(p).model_dump() for p in policies]}

@router.post("/policies",status_code=201)
async def create_policy(body:RemediationPolicyCreate,db:AsyncSession=Depends(get_db)):
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
async def get_policy(policy_id:str,db:AsyncSession=Depends(get_db)):
    policy = (await db.execute(select(RemediationPolicy).where(RemediationPolicy.id==policy_id))).scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404,detail="策略不存在")
    return RemediationPolicyOut.model_validate(policy).model_dump()
@router.put("/policies/{policy_id}")
async def update_policy(policy_id:str,body:RemediationPolicyUpdate,db:AsyncSession=Depends(get_db)):
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
async def delete_policy(policy_id:str,db:AsyncSession=Depends(get_db)):
    policy = (await db.execute(select(RemediationPolicy).where(RemediationPolicy.id== policy_id))).scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404,detail="策略不存在")
    await db.delete(policy)
    await db.commit()
    return {"status": "deleted"}

@router.post("/policies/test-match")
async def test_match(body:dict,db: AsyncSession=Depends(get_db)):
    """测试告警会匹配哪些策略"""
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
    status: str = None,
    server_id: str = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    stmt = select(RemediationLog).order_by(RemediationLog.created_at.desc())
    if status:
        stmt = stmt.where(RemediationLog.status==status)
    if server_id:
        stmt = stmt.where(RemediationLog.server_id==server_id)
    total = (await
        db.execute(select(func.count()).select_from(stmt.subquery()))

    ).scalar()
    stmt = stmt.offset((page-1)*page_size).limit(page_size)
    logs=(await db.execute(stmt)).scalars().all()
    return {
        "total":total,
        "page": page,
        "page_size":page_size,
        "items":[RemediationLogOut.model_validate(l).model_dump() for l in logs]
    }
@router.get("/logs/{log_id}")
async def get_log(log_id:str,db:AsyncSession=Depends(get_db)):
    log = (await db.execute(select(RemediationLog).where(RemediationLog.id==log_id))).scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404,detail="日志不存在")
    return RemediationLogOut.model_validate(log).model_dump()


