"""知识库服务 —— 基于 sentence-transformers 的语义 RAG"""

import logging

import numpy as np
from sqlalchemy import select

from ..database import AsyncSessionLocal
from ..models import KnowledgeBase

logger = logging.getLogger("knowledge")

# 懒加载的 embedding 模型实例
_embedding_model = None
# 内存向量缓存: {entry_id: np.ndarray}
_embedding_cache: dict[str, np.ndarray] = {}

PRESET_KNOWLEDGE = [
    {"title": "服务器CPU使用率过高排查", "category": "故障排查", "tags": "CPU,性能",
     "content": "当服务器CPU使用率超过90%时，应按以下步骤排查：1. 使用top/htop查看占用CPU最高的进程；2. 检查是否有死循环或异常进程；3. 查看应用日志是否有异常；4. 考虑是否需要扩容或优化代码。"},
    {"title": "服务器内存不足处理", "category": "故障排查", "tags": "内存,OOM",
     "content": "内存使用率超过90%时：1. free -m 查看内存使用情况；2. ps aux --sort=-%mem 查看占用内存最多的进程；3. 检查是否有内存泄漏；4. 清理缓存 sync && echo 3 > /proc/sys/vm/drop_caches；5. 考虑增加swap或物理内存。"},
    {"title": "磁盘空间不足处理", "category": "故障排查", "tags": "磁盘,清理",
     "content": "磁盘使用率超过85%时：1. df -h 查看各分区使用情况；2. du -sh /* 定位大目录；3. 清理日志文件 find /var/log -name '*.log' -mtime +30 -delete；4. 清理Docker镜像 docker system prune -a；5. 清理临时文件。"},
    {"title": "Nginx服务故障排查", "category": "服务管理", "tags": "Nginx,Web服务",
     "content": "Nginx故障排查步骤：1. nginx -t 检查配置文件语法；2. systemctl status nginx 查看服务状态；3. tail -f /var/log/nginx/error.log 查看错误日志；4. netstat -tlnp 检查端口是否被占用；5. 检查防火墙规则是否放行80/443端口。"},
    {"title": "MySQL数据库连接数过多", "category": "数据库", "tags": "MySQL,连接池",
     "content": "MySQL连接数过多处理：1. SHOW PROCESSLIST 查看当前连接；2. SHOW VARIABLES LIKE 'max_connections' 查看最大连接数；3. 检查应用连接池配置是否合理；4. 优化慢查询；5. 考虑读写分离或增加从库。"},
    {"title": "Redis内存溢出处理", "category": "数据库", "tags": "Redis,内存",
     "content": "Redis内存溢出处理：1. INFO memory 查看内存使用情况；2. 配置maxmemory和淘汰策略maxmemory-policy；3. 使用redis-cli --bigkeys查找大key；4. 设置过期时间；5. 考虑集群分片。"},
    {"title": "Docker容器异常重启", "category": "容器", "tags": "Docker,容器",
     "content": "Docker容器频繁重启排查：1. docker logs --tail 100 container_name 查看日志；2. docker inspect container_name 查看容器配置；3. 检查宿主机资源是否充足；4. 检查健康检查配置是否合理；5. 检查restart policy设置。"},
    {"title": "Kubernetes Pod CrashLoopBackOff", "category": "容器编排", "tags": "K8s,Pod",
     "content": "Pod CrashLoopBackOff处理：1. kubectl describe pod pod_name 查看事件；2. kubectl logs pod_name --previous 查看上一次容器日志；3. 检查镜像是否正确；4. 检查资源限制是否过小；5. 检查启动命令和探针配置。"},
    {"title": "SSL/TLS证书过期处理", "category": "安全", "tags": "SSL,证书",
     "content": "SSL证书过期处理：1. openssl x509 -in cert.pem -noout -dates 查看证书有效期；2. 使用Let's Encrypt免费证书；3. 配置certbot自动续期；4. 更新Nginx/Apache配置；5. 重启Web服务加载新证书。"},
    {"title": "服务器时间同步问题", "category": "系统管理", "tags": "NTP,时间",
     "content": "时间不同步会导致日志混乱、证书验证失败等问题：1. timedatectl status 查看时间状态；2. 配置NTP服务 systemctl enable --now chronyd；3. 强制同步 ntpdate ntp.aliyun.com；4. 检查时区设置是否正确。"},
    {"title": "SSH暴力破解防护", "category": "安全", "tags": "SSH,安全",
     "content": "SSH安全加固：1. 修改默认端口22；2. 禁止root直接登录 PermitRootLogin no；3. 使用密钥认证禁用密码登录；4. 安装fail2ban自动封禁暴力破解IP；5. 配置防火墙白名单限制SSH访问来源。"},
    {"title": "系统负载过高排查", "category": "故障排查", "tags": "负载,性能",
     "content": "系统负载(Load Average)持续高于CPU核心数时：1. uptime查看负载值；2. top查看CPU和IO等待；3. iostat -x 1查看磁盘IO；4. vmstat 1查看系统整体状态；5. 判断是CPU密集型还是IO密集型问题。"},
    {"title": "日志文件管理最佳实践", "category": "运维管理", "tags": "日志,logrotate",
     "content": "日志管理实践：1. 配置logrotate按天/大小轮转；2. 设置日志保留天数避免磁盘满；3. 使用集中式日志系统(ELK/Loki)；4. 关键日志实时监控告警；5. 定期清理过期日志文件。"},
    {"title": "防火墙iptables常用规则", "category": "安全", "tags": "防火墙,iptables",
     "content": "iptables常用操作：1. iptables -L -n -v 查看当前规则；2. 开放端口 iptables -A INPUT -p tcp --dport 80 -j ACCEPT；3. 保存规则 iptables-save > /etc/iptables/rules.v4；4. 封禁IP iptables -A INPUT -s IP -j DROP。"},
    {"title": "Linux用户和权限管理", "category": "系统管理", "tags": "用户,权限",
     "content": "用户管理要点：1. useradd/adduser创建用户；2. usermod修改用户组；3. chmod/chown管理文件和目录权限；4. sudo权限最小化原则；5. 定期审计/etc/passwd和/etc/shadow；6. 禁用不必要的系统账户。"},
    {"title": "服务自动启动配置", "category": "系统管理", "tags": "systemd,自启动",
     "content": "systemd服务管理：1. systemctl enable service_name 设置开机自启；2. 编写.service单元文件；3. Restart=on-failure配置自动重启；4. journalctl -u service_name 查看服务日志；5. systemctl daemon-reload 重载配置。"},
    {"title": "网络连通性排查", "category": "网络", "tags": "网络,ping,telnet",
     "content": "网络问题排查流程：1. ping测试基础连通性；2. telnet/curl测试端口是否开放；3. traceroute追踪路由路径；4. nslookup/dig检查DNS解析；5. tcpdump抓包分析；6. 检查防火墙和路由表。"},
    {"title": "定期备份策略", "category": "运维管理", "tags": "备份,容灾",
     "content": "备份策略建议：1. 数据库每日全量备份+增量binlog；2. 配置文件使用Git版本控制；3. 备份文件异地存储或对象存储；4. 定期验证备份可恢复性；5. 备份保留周期至少30天；6. 关键数据实时同步到备库。"},
    {"title": "性能基准测试方法", "category": "性能", "tags": "压测,基准",
     "content": "性能测试工具：1. sysbench测试CPU/内存/磁盘/数据库；2. ab/wrk测试Web服务QPS；3. iperf测试网络带宽；4. fio测试磁盘IOPS；5. 建立性能基线，对比变更前后的指标变化。"},
    {"title": "进程管理常用命令", "category": "系统管理", "tags": "进程,ps,kill",
     "content": "进程管理命令：1. ps aux查看所有进程；2. pgrep/pkill按名称查找/终止进程；3. kill -9 PID强制终止；4. nice/renice调整进程优先级；5. nohup后台运行不受终端关闭影响；6. screen/tmux多窗口管理。"},
    {"title": "内核参数调优", "category": "性能", "tags": "内核,sysctl",
     "content": "常用内核参数：1. vm.swappiness调整swap使用倾向；2. net.core.somaxconn调整TCP最大连接队列；3. fs.file-max调整最大文件句柄数；4. net.ipv4.tcp_tw_reuse快速回收TIME_WAIT连接；5. sysctl -p使配置生效。"},
    {"title": "监控指标体系建设", "category": "监控", "tags": "Prometheus,Grafana",
     "content": "监控四大黄金指标：1. 延迟(Latency)——请求耗时分布；2. 流量(Traffic)——QPS/带宽；3. 错误(Errors)——错误率/5xx；4. 饱和度(Saturation)——资源使用率。建议使用RED方法(服务)和USE方法(资源)结合。"},
]


