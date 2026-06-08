from enum import StrEnum

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    log_level: LogLevel = LogLevel.INFO

    database_url: str = Field(
        default="postgresql+asyncpg://localhost:5432/solved_sports",
        description="Async SQLAlchemy database URL",
    )
    database_pool_size: int = Field(default=10, ge=1)
    database_max_overflow: int = Field(default=20, ge=0)

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    odds_api_key: str = ""
    stats_api_key: str = ""

    ev_threshold_percent: float = Field(
        default=3.0,
        description="Minimum +EV percentage to surface an opportunity",
    )

    odds_poll_interval_seconds: int = Field(
        default=60,
        ge=5,
        description="Seconds between odds polling cycles",
    )
    odds_api_base_url: str = "https://api.the-odds-api.com/v4"
    stats_api_base_url: str = "https://api.sportsdata.io/v3"
