
# 结构化日志-JSON格式。携带request_id链路追踪
import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone

# 上下文变量：跨函数传递request_id,无需传参
request_id_var: ContextVar[str] = ContextVar("request_id",default="")
user_var: ContextVar[str] = ContextVar("username",default="")

class JsonFormatter(logging.Formatter):
    """将日志格式化为JSON行"""
    def format(self,record:logging.LogRecord) -> str:
        log_entry = {
            "timestamp":datetime.now(timezone.utc).isoformat(),
            "level":record.levelname,
            "logger":record.name,
            "message":record.getMessage(),
            "service":"itops-backend",
            "request_id":request_id_var.get(),
            "username":user_var.get(),
            "module":record.module,
            "line":record.lineno,
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)

def setup_logging(level:str="INFO",fmt:str="json"):
    """初始化全局日志配置(在main.py lifespan startup中调用)"""
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging,level.upper(),logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    if fmt == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            )
        )
    root.addHandler(handler)
    # 抑制过于啰嗦的第三方库日志
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("redis").setLevel(logging.WARNING)

    return logging.getLogger("itops")

