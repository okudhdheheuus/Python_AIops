
"""API 限流 —— 基于Redis的固定窗口计数器 避免攻击者多次访问"""
import time

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

from ..config import settings
from ..core.logging import request_id_var
from .redis import get_redis


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    固定窗口限流中间件。
    每 IP 每个时间窗口内最多N次请求。超出返回 429 Too many Requests。
    Redis Key 格式：ratelimit:<IP>:<窗口起始时间戳>
    """

    async def dispatch(self,request:Request,call_next):
        if not settings.rate_limit_enabled:
            return await call_next(request)
        # 跳过健康检查和metrics端点
        if request.url.path.startswith("/health") or request.url.path == "/metrics":
            return await call_next(request)
        client_ip = request.client.host if request.client else "unknown" # 获取用户IP
        window_key = int(time.time() / settings.rate_limit_window_seconds) # 获取时间窗口
        redis_key = f"ratelimit:{client_ip}:{window_key}" # 生成唯一Key

        try:
            r = await get_redis()
            count = await r.incr(redis_key) # 原子操作，不使用字典，保证并发安全
            if count == 1:
                await r.expire(redis_key,settings.rate_limit_window_seconds)
            if count > settings.rate_limit_requests:
                raise HTTPException(
                    status_code = 429,
                    detail={
                        "error":"rate_limit_exceeded",
                        "message": f"每分钟最多 {settings.rate_limit_requests} 次请求",
                        "retry_after_seconds":settings.rate_limit_window_seconds,
                        "request_id":request_id_var.get(),
                    },
                )
        except HTTPException:
            raise
        except Exception:
            # Redis 不可用时降级 —— 不限流，保证服务可用
            pass
        return await call_next(request)







