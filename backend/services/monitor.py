import logging
import asyncio
import httpx
from datetime import datetime
from sqlalchemy import select
from ..database import AsyncSessionLocal
from ..models import Server
from .agent_executor import AgentExecutor
logger = logging.getLogger("monitor")

# 告警阈值（按序要调整）
THRESHOLDS = {
    "cpu":90.0,
    "memory":90.0,
    "disk":85.0,
}
# 告警类型
RULES = [
    ("HighCPU","cpu","CPU"),
    ("HighMemory","memory","内存"),
    ("HighDisk","disk","磁盘")
]
# 采集信息命令
COLLECT_CMD = "df -h && free -m && top -bn1 | head -5"
# 巡检间隔(秒)，默认5分钟
CHECK_INTERVAL = 300


def parse_metrics(stdout:str)->dict:
    """
    解析巡检脚本的输出，格式为：
    CPU:85.2
    MEM:60.5
    DISK:72
    """
    metrics = {}
    for line in stdout.strip().split("\n"):
        line = line.strip()
        if ":" in line:
            key,val = line.split(":",1)
            try:
                metrics[key] = float(val)
            except ValueError:
                pass
    return metrics
# -----单台检查----
async def check_server(server)->list:
    """复用AgentExecutor采集指标，只做解析和阈值判断"""
    from .agent_executor import AgentExecutor
    alerts = []
    instance = f"{server.host}:{server.port}"
    # 直接调AgentExecutor采集
    executor = AgentExecutor()
    result = await executor.execute(
        agent_type="monitor",
        input_text="状态检查", # 暂时用这个占位
        server_id = server.id,
    )
    if result.get("status") != "success":
        return alerts
    for alertname,key,label in RULES:
        value = result.get(key,0)
        alerts.append({
            "alertname": alertname,
            "severity": "critical" if value >  THRESHOLDS[key] else "warning",
            "instance": instance,
            "server_name": server.name,
            "server_id": server.id,
            "summary": f"{label}使用率{value}%超过阈值{THRESHOLDS[key]}%",
        })
    return alerts

# -----告警推送(走统一Webhook)------
async def process_alert(alert_info:dict):
    """超阈值时POST到/api/alerts/webhook，不重复写存储逻辑"""
    payload={
        "alerts": [{
            "status":"firing",
            "labels":{
                "alertname": alert_info["alertname"],
                "severity": alert_info["severity"],
                "instance": alert_info["instance"],
            },
            "annotations":{"summary":alert_info["summary"]},
        }]
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            await client.post(
                "http://localhost:8000/api/alerts/webhook",
                json=payload,
            )
    except Exception as e:
        logger.error(f"推送告警失败：{e}")

# ---单次巡检-----
async def run_check():
    """查询所有启用的服务器,逐一检查"""
    async with AsyncSessionLocal() as db:
        stmt = select(Server).where(Server.enabled == True)
        result = await db.execute(stmt)
        servers = result.scalars().all()
    if not servers:
        return
    logger.info(f"[巡检]开始，共{len(servers)}台服务器")
    for server in servers:
        server_alerts = await check_server(server)
        for alert_info in server_alerts:
            logger.info(
                f"[告警]{alert_info['alertname']} |"
                f"{server.name}({alert_info['instance']}) |"
                f"{alert_info['summary']}"
            )
            await process_alert(alert_info)
    logger.info(f"[巡检]结束")



