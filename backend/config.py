from pydantic_settings import BaseSettings  # 配置基类


class Settings(BaseSettings):

    # 应用基础配置
    app_name: str = "Py_Itops Platform"
    app_version: str = "2.0.0"
    environment: str = "development"  # production / development,对应开发/生产环境
    debug: bool = True
    debug_sql: bool = False

    # ========安全=========
    secret_key: str = "your-super-secret-key-change-in-production"  # JWT密钥
    algorithms: str = "HS256"
    access_token_expires_minutes: int = 30  # 登陆有效时长
    # ======数据库=========
    database_url: str = "sqlite+aiosqlite:///./data/itops.db"  # 数据库类型+异步驱动+数据库文件存放位置

    # PostgreSQL(生产环境通过环境变量注入,docker-compose / k8s 中配置)
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "itops"
    postgres_password: str = "itops123"
    postgres_db: str = "itops"

    #===========Redis============
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0
    redis_url: str = "" # 如果设置，直接使用完整的Redis URL

    # ======LLM / AI =============
    llm_provider: str = "deepseek"  # deepseek | openai
    deepseek_api_key: str = ""
    deepseek_api_base: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-v4-flash"
    openai_api_key: str = ""
    openai_api_base: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-3.5-turbo"

    # ====巡检阈值=======
    cpu_threshold: float = 90.0
    memory_threshold: float = 90.0
    disk_threshold: float = 90.0

    # ======SMTP邮件========
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True

    # =========日志==========
    log_level: str = "INFO"         # DEBUG | INFO | WARNING | ERROR
    log_format: str = "json"        # json | text —— 生产用json

    # ======限流======
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100  # 每分钟每 IP 最大请求数
    rate_limit_window_seconds: int = 60

    # ====CORS=======
    cors_origins: str = "http://localhost:3000,http://localhost:3001,http://localhost:8501,http://127.0.0.1:3000,http://127.0.0.1:3001,http://127.0.0.1:8000"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def get_redis_url(self) -> str:
        """获取Redis连接URL"""
        if self.redis_url:
            return self.redis_url
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    def get_postgres_url(self) -> str:
        """获取PostgreSQL 连接URL"""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
settings = Settings()


