import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Alert, Server, SilenceRule, User, UserLLMConfig
from ..schemas import AlertOut, AlertUpdate, WebhookPayload
from ..services.agent_executor import AgentExecutor, trigger_auto_remediation
from ..services.notification_service import (
    send_notification,
    send_recovery_notification,
)
from ..utils.security import get_current_active_user

router = APIRouter()


@router.post("/alerts/webhook")
async def receive_alert(payload: WebhookPayload,db:AsyncSession = Depends(get_db)):
    """接收 Prometheus webhook 告警，持久化到数据库"""
    if not payload.alerts:
        return {"status":"ignored","reason":"no alerts"}

    results = []
    for alert_data in payload.alerts:
        # 提取信息
        severity = alert_data.labels.get("severity","warning")
        alert_name = alert_data.labels.get("alertname","Unknown")
        instance = alert_data.labels.get("instance","")
        summary = alert_data.annotations.get("summary",alert_data.annotations.get("description",""))
        # 去重
        existing = (
            await db.execute(
                select(Alert).where(
                    Alert.alert_name == alert_name,
                    Alert.instance == instance,
                    Alert.status == "firing",
                )
            )
        ).scalar_one_or_none()
        if existing: # 如果已经存在对应报警记录，则根据报警信息更新非关键字段
            existing.summary = summary
            existing.started_at = datetime.now(tz=timezone.utc)
            await db.flush()
            results.append({"alert_id":existing.id,"duplicate":True,"server_id":existing.server_id})
            continue

        # 没有对应记录，就先查找对应服务器
        server_id = None
        owner_id = None
        if ":" in instance:
            ip,port_str = instance.split(":",1)
            try:
                port = int(port_str)
                server_obj = (
                    await db.execute(
                        select(Server).where(Server.host==ip,Server.port==port)
                    )
                ).scalar_one_or_none()
                if server_obj:
                    server_id = server_obj.id
                    owner_id = server_obj.owner_id
            except ValueError:
                pass
        alert = Alert(
            alert_name=alert_name,severity=severity,status="firing",
            instance=instance,server_id=server_id,summary=summary,
            source = "webhook"
        )
        db.add(alert)
        await db.flush()
        results.append({"alert_id":alert.id,"server_id":server_id,"owner_id":owner_id})
    await db.commit()

    # 异步发送通知 + 自动修复（仅对新建告警，忽略异常避免影响主流程）
    for i, alert_data in enumerate(payload.alerts):
        if i < len(results) and not results[i].get("duplicate"):
            try:
                await send_notification(
                    alert_name=alert_data.labels.get("alertname", "Unknown"),
                    summary=alert_data.annotations.get("summary", ""),
                    severity=alert_data.labels.get("severity", "warning"),
                    instance=alert_data.labels.get("instance", ""),
                    owner_id=results[i].get("owner_id"),
                )
            except Exception:
                pass
            # 自动触发AI修复
            try:
                await trigger_auto_remediation(
                    alert_id=results[i]["alert_id"],
                    alert_labels=alert_data.labels,
                    server_id=results[i].get("server_id"),
                )
            except Exception:
                pass

    return {"status":"success","results":results}

def _alert_ownership_filter(stmt, current_user: User):
    """每个用户只看自己服务器的告警"""
    user_server_ids = select(Server.id).where(Server.owner_id == current_user.id)
    stmt = stmt.where(
        (Alert.server_id == None) | (Alert.server_id.in_(user_server_ids))
    )
    return stmt

@router.get("/alerts")
async def list_alerts(
    db: AsyncSession = Depends(get_db),
    severity: str | None = None,
    status: str | None = None,
    page: int = Query(1,ge=1),
    page_size: int = Query(20,ge=1,le=100),
    current_user: User = Depends(get_current_active_user),
):
    """查询告警列表，支持分页和筛选"""
    stmt = select(Alert).order_by(Alert.created_at.desc())
    stmt = _alert_ownership_filter(stmt, current_user)
    if severity:
        stmt = stmt.where(Alert.severity==severity)
    if status:
        stmt = stmt.where(Alert.status==status)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = await db.scalar(count_stmt) or 0
    stmt = stmt.offset((page-1)* page_size).limit(page_size)
    alerts = (await db.execute(stmt)).scalars().all()
    return {
        "total":total,
        "page":page,
        "page_size":page_size,
        "items":[AlertOut.model_validate(a).model_dump() for a in alerts]
    }


