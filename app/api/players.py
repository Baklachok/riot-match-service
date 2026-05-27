from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.players_mapper import (
    to_read_player_champions_response,
    to_read_player_matches_response,
    to_read_player_profile_response,
    to_read_player_response,
)
from app.db.session import get_session
from app.schemas.player_read import (
    ReadApiErrorDetail,
    ReadApiErrorResponse,
    ReadPlayerChampionsResponse,
    ReadPlayerMatchesResponse,
    ReadPlayerProfileResponse,
    ReadPlayerResponse,
)
from app.services.player_read import PlayerReadService

_SOLOQ_QUEUE_ID = 420

router = APIRouter(prefix="/api/v1/players", tags=["players"])


@router.get(
    "/search",
    response_model=ReadPlayerResponse,
    responses={
        404: {
            "model": ReadApiErrorResponse,
            "description": "Player not found in local database",
        },
        422: {
            "model": ReadApiErrorResponse,
            "description": "Invalid riot_id format",
        },
    },
)
async def search_player(
    riot_id: Annotated[str, Query(min_length=3, max_length=128)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReadPlayerResponse:
    game_name, tag_line = _parse_riot_id(riot_id)
    service = PlayerReadService(session=session)
    player = await service.search_player_by_riot_id(
        game_name=game_name,
        tag_line=tag_line,
    )
    if player is None:
        raise HTTPException(
            status_code=404,
            detail=_error_detail(
                code="PLAYER_NOT_FOUND",
                message="Player not found in local database",
            ),
        )
    return to_read_player_response(player)


@router.get(
    "/{puuid}/profile",
    response_model=ReadPlayerProfileResponse,
    responses={
        404: {
            "model": ReadApiErrorResponse,
            "description": "Player not found in local database",
        }
    },
)
async def get_player_profile(
    puuid: Annotated[str, Path(min_length=1, max_length=128)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReadPlayerProfileResponse:
    service = PlayerReadService(session=session)
    profile = await service.get_player_profile(puuid=puuid)
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail=_error_detail(
                code="PLAYER_NOT_FOUND",
                message="Player not found in local database",
            ),
        )
    return to_read_player_profile_response(profile)


@router.get(
    "/{puuid}/matches",
    response_model=ReadPlayerMatchesResponse,
    responses={
        404: {
            "model": ReadApiErrorResponse,
            "description": "Player not found in local database",
        }
    },
)
async def get_player_matches(
    puuid: Annotated[str, Path(min_length=1, max_length=128)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ReadPlayerMatchesResponse:
    service = PlayerReadService(session=session)
    matches = await service.get_player_matches(
        puuid=puuid,
        limit=limit,
    )
    if matches is None:
        raise HTTPException(
            status_code=404,
            detail=_error_detail(
                code="PLAYER_NOT_FOUND",
                message="Player not found in local database",
            ),
        )
    return to_read_player_matches_response(matches=matches, limit=limit)


@router.get(
    "/{puuid}/champions",
    response_model=ReadPlayerChampionsResponse,
    responses={
        404: {
            "model": ReadApiErrorResponse,
            "description": "Player not found in local database",
        }
    },
)
async def get_player_champions(
    puuid: Annotated[str, Path(min_length=1, max_length=128)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ReadPlayerChampionsResponse:
    service = PlayerReadService(session=session)
    champions = await service.get_player_champions(
        puuid=puuid,
        queue_id=_SOLOQ_QUEUE_ID,
        limit=limit,
    )
    if champions is None:
        raise HTTPException(
            status_code=404,
            detail=_error_detail(
                code="PLAYER_NOT_FOUND",
                message="Player not found in local database",
            ),
        )
    return to_read_player_champions_response(
        champions=champions,
        queue_id=_SOLOQ_QUEUE_ID,
        limit=limit,
    )


def _parse_riot_id(riot_id: str) -> tuple[str, str]:
    normalized = riot_id.strip()
    if normalized.count("#") != 1:
        raise HTTPException(
            status_code=422,
            detail=_error_detail(
                code="INVALID_RIOT_ID",
                message="riot_id must be in format gameName#tagLine",
            ),
        )

    game_name, tag_line = (part.strip() for part in normalized.split("#", 1))
    if not game_name or not tag_line:
        raise HTTPException(
            status_code=422,
            detail=_error_detail(
                code="INVALID_RIOT_ID",
                message="riot_id must contain non-empty gameName and tagLine",
            ),
        )
    return game_name, tag_line


def _error_detail(*, code: str, message: str) -> dict[str, str]:
    return ReadApiErrorDetail(
        code=code,
        message=message,
    ).model_dump()
