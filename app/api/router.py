from fastapi import APIRouter

from app.api.admin_players import router as admin_players_router
from app.api.health import router as health_router
from app.api.players import router as players_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(players_router)
api_router.include_router(admin_players_router)
