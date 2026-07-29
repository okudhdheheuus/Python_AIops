"""全局中间件 —— 请求 ID 注入 + 统一错误响应 + 请求日志"""
import logging
import time
import uuid

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .logging import request_id_var

logger = logging.getLogger("itops")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    为每个请求注入唯一 request_id，并在响应头中返回。
    前端可以在报错时带上此 ID，方便后端日志中定位问题。
    request_id 同时写入 ContextVar，后续所有日志自动携带。
    """

    async def dispatch(self, request: Request, call_next):
        # 优先从请求头读取（用于链路追踪跨服务传递），否则生成新的
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        request_id_var.set(req_id)

        start = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000

        response.headers["X-Request-ID"] = req_id
        response.headers["X-Response-Time-Ms"] = f"{duration_ms:.1f}"

        # 结构化请求日志
        logger.info(
            f"{request.method} {request.url.path}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 1),
            },
        )

        return response


async def global_exception_handler(request: Request, exc: Exception):
    """全局异常捕获 —— 避免 500 暴露堆栈到客户端"""
    logger.exception(f"Unhandled exception on {request.method} {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "服务器内部错误，请联系管理员",
            "request_id": request_id_var.get(),
        },
    )
