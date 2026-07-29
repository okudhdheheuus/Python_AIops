import time
from contextlib import asynccontextmanager
from typing import Dict

import asyncssh


class SSHConnectionPool:
    "SSH连接池：复用连接,支持并发巡检和修复"
    def __init__(self,max_size: int=30,idle_timeout: int = 300):
        self.pool: Dict[str,dict] = {}
        self.max_size = max_size
        self.idle_timeout = idle_timeout # 5分钟无活动自动关闭
    def _key(self,host:str,port:int,username:str)->str:
        return f"{host}:{port}:{username}"

    @asynccontextmanager
    async def get_connection(self,host:str,port:int,username:str,password:str=None,private_key: str=None):
        key = self._key(host,port,username)

        # 1. 尝试从池中获取
        if key in self.pool:
            conn_info = self.pool[key]
            elapsed = time.time() - conn_info["last_used"]
            if elapsed < self.idle_timeout:
                conn_info["last_used"] = time.time()
                yield conn_info["conn"]
                return
            else:
                # 连接已过期，清理
                try:
                    conn_info["conn"].close()
                except Exception:
                    pass
                del self.pool[key]
        # 2、尝试创建连接
        conn_kwargs = {
            "host": host,
            "port": port,
            "username": username,
            "known_hosts": None, # 这里不是生产环境，直接跳过验证
            "connect_timeout": 10
        }
        if password:
            conn_kwargs["password"] = password
        if private_key:
            conn_kwargs["client_keys"] = [private_key]
        conn =await asyncssh.connect(**conn_kwargs)
        self.pool[key] = {"conn":conn,"last_used":time.time()}

        # 3、池子满了，踢掉无用连接
        if len(self.pool) > self.max_size:
            # 自定义排序顺序，取时间最久远的那个连接
            oldest = min(self.pool.items(),key=lambda x:x[1]["last_used"])
            oldest[1]["conn"].close()
            del self.pool[oldest[0]]
        yield conn
    def close_all(self):
        for info in self.pool.values():
            info["conn"].close()
        self.pool.clear()
pool = SSHConnectionPool()