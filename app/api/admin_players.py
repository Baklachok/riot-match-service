from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session
from app.schemas.player_refresh import (
    PlayerProfileResponse,
    PlayerRefreshRequest,
    PlayerRefreshResponse,
    RankedEntryResponse,
)
from app.services.player_refresh import PlayerRefreshService
from app.services.riot.client import RiotClient
from app.services.riot.dependencies import get_riot_client
from app.services.riot.errors import RiotApiError, RiotClientError

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.post("/players/refresh", response_model=PlayerRefreshResponse)
async def refresh_player(
    payload: PlayerRefreshRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    riot_client: Annotated[RiotClient, Depends(get_riot_client)],
) -> PlayerRefreshResponse:
    service = PlayerRefreshService(
        session=session,
        riot_client=riot_client,
        platform=settings.riot_platform,
    )

    try:
        result = await service.refresh_player(
            game_name=payload.game_name,
            tag_line=payload.tag_line,
        )
    except RiotApiError as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=404, detail="Player not found in Riot API") from exc
        raise HTTPException(
            status_code=502,
            detail=f"Riot API returned {exc.status_code}",
        ) from exc
    except RiotClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return PlayerRefreshResponse(
        player=PlayerProfileResponse(
            puuid=result.player.puuid,
            game_name=result.player.game_name,
            tag_line=result.player.tag_line,
            platform=result.player.platform,
            profile_icon_id=result.player.profile_icon_id,
            summoner_level=result.player.summoner_level,
            last_refreshed_at=result.player.last_refreshed_at,
            refresh_status=result.player.refresh_status,
            refresh_error=result.player.refresh_error,
        ),
        ranked_entries=[
            RankedEntryResponse(
                queue_type=entry.queue_type,
                tier=entry.tier,
                rank=entry.rank,
                league_points=entry.league_points,
                wins=entry.wins,
                losses=entry.losses,
            )
            for entry in result.ranked_entries
        ],
    )
