from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Postgres
    database_url: str = "postgresql+asyncpg://runtime:changeme@localhost:5432/gemini_runtime"

    # ClickHouse
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 9000
    clickhouse_db: str = "default"
    clickhouse_user: str = "default"
    clickhouse_password: str = ""

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-pro"

    # Service URLs (used by API gateway)
    orchestrator_url: str = "http://localhost:8001"
    analytics_url: str = "http://localhost:8003"
    ingestion_url: str = "http://localhost:8002"

    # Auth
    api_key: str = "dev-key"

    # Agent worker
    agent_role: str = "planner"
    workspace_root: str = "/workspace"

    # Observability
    log_level: str = "INFO"
    otel_endpoint: str = ""  # OTLP exporter endpoint, empty = stdout only

    # Retry
    max_agent_retries: int = 3
    task_timeout_seconds: int = 300

    # SLO thresholds
    planner_slo_latency_ms: float = 30_000
    executor_first_pass_rate: float = 0.90
    verifier_parse_success_rate: float = 0.99
    system_completion_rate: float = 0.95


settings = Settings()
