import redis.asyncio as aioredis

from ..config import settings

# 全局连接池(懒初始化)
_pool: aioredis.ConnectionPool | None = None
_client: aioredis.Redis | None = None

async def get_redis() -> aioredis.Redis:
    """获取Redis客户端（单例）"""
    global _pool,_client
    if _client is None:
        _pool = aioredis.ConnectionPool.from_url(
            settings.get_redis_url(),
            max_connections = 50,
            decode_responses = True,
            socket_keepalive = True,
            socket_connect_timeout = 2,
            retry_on_timeout = True
        )
        _client = aioredis.Redis(connection_pool=_pool)
    return _client

async def check_redis_health() -> bool:
    """Redis健康检查"""
    try:
        r=await get_redis()
        return await r.ping() is True
    except Exception:
        return False

async def close_redis():
    """关闭Redis连接池(应用shutdown时调用)"""
    global _pool,_client
    if _client:
        await _client.close()
        _client = None
    if _pool:
        await _pool.disconnect()
        _pool = None

