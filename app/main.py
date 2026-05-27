from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings
from app.services.riot.client import RiotClient


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    timeout = httpx.Timeout(20.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as http_client:
        app.state.riot_client = RiotClient(
            http_client=http_client,
            api_key=settings.riot_api_key,
            platform=settings.riot_platform,
            region=settings.riot_region,
            max_retries=settings.riot_max_retries,
            backoff_base_seconds=settings.riot_backoff_base_seconds,
            rate_limit_rps=settings.riot_rate_limit_rps,
            rate_limit_capacity=settings.riot_rate_limit_capacity,
        )
        yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.include_router(api_router)
    return app


app = create_app()
