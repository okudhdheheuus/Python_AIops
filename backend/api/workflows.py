import json
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import AsyncSessionLocal, get_db
from ..models import User, UserLLMConfig, Workflow, WorkflowExecution
from ..services.agent_executor import AgentExecutor
from ..services.workflow_engine import WorkflowEngine
from ..utils.security import get_current_active_user

router = APIRouter()


def _workflow_ownership_filter(stmt, current_user: User):
    """每个用户看模板 + 自己的工作流"""
    stmt = stmt.where(
        (Workflow.is_template == True) | (Workflow.owner_id == current_user.id)
    )
    return stmt

# ===== 工作流CRUD =====
@router.get("")
async def list_workflows(
    db: AsyncSession = Depends(get_db),
    is_template: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
):
    """列出工作流"""
    stmt = select(Workflow).order_by(Workflow.created_at.desc())
    stmt = _workflow_ownership_filter(stmt, current_user)
    if is_template is not None:
        stmt = stmt.where(Workflow.is_template == is_template)

    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    workflows = (await db.execute(stmt)).scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": wf.id,
                "name": wf.name,
                "description": wf.description,
                "nodes": json.loads(wf.nodes) if wf.nodes else [],
                "edges": json.loads(wf.edges) if wf.edges else [],
                "is_template": wf.is_template,
                "owner_id": wf.owner_id,
                "created_at": str(wf.created_at) if wf.created_at else None,
                "updated_at": str(wf.updated_at) if wf.updated_at else None,
            }
            for wf in workflows
        ]
    }


@router.post("", status_code=201)
async def create_workflow(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """创建工作流"""
    is_template = body.get("is_template", False)
    wf = Workflow(
        name=body["name"],
        description=body.get("description"),
        nodes=json.dumps(body.get("nodes", []), ensure_ascii=False),
        edges=json.dumps(body.get("edges", []), ensure_ascii=False),
        is_template=is_template,
        owner_id=None if is_template else current_user.id,
    )
    db.add(wf)
    await db.commit()
    await db.refresh(wf)
    return {"id": wf.id, "name": wf.name, "status": "created"}


@router.get("/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """获取工作流详情"""
    wf = await _check_workflow_access(workflow_id, db, current_user)
    return {
        "id": wf.id,
        "name": wf.name,
        "description": wf.description,
        "nodes": json.loads(wf.nodes) if wf.nodes else [],
        "edges": json.loads(wf.edges) if wf.edges else [],
        "is_template": wf.is_template,
        "owner_id": wf.owner_id,
        "created_at": str(wf.created_at) if wf.created_at else None,
    }


@router.put("/{workflow_id}")
async def update_workflow(
    workflow_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """更新工作流"""
    wf = await _check_workflow_access(workflow_id, db, current_user)

    for field in ("name", "description", "is_template"):
        if field in body:
            setattr(wf, field, body[field])
    if "nodes" in body:
        wf.nodes = json.dumps(body["nodes"], ensure_ascii=False)
    if "edges" in body:
        wf.edges = json.dumps(body["edges"], ensure_ascii=False)

    await db.commit()
    return {"status": "updated"}


@router.delete("/{workflow_id}")
async def delete_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """删除工作流"""
    wf = await _check_workflow_access(workflow_id, db, current_user)
    await db.delete(wf)
    await db.commit()
    return {"status": "deleted"}


async def _check_workflow_access(workflow_id: str, db: AsyncSession, current_user: User) -> Workflow:
    """获取工作流并校验访问权限"""
    wf = await db.get(Workflow, workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="工作流不存在")
    if wf.is_template:
        return wf  # 模板所有人可见
    if wf.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="工作流不存在")
    return wf


# ===== 工作流执行 =====
@router.post("/{workflow_id}/run")
async def run_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    body: dict | None = None,
    current_user: User = Depends(get_current_active_user),
):
    """执行工作流"""
    wf = await _check_workflow_access(workflow_id, db, current_user)

    # 加载当前用户的 LLM 配置，节点执行走用户的 Key（未配置则回退全局）
    user_llm_config = None
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(UserLLMConfig).where(UserLLMConfig.user_id == current_user.id)
        )
        user_llm_config = result.scalar_one_or_none()

    workflow_def = {
        "nodes": json.loads(wf.nodes) if isinstance(wf.nodes, str) else wf.nodes,
        "edges": json.loads(wf.edges) if isinstance(wf.edges, str) else wf.edges,
    }

    initial_input = (body or {}).get("input", "Start workflow")
    node_timeout = (body or {}).get("node_timeout", 60)
    max_retries = (body or {}).get("max_retries", 2)

    executor = AgentExecutor(user_llm_config=user_llm_config)
    engine = WorkflowEngine(executor)

    start = time.perf_counter()
    result = await engine.run_workflow(workflow_def, initial_input, node_timeout, max_retries)
    duration_ms = int((time.perf_counter() - start) * 1000)

    # 持久化执行历史
    exec_record = WorkflowExecution(
        workflow_id=workflow_id,
        workflow_name=wf.name,
        status=result["status"],
        node_count=result["node_count"],
        completed_count=result["completed_count"],
        failed_count=result["failed_count"],
        results=json.dumps(result["results"], ensure_ascii=False),
        duration_ms=duration_ms,
    )
    db.add(exec_record)
    await db.commit()

    result["execution_id"] = exec_record.id
    result["duration_ms"] = duration_ms
    return result


# ===== 执行历史 =====
@router.get("/{workflow_id}/executions")
async def list_executions(
    workflow_id: str,
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
):
    """查看工作流执行历史"""
    stmt = (
        select(WorkflowExecution)
        .where(WorkflowExecution.workflow_id == workflow_id)
        .order_by(WorkflowExecution.started_at.desc())
    )
    total = await db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    executions = (await db.execute(stmt)).scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": e.id,
                "workflow_name": e.workflow_name,
                "status": e.status,
                "node_count": e.node_count,
                "completed_count": e.completed_count,
                "failed_count": e.failed_count,
                "duration_ms": e.duration_ms,
                "error_message": e.error_message,
                "started_at": str(e.started_at) if e.started_at else None,
                "finished_at": str(e.finished_at) if e.finished_at else None,
            }
            for e in executions
        ]
    }
