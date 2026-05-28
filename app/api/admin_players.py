from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin_players_mapper import to_player_refresh_response
from app.core.config import settings
from app.db.session import get_session
from app.schemas.player_refresh import (
    PlayerRefreshErrorDetail,
    PlayerRefreshErrorResponse,
    PlayerRefreshRequest,
    PlayerRefreshResponse,
)
from app.services.player_refresh import PlayerRefreshService
from app.services.riot.client import RiotClient
from app.services.riot.dependencies import get_riot_client
from app.services.riot.errors import RiotApiError, RiotClientError

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

_INVALID_IDENTIFIER_FORMAT_MESSAGE = "identifier with # must be in format gameName#tagLine"
_INVALID_IDENTIFIER_PARTS_MESSAGE = "identifier must contain non-empty gameName and tagLine"
_EMPTY_IDENTIFIER_MESSAGE = "identifier must not be empty"


@router.post(
    "/players/refresh",
    response_model=PlayerRefreshResponse,
    responses={
        422: {
            "model": PlayerRefreshErrorResponse,
            "description": "Invalid identifier format",
        },
        404: {
            "model": PlayerRefreshErrorResponse,
            "description": "Player was not found in Riot API",
        },
        502: {
            "model": PlayerRefreshErrorResponse,
            "description": "Riot API is unavailable or returned an unexpected error",
        },
    },
)
async def refresh_player(
    payload: PlayerRefreshRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    riot_client: Annotated[RiotClient, Depends(get_riot_client)],
) -> PlayerRefreshResponse:
    service = PlayerRefreshService(
        session=session,
        riot_client=riot_client,
        platform=settings.riot_platform,
        match_sync_count=settings.riot_match_sync_count,
        match_sync_queue=settings.riot_match_sync_queue,
    )
    player_identifier, tag_line = _parse_identifier(payload.identifier)

    try:
        if tag_line is None:
            result = await service.refresh_player_by_puuid(puuid=player_identifier)
        else:
            result = await service.refresh_player_by_riot_id(
                game_name=player_identifier,
                tag_line=tag_line,
            )
    except RiotApiError as exc:
        if exc.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail=_error_detail(
                    code="PLAYER_NOT_FOUND",
                    message="Player not found in Riot API",
                    upstream_status=404,
                ),
            ) from exc
        raise HTTPException(
            status_code=502,
            detail=_error_detail(
                code="RIOT_API_ERROR",
                message="Riot API returned an error",
                upstream_status=exc.status_code,
            ),
        ) from exc
    except RiotClientError as exc:
        raise HTTPException(
            status_code=502,
            detail=_error_detail(
                code="RIOT_CLIENT_ERROR",
                message=str(exc),
                upstream_status=None,
            ),
        ) from exc

    return to_player_refresh_response(result)


def _parse_identifier(identifier: str) -> tuple[str, str | None]:
    normalized = identifier.strip()
    if not normalized:
        _raise_invalid_identifier(_EMPTY_IDENTIFIER_MESSAGE)

    if "#" not in normalized:
        return normalized, None

    if normalized.count("#") != 1:
        _raise_invalid_identifier(_INVALID_IDENTIFIER_FORMAT_MESSAGE)

    game_name, tag_line = (part.strip() for part in normalized.split("#", 1))
    if not game_name or not tag_line:
        _raise_invalid_identifier(_INVALID_IDENTIFIER_PARTS_MESSAGE)
    return game_name, tag_line


def _error_detail(
    *,
    code: str,
    message: str,
    upstream_status: int | None,
) -> dict[str, object]:
    return PlayerRefreshErrorDetail(
        code=code,
        message=message,
        upstream_status=upstream_status,
    ).model_dump()


def _raise_invalid_identifier(message: str) -> NoReturn:
    raise HTTPException(
        status_code=422,
        detail=_error_detail(
            code="INVALID_IDENTIFIER",
            message=message,
            upstream_status=None,
        ),
    )
