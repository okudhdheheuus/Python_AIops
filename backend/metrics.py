from contextlib import asynccontextmanager
import time

from prometheus_client import Counter,Gauge,Histogram,generate_latest,REGISTRY
http_requests_total = Counter(
    "itops_http_requests_total",
    "Total HTTP requests",
    ["method","endpoint","status_code"],
)

http_request_duration_seconds = Histogram(
    "itops_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

http_requests_in_progress=Gauge(
    "itops_http_requests_in_progress",
    "Number of HTTP requests currently being processed",
)

# ======业务指标========
servers_total = Gauge(
    "itops_servers_total",
    "Total number of managed servers",
)

alerts_firing_total = Gauge(
    "itops_alerts_firing_total",
    "Number of currently firing alerts",
)

patrol_runs_total = Counter(
    "itops_patrol_runs_total",
    "Total number of patrol runs executed",
)

# ========数据库指标=========
db_connections_active = Gauge(
    "itops_db_connections_active",
    "Number of active database connections",
)

# ======AI/LLM指标========
llm_requests_total = Counter(
    "itops_llm_requests_total",
    "Total LLM API calls",
    ["provider","status"],
)

llm_request_duration_seconds = Histogram(
    "itops_llm_request_duration_seconds",
    "LLM API call latency in seconds",
    ["provider"],
    buckets=[0.5,1.0,2.0,5.0,10.0,20.0,30.0,60.0]
)
llm_tokens_total = Counter(
    "itops_llm_tokens_total",
    "Total tokens consumed",
    ["provider","type"], # type:prompt | completion
)

def get_metrics() -> str:
    """生成Prometheus格式的指标文本"""
    return generate_latest(REGISTRY).decode("utf-8")

@asynccontextmanager
async def track_request(method:str,endpoint:str):
    http_requests_in_progress.inc()
    start = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter()-start
        http_requests_in_progress.dec()
        # 注意：status_code在yield之后由调用方设置，这里先不记录status
        http_request_duration_seconds.labels(method=method,endpoint=endpoint).observe(duration)