def _get_model():
    """懒加载 sentence-transformers 模型（首次调用时下载约 80MB）"""
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("embedding 模型加载完成: all-MiniLM-L6-v2")
        except Exception as e:
            # 模型加载失败（如 torch CUDA 库不可用）时置为 False，语义检索降级为空
            logger.error(f"embedding 模型加载失败，语义检索将降级为不可用: {e}")
            _embedding_model = False
    return _embedding_model or None


def _embed(text: str) -> np.ndarray:
    """对文本计算 embedding 向量"""
    model = _get_model()
    return model.encode(text, normalize_embeddings=True)


async def rebuild_embedding_cache():
    """从数据库重建全部 embedding 缓存"""
    global _embedding_cache
    model = _get_model()
    if not model:
        logger.warning("embedding 模型不可用，跳过缓存重建")
        _embedding_cache = {}
        return
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(KnowledgeBase).where(KnowledgeBase.enabled == True)
        )
        entries = result.scalars().all()
        if not entries:
            _embedding_cache = {}
            return
        texts = [f"{e.title} {e.content} {e.tags or ''}" for e in entries]
        vectors = model.encode(texts, normalize_embeddings=True)
        _embedding_cache = {e.id: vec for e, vec in zip(entries, vectors)}
    logger.info(f"embedding 缓存已重建，共 {len(_embedding_cache)} 条")


