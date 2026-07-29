"""健康检查端点 ——K8s Liveness/Readiness/Startup 探针"""
import time

from fastapi import APIRouter

from ..core.redis import check_redis_health
from ..database import check_db_health

router = APIRouter(tags=['health'])

# 记录应用启动时间(用于startup探针判断)
_start_time = time.time()

@router.get("/health/live")
async def liveness():
    """
    Liveness 探针——最简单，只要进程活着就返回200。
    K8s 会定期调用，失败次数超阈值就重启Pod
    """
    return {"status":"alive","uptime_seconds":int(time.time()-_start_time)}

@router.get("/health/ready")
async def readiness():
    """
    Readiness 探针 —— 检查所有外部依赖（DB+Redis）是否可用。
    任何一个不可用返回503，K8s会把该Pod从Service摘除，流量不再分配过来
    """
    db_ok = await check_db_health()
    redis_ok = await check_redis_health()

    healthy = db_ok and redis_ok
    status_code = 200 if healthy else 503

    return {
        "status":"ready" if healthy else "not_ready",
        "checks":{
            "database":"ok" if db_ok else "unavailable",
            "redis":"ok" if redis_ok else "unavailable",
        },
        "uptime_seconds":int(time.time() - _start_time),
    },status_code

@router.get("/health/startup")
async def startup():
    """
    Startup 探针 —— 启动后第一次成功返回后,K8s停止调用此探针,开始调用Liveness。
    用于保护启动较慢的容器（如需要建立DB连接池、加载模型等）。
    :return:
    """
    db_ok = await check_db_health()
    if not db_ok:
        return {"status":"starting","reason":"database is not ready"},503
    return {"status":"started","update_seconds":int(time.time() - _start_time)}


