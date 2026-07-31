import asyncio
import logging
import re

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from .database import AsyncSessionLocal
from .models import Alert, PatrolRecord, Server
from .services.agent_executor import trigger_auto_remediation
from .services.monitor import RULES, THRESHOLDS
from .services.notification_service import send_notification
from .services.ssh_pool import pool

logger = logging.getLogger("scheduler")
# 全局调度器实例
scheduler = AsyncIOScheduler()
# 巡检间隔
CHECK_INTERVAL = 300

# 日志事件检测规则：(匹配正则, 告警名称, 严重级别, 摘要模板)
LOG_EVENT_RULES = [
    (r"oom.?killer|out of memory|invoked oom-killer", "OOMKiller", "critical", "OOM Killer 被触发"),
    (r"killed process (\S+)", "ProcessKilled", "critical", "进程被 OOM Killer 杀死: {match}"),
    (r"segfault at", "Segfault", "warning", "检测到段错误 (Segfault)"),
    (r"hung_task|blocked for more than", "HungTask", "warning", "检测到任务挂起 (hung task)"),
    (r"i/o error|ext4.*error|read-only", "IOError", "critical", "磁盘 I/O 错误或文件系统异常"),
    (r"out of memory|memory cgroup out of", "MemoryExhausted", "critical", "内存耗尽 (Out of Memory)"),
    (r"failed command:.*write|ata.*error", "DiskError", "warning", "磁盘控制器或写入错误"),
    (r"tcp:.*overflow|possible syn flooding", "NetworkFlood", "warning", "网络栈异常 (SYN flood/overflow)"),
]


async def _run_log_patrol(server, db) -> int:
    """在服务器上检查 dmesg，匹配事件规则并创建告警。返回创建的告警数。"""
    if not server.password and not server.use_ssh_key:
        return 0

    try:
        cmd = "dmesg --level=err,warn 2>/dev/null | tail -20"
        async with pool.get_connection(
            host=server.host, port=server.port,
            username=server.username,
            password=server.password if not server.use_ssh_key else None,
            private_key=server.private_key if server.use_ssh_key else None,
        ) as conn:
            result = await asyncio.wait_for(conn.run(cmd, check=False, timeout=10), timeout=15)
            output = (result.stdout or "").strip()
    except Exception as e:
        logger.warning(f"[巡检] 日志检查SSH失败 {server.host}:{server.port}: {e}")
        return 0

    if not output:
        return 0

    instance = f"{server.host}:{server.port}"
    created = 0
    for pattern, alert_name, severity, summary_tpl in LOG_EVENT_RULES:
        matches = re.findall(pattern, output, re.IGNORECASE)
        if not matches:
            continue
        # 去重：同名告警 + 同实例 + firing 则不重复创建
        existing = (
            await db.execute(
                select(Alert).where(
                    Alert.alert_name == alert_name,
                    Alert.instance == instance,
                    Alert.status == "firing",
                )
            )
        ).scalar_one_or_none()
        if existing:
            continue
        # 提取匹配内容
        match_str = matches[0] if isinstance(matches[0], str) else (
            matches[0][0] if isinstance(matches[0], tuple) else str(matches[0])
        )[:80]
        summary = summary_tpl.format(match=match_str)
        alert = Alert(
            alert_name=alert_name, severity=severity, status="firing",
            instance=instance, server_id=server.id,
            summary=summary, source="log_patrol",
        )
        db.add(alert)
        created += 1
        logger.warning(f"[日志巡检告警] {alert_name} | {server.name}({instance}) | {summary}")

    return created

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

            # 日志事件巡检（OOM/段错误/磁盘错误等，不依赖阈值）
            try:
                log_alerts = await _run_log_patrol(server, db)
                if log_alerts > 0:
                    logger.info(f"[巡检] {server.name} 日志巡检发现 {log_alerts} 条事件")
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
