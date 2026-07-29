"""运维级FastAPI应用入口"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response

from .api import (
    agents,
    alerts,
    audit,
    auth,
    chat,
    dashboard,
    health,
    knowledge,
    notifications,
    patrol,
    remediation,
    servers,
    workflows,
)
from .config import settings
from .core.logging import setup_logging
from .core.middleware import RequestIDMiddleware, global_exception_handler
from .core.rate_limit import RateLimitMiddleware
from .core.redis import close_redis, get_redis
from .database import Base, engine, ensure_sqlite_columns
from .metrics import get_metrics, track_request
from .schedulers import shutdown_scheduler, start_scheduler

logger = logging.getLogger("itops")
# =================应用生命周期=============
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动 / 关闭时初始化逻辑"""
    # -----Startup-----
    setup_logging(settings.log_level, settings.log_format)
    logger.info(
        f"Starting {settings.app_name} v{settings.app_version}",
        extra={"environment": settings.environment}
    )
    # 创建数据库表 （开发模式：生产用Alembic迁移）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await ensure_sqlite_columns()
    logger.info("Database tables ensured")
    # 预热Redis连接
    try:
        r = await get_redis()
        await r.ping()
        logger.info("Redis connection established")
    except Exception:
        logger.warning("Redis unavailable - rate limiting and caching disabled")
    # 启动定时巡检调度器
    await start_scheduler()
    logger.info("Scheduler started")

    # 初始化预设知识库（幂等）
    try:
        from .services.knowledge_service import seed_preset_knowledge
        await seed_preset_knowledge()
        logger.info("Knowledge base seeded")
    except Exception:
        logger.warning("Knowledge base seeding skipped")

    yield
    # -----Shutdown-----
    await shutdown_scheduler()
    await close_redis()
    await engine.dispose()
    logger.info(f"{settings.app_name} shut down")


# ----FastAPI应用--------
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url=None,
    redirect_slashes=False,
)

# =============中间件注册(注意顺序)======
# 1.CORS ——最先处理，避免跨域预检失败
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(", "),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)
#2、请求ID —— 为每个请求注入唯一标识
app.add_middleware(RequestIDMiddleware)
#3、限流 —— Redis不可用时自动降级
app.add_middleware(RateLimitMiddleware)

# 4、全局异常处理
app.add_exception_handler(Exception,global_exception_handler)

# ==============Prometheus Metrics中间件==============
@app.middleware("http")
async def prometheus_middleware(request:Request,call_next):
    """记录每个HTTP请求的指标(计数、延迟、状态码)"""
    # 跳过metrics端点自身，避免自循环
    if request.url.path == "/metrics":
        return await call_next(request)
    async with track_request(request.method,request.url.path):
        response: Response = await call_next(request)
    from .metrics import http_requests_total
    http_requests_total.labels(
        method=request.method,
        endpoint=request.url.path,
        status_code=str(response.status_code),
    ).inc()
    return response

# ================路由注册================
# 健康检查（无前缀,K8s探针直接用 /health/*访问）
app.include_router(health.router)
# Prometheus 指标暴露
@app.get("/metrics",response_class=PlainTextResponse)
async def metrics():
    """Prometheus指标端点——被Prometheus Server定期抓取"""
    return get_metrics()

# API 路由
app.include_router(auth.router,prefix="/api/auth",tags=["认证"])
app.include_router(servers.router,prefix="/api",tags=["服务器管理"])
app.include_router(agents.router,prefix="/api/agents",tags=["AI Agent"])
app.include_router(workflows.router,prefix="/api/workflows",tags=["工作流"])
app.include_router(dashboard.router,prefix="/api/dashboard",tags=["仪表盘"])
app.include_router(alerts.router, prefix="/api", tags=["告警中心"])
app.include_router(patrol.router, prefix="/api/patrol", tags=["巡检记录"])
app.include_router(remediation.router,prefix="/api/remediation",tags=["修复管理"])
app.include_router(chat.router,prefix="/api/chat",tags=["AI聊天"])
app.include_router(audit.router, prefix="/api/audit", tags=["审计日志"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["知识库"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["通知管理"])

@app.get("/health")
async def health_legacy():
    """兼容旧版健康检查"""
    return {"status":"ok","environment":settings.environment}



