from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Riot Match Service"
    database_url: str = Field(
        default="postgresql+asyncpg://riot:riot@postgres:5432/riot_match_service"
    )
    riot_api_key: str = ""
    riot_platform: str = "euw1"
    riot_region: str = "europe"
    riot_max_retries: int = 3
    riot_backoff_base_seconds: float = 0.5
    riot_rate_limit_rps: float = 20.0
    riot_rate_limit_capacity: int = 20
    riot_match_sync_count: int = 30
    riot_match_sync_queue: int = 420

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
