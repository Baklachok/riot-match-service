from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Riot Match Service"
    database_url: str = Field(
        default="postgresql+asyncpg://riot:riot@localhost:5432/riot_match_service"
    )
    riot_api_key: str = ""
    riot_platform: str = "euw1"
    riot_region: str = "europe"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
