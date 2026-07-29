import json
import logging
import time

from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select
from .database import AsyncSessionLocal
from .models import Server,Alert,PatrolRecord
from .services.monitor import THRESHOLDS,RULES,check_server,process_alert
from .services.notification_service import send_notification
from .services.agent_executor import trigger_auto_remediation



logger = logging.getLogger("scheduler")
# 全局调度器实例
scheduler = AsyncIOScheduler()
# 巡检间隔
CHECK_INTERVAL = 300

async def patrol_job():
    """
    定时巡检：遍历启用服务器->采集指标->超阈值写告警->写巡检记录
    """
    logger.info("[巡检任务] 开始")
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Server).where(Server.enabled == True))
        servers = result.scalars().all()
        if not servers:
            logger.info("[巡检任务] 无启用的服务器，跳过")
            return
        from .services.agent_executor import AgentExecutor
        executor = AgentExecutor()
        for server in servers:
            instance = f"{server.host}:{server.port}"
            # 采集指标(复用AgentExecutor)
            monitor_result = await executor.execute(
                agent_type = "monitor",input_text="状态检查",
                server_id = server.id,
            )
            cpu_val = monitor_result.get("cpu",0)
            mem_val = monitor_result.get("memory",0)
            disk_val = monitor_result.get("disk",0)
            # 写入巡检记录
            patrol_status = "success"
            if cpu_val>THRESHOLDS["cpu"] or mem_val > THRESHOLDS["memory"] or disk_val>THRESHOLDS["disk"]:
                patrol_status = "warning"
            record = PatrolRecord(
                server_id = server.id,server_name=server.name,
                status=patrol_status,cpu_usage=cpu_val,memory_usage=mem_val,disk_usage=disk_val,
            )
            db.add(record)

            # 检查阈值 -> 生成告警
            for alertname_key,metric_key,label_cn in RULES:
                threshold = THRESHOLDS[metric_key]
                # 取出数据进行比较，评定级别
                value = {"cpu":cpu_val,"memory":mem_val,"disk":disk_val}[metric_key]
                if value <= threshold:
                    continue
                # 去重：同名警告+实例+已firing的不在重复创建
                existing = (
                    await db.execute(
                        select(Alert).where(
                            Alert.alert_name == alertname_key,
                            Alert.instance == instance,
                            Alert.status == "firing",
                        )
                    )
                ).scalar_one_or_none()
                if existing:
                    continue
                severity = "critical" if value > threshold*1.2 else "warning"
                alert = Alert(
                    alert_name = alertname_key,severity=severity,status="firing",
                    instance=instance,server_id=server.id,
                    summary =f"{label_cn}使用率{value:.1f}% 超过阈值 {threshold}%",
                    source="patrol",
                )
                db.add(alert)
                logger.warning(f"[巡检告警]{alertname_key} | {server.name}({instance}) | {value:.1f}% > {threshold}%")
                try:
                    await send_notification(
                        alert_name=alertname_key,
                        summary=f"{label_cn}使用率{value:.1f}% 超过阈值 {threshold}%",
                        severity=severity,
                        instance=instance,
                    )
                except Exception:
                    pass
                # 自动触发AI修复
                try:
                    await trigger_auto_remediation(
                        alert_id=alert.id,
                        alert_labels={"alertname": alertname_key, "severity": severity},
                        server_id=server.id,
                    )
                except Exception:
                    pass
        await db.commit()
    logger.info("[巡检任务] 结束")

async def start_scheduler():
    scheduler.add_job(patrol_job,IntervalTrigger(seconds=CHECK_INTERVAL),
        id="patrol_job",replace_existing=True)
    scheduler.start()
    logger.info(f"[调度器] 已启动，间隔 {CHECK_INTERVAL} 秒")


async def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[调度器] 已关闭")