@router.get("/alerts/stats")
async def alert_stats(db:AsyncSession = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    """告警统计（各级别数量）"""
    base = _alert_ownership_filter(select(Alert), current_user)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar()
    critical = (await db.execute(
        select(func.count()).select_from(
            _alert_ownership_filter(
                select(Alert).where(Alert.severity=="critical",Alert.status=="firing"),
                current_user
            ).subquery()
        )
    )).scalar()
    warning = (await db.execute(
        select(func.count()).select_from(
            _alert_ownership_filter(
                select(Alert).where(Alert.severity=="warning",Alert.status=="firing"),
                current_user
            ).subquery()
        )
    )).scalar()
    return {"total" : total or 0,"critical_firing":critical or 0,"warning_firing": warning or 0}

@router.put("/alerts/{alert_id}")
async def update_alert(
    alert_id: str,
    body: AlertUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """确认/解决告警"""
    alert = (await db.execute(select(Alert).where(Alert.id == alert_id))).scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")
    # 每个用户只能操作自己服务器的告警
    if alert.server_id:
        owner_check = await db.execute(
            select(Server).where(Server.id == alert.server_id, Server.owner_id == current_user.id)
        )
        if not owner_check.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="告警不存在")
    alert.status = body.status
    if body.status == "resolved":
        alert.resolved_at = datetime.now(tz=timezone.utc)
    await db.commit()

    # 告警恢复时发送通知
    if body.status == "resolved":
        try:
            await send_recovery_notification(
                alert_name=alert.alert_name,
                instance=alert.instance,
                resolved_at=alert.resolved_at.strftime("%Y-%m-%d %H:%M:%S") if alert.resolved_at else "",
            )
        except Exception:
            pass

    return {"status":"success"}

@router.post("/alerts/silence")
async def create_silence_rule(
    body:dict,
    db:AsyncSession = Depends(get_db),
    current_user: User=Depends(get_current_active_user),
):
    """创建静默规则"""
    rule = SilenceRule(
        name = body["name"],
        match_labels=json.dumps(body.get("match_labels",{})),
        duration_minutes=body.get("duration_minute",60),
        comment = body.get("comment"),
        created_by = current_user.username,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return {"id":rule.id,"name":rule.name}
@router.get("/alerts/silence")
async def list_silence_rules(
    db:AsyncSession=Depends(get_db),
    current_user:User=Depends(get_current_active_user),
):
    """获取静默规则（每个用户只看自己创建的）"""
    stmt = select(SilenceRule).order_by(SilenceRule.created_at.desc())
    stmt = stmt.where(SilenceRule.created_by == current_user.username)
    result = await db.execute(stmt)
    rules = result.scalars().all()
    return {
        "total":len(rules),
        "items": [
            {
                "id":r.id,
                "name":r.name,
                "match_labels":json.loads(r.match_labels) if r.match_labels else {},
                "duration_minutes":r.duration_minutes,
                "comment":r.comment,
                "enabled":r.enabled,
                "created_by":r.created_by,
            }
            for r in rules
        ]
    }
@router.delete("/alerts/silence/{rule_id}")
async def delete_silence_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """删除静默规则"""
    rule = await db.get(SilenceRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    if rule.created_by != current_user.username:
        raise HTTPException(status_code=404, detail="规则不存在")
    await db.delete(rule)
    await db.commit()
    return {"status":"deleted"}

@router.post("/alerts/{alert_id}/remediate")
async def remediate_alert_manual(
    alert_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """手动触发AI告警修复"""
    alert = (await db.execute(select(Alert).where(Alert.id == alert_id))).scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")
    # 每个用户只能修复自己服务器的告警
    if alert.server_id:
        owner_check = await db.execute(
            select(Server).where(Server.id == alert.server_id, Server.owner_id == current_user.id)
        )
        if not owner_check.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="告警不存在")
    if alert.status != "firing":
        raise HTTPException(status_code=400, detail="只能修复活跃(firing)告警")

    user_llm_config = (
        await db.execute(
            select(UserLLMConfig).where(UserLLMConfig.user_id == current_user.id)
        )
    ).scalar_one_or_none()
    executor = AgentExecutor(user_llm_config=user_llm_config)
    result = await executor.remediate_alert(
        alert_id=alert_id,
        server_id=alert.server_id,
        triggered_by="manual",
    )

    if result.get("status") == "success":
        alert.status = "resolved"
        alert.resolved_at = datetime.now(tz=timezone.utc)
        await db.commit()

    return result