async def search_knowledge(query: str, limit: int = 5) -> list[dict]:
    """语义搜索：用 cosine similarity 检索最相关的知识条目"""
    import asyncio as aio
    if not _embedding_cache:
        await rebuild_embedding_cache()
    if not _embedding_cache:
        return []

    # 在后台线程跑 embedding（sentence-transformers 是同步的）
    query_vec = await aio.to_thread(_embed, query)

    async with AsyncSessionLocal() as db:
        entry_ids = list(_embedding_cache.keys())
        entries = (
            await db.execute(
                select(KnowledgeBase).where(KnowledgeBase.id.in_(entry_ids))
            )
        ).scalars().all()
        entry_map = {e.id: e for e in entries}

    # 计算 cosine similarity（向量已 normalize，点积即 cosine）
    scored = []
    for eid, vec in _embedding_cache.items():
        entry = entry_map.get(eid)
        if entry is None:
            continue
        score = float(np.dot(query_vec, vec))
        scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:limit]

    return [
        {
            "id": e.id,
            "title": e.title,
            "content": e.content,
            "category": e.category,
            "tags": e.tags,
            "score": round(s, 4),
        }
        for s, e in top if s > 0.2  # 过滤低相关度
    ]


async def seed_preset_knowledge():
    """初始化预设知识库（幂等：跳过已存在的标题）"""
    async with AsyncSessionLocal() as db:
        for item in PRESET_KNOWLEDGE:
            existing = (
                await db.execute(
                    select(KnowledgeBase).where(KnowledgeBase.title == item["title"])
                )
            ).scalar_one_or_none()
            if existing:
                continue
            entry = KnowledgeBase(
                title=item["title"],
                content=item["content"],
                category=item.get("category"),
                tags=item.get("tags"),
                source="preset",
                enabled=True,
            )
            db.add(entry)
        await db.commit()
    await rebuild_embedding_cache()
    logger.info(f"预设知识库初始化完成，共 {len(PRESET_KNOWLEDGE)} 条")


async def create_entry(title: str, content: str, category: str = "", tags: str = "", source: str = "manual") -> dict:
    """新增知识条目"""
    async with AsyncSessionLocal() as db:
        entry = KnowledgeBase(
            title=title, content=content, category=category,
            tags=tags, source=source, enabled=True,
        )
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
    await rebuild_embedding_cache()
    return _entry_to_dict(entry)


async def update_entry(entry_id: str, **fields) -> dict | None:
    """更新知识条目"""
    async with AsyncSessionLocal() as db:
        entry = await db.get(KnowledgeBase, entry_id)
        if not entry:
            return None
        for k, v in fields.items():
            if hasattr(entry, k) and v is not None:
                setattr(entry, k, v)
        await db.commit()
        await db.refresh(entry)
    await rebuild_embedding_cache()
    return _entry_to_dict(entry)


async def delete_entry(entry_id: str) -> bool:
    """删除知识条目"""
    async with AsyncSessionLocal() as db:
        entry = await db.get(KnowledgeBase, entry_id)
        if not entry:
            return False
        await db.delete(entry)
        await db.commit()
    await rebuild_embedding_cache()
    return True


def _entry_to_dict(e: KnowledgeBase) -> dict:
    return {
        "id": e.id,
        "title": e.title,
        "content": e.content,
        "category": e.category,
        "tags": e.tags,
        "source": e.source,
        "enabled": e.enabled,
        "created_at": str(e.created_at) if e.created_at else None,
    }


async def build_rag_context(query: str, max_tokens: int = 2000) -> str:
    """构建 RAG 上下文：语义检索相关知识，拼接为 prompt 可用的文本"""
    try:
        items = await search_knowledge(query)
        if not items:
            return ""

        lines = ["以下是相关的运维知识，请基于这些知识回答问题：\n"]
        token_estimate = 0
        for item in items:
            snippet = f"---\n【{item['title']}】(相关度: {item['score']:.0%} | {item.get('category', '')}): {item['content']}\n"
            token_estimate += len(snippet) // 3
            if token_estimate > max_tokens:
                break
            lines.append(snippet)
        return "\n".join(lines)
    except Exception as e:
        # RAG 失败不能阻断 AI 修复/分析主流程，降级为无知识上下文
        logger.warning(f"RAG 上下文构建失败，跳过知识增强: {e}")
        return ""
