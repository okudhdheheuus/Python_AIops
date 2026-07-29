
import logging
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import settings

DATABASE_URL = os.getenv("DATABASE_URL",settings.database_url)
# 引擎参数根据数据库类型区分
if "postgresql" in DATABASE_URL or "postgres" in DATABASE_URL:
    engine_kwargs = {
        "echo":settings.debug_sql,
        "pool_size":20,                   # PostgreSQL 连接池
        "max_overflow":10,                # 峰值额外连接数
        "pool_pre_ping":True,             # 连接前检测可用性
        "pool_recycle":3600,              # 每小时回收连接，防止PG服务端断开
    }
else:
    # SQLite 不支持连接池参数
    engine_kwargs = {"echo":settings.debug_sql}
engine = create_async_engine(DATABASE_URL,**engine_kwargs)
# 异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    engine,class_=AsyncSession,expire_on_commit=False
)

class Base(DeclarativeBase):
    """所有ORM模型的基类"""
async def get_db() -> AsyncSession:
    """FastAPI 依赖注入 —— 每次请求创建一个新的数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def ensure_sqlite_columns():
    """开发模式：自动为 SQLite 添加缺失的列（生产环境请用 Alembic）"""
    if "sqlite" not in DATABASE_URL:
        return
    import sqlite3
    db_path = DATABASE_URL.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
    if not db_path:
        return
    conn = sqlite3.connect(db_path)
    try:
        existing = {c[1] for c in conn.execute("PRAGMA table_info(notification_channels)")}
        if "sign_secret" not in existing:
            conn.execute("ALTER TABLE notification_channels ADD COLUMN sign_secret VARCHAR(200)")
            conn.commit()
            logging.getLogger("itops").info("Database: added missing column notification_channels.sign_secret")
        # remediation_policies 新字段
        rp_cols = {c[1] for c in conn.execute("PRAGMA table_info(remediation_policies)")}
        for col_name, col_type in [("repair_mode", "VARCHAR(20) DEFAULT 'ai'"),
                                    ("requires_approval", "BOOLEAN DEFAULT 1")]:
            if col_name not in rp_cols:
                conn.execute(f"ALTER TABLE remediation_policies ADD COLUMN {col_name} {col_type}")
                conn.commit()
                logging.getLogger("itops").info(f"Database: added missing column remediation_policies.{col_name}")
    finally:
        conn.close()


async def check_db_health() -> bool:
    """数据库健康检查 —— 执行轻量查询验证连接可用"""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False








