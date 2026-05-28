from typing import Annotated, Any, NoReturn, TypeVar

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

_PLAYER_NOT_FOUND_MESSAGE = "Player not found in local database"
_INVALID_RIOT_ID_FORMAT_MESSAGE = "riot_id must be in format gameName#tagLine"
_INVALID_RIOT_ID_PARTS_MESSAGE = "riot_id must contain non-empty gameName and tagLine"

_ResponseMap = dict[int | str, dict[str, Any]]

_NOT_FOUND_RESPONSES: _ResponseMap = {
    404: {
        "model": ReadApiErrorResponse,
        "description": _PLAYER_NOT_FOUND_MESSAGE,
    }
}
_SEARCH_RESPONSES: _ResponseMap = {
    **_NOT_FOUND_RESPONSES,
    422: {
        "model": ReadApiErrorResponse,
        "description": "Invalid riot_id format",
    },
}

router = APIRouter(prefix="/api/v1/players", tags=["players"])

_T = TypeVar("_T")


def get_player_read_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PlayerReadService:
    return PlayerReadService(session=session)


@router.get(
    "/search",
    response_model=ReadPlayerResponse,
    responses=_SEARCH_RESPONSES,
)
async def search_player(
    riot_id: Annotated[str, Query(min_length=3, max_length=128)],
    service: Annotated[PlayerReadService, Depends(get_player_read_service)],
) -> ReadPlayerResponse:
    game_name, tag_line = _parse_riot_id(riot_id)
    player = _require_found(
        await service.search_player_by_riot_id(
            game_name=game_name,
            tag_line=tag_line,
        )
    )
    return to_read_player_response(player)


@router.get(
    "/{puuid}/profile",
    response_model=ReadPlayerProfileResponse,
    responses=_NOT_FOUND_RESPONSES,
)
async def get_player_profile(
    puuid: Annotated[str, Path(min_length=1, max_length=128)],
    service: Annotated[PlayerReadService, Depends(get_player_read_service)],
) -> ReadPlayerProfileResponse:
    profile = _require_found(await service.get_player_profile(puuid=puuid))
    return to_read_player_profile_response(profile)


@router.get(
    "/{puuid}/matches",
    response_model=ReadPlayerMatchesResponse,
    responses=_NOT_FOUND_RESPONSES,
)
async def get_player_matches(
    puuid: Annotated[str, Path(min_length=1, max_length=128)],
    service: Annotated[PlayerReadService, Depends(get_player_read_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ReadPlayerMatchesResponse:
    matches = _require_found(await service.get_player_matches(puuid=puuid, limit=limit))
    return to_read_player_matches_response(matches=matches, limit=limit)


@router.get(
    "/{puuid}/champions",
    response_model=ReadPlayerChampionsResponse,
    responses=_NOT_FOUND_RESPONSES,
)
async def get_player_champions(
    puuid: Annotated[str, Path(min_length=1, max_length=128)],
    service: Annotated[PlayerReadService, Depends(get_player_read_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ReadPlayerChampionsResponse:
    champions = _require_found(
        await service.get_player_champions(
            puuid=puuid,
            queue_id=_SOLOQ_QUEUE_ID,
            limit=limit,
        )
    )
    return to_read_player_champions_response(
        champions=champions,
        queue_id=_SOLOQ_QUEUE_ID,
        limit=limit,
    )


def _parse_riot_id(riot_id: str) -> tuple[str, str]:
    normalized = riot_id.strip()
    if normalized.count("#") != 1:
        _raise_invalid_riot_id(_INVALID_RIOT_ID_FORMAT_MESSAGE)

    game_name, tag_line = (part.strip() for part in normalized.split("#", 1))
    if not game_name or not tag_line:
        _raise_invalid_riot_id(_INVALID_RIOT_ID_PARTS_MESSAGE)
    return game_name, tag_line


def _require_found(value: _T | None) -> _T:
    if value is None:
        _raise_player_not_found()
    return value


def _raise_player_not_found() -> NoReturn:
    raise HTTPException(
        status_code=404,
        detail=_error_detail(
            code="PLAYER_NOT_FOUND",
            message=_PLAYER_NOT_FOUND_MESSAGE,
        ),
    )


def _raise_invalid_riot_id(message: str) -> NoReturn:
    raise HTTPException(
        status_code=422,
        detail=_error_detail(
            code="INVALID_RIOT_ID",
            message=message,
        ),
    )


def _error_detail(*, code: str, message: str) -> dict[str, str]:
    return ReadApiErrorDetail(
        code=code,
        message=message,
    ).model_dump()
