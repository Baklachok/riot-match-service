from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


router = APIRouter()


@router.get("/healthz")
async def healthz() -> HealthResponse:
    return HealthResponse()
