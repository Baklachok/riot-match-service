from collections.abc import Iterable
from typing import TypeVar

from pydantic import BaseModel

from app.schemas.player_read import (
    ReadChampionStatsResponse,
    ReadPlayerChampionsResponse,
    ReadPlayerMatchesResponse,
    ReadPlayerMatchResponse,
    ReadPlayerProfileResponse,
    ReadPlayerResponse,
)
from app.services import (
    ReadChampionStats,
    ReadPlayer,
    ReadPlayerMatch,
    ReadPlayerProfile,
)

_SchemaT = TypeVar("_SchemaT", bound=BaseModel)


def to_read_player_response(player: ReadPlayer) -> ReadPlayerResponse:
    return _to_schema(ReadPlayerResponse, player)


def to_read_player_profile_response(profile: ReadPlayerProfile) -> ReadPlayerProfileResponse:
    return _to_schema(ReadPlayerProfileResponse, profile)


def to_read_player_matches_response(
    *,
    matches: list[ReadPlayerMatch],
    limit: int,
) -> ReadPlayerMatchesResponse:
    return ReadPlayerMatchesResponse(
        limit=limit,
        items=_to_schema_list(ReadPlayerMatchResponse, matches),
    )


def to_read_player_champions_response(
    *,
    champions: list[ReadChampionStats],
    queue_id: int,
    limit: int,
) -> ReadPlayerChampionsResponse:
    return ReadPlayerChampionsResponse(
        queue_id=queue_id,
        limit=limit,
        items=_to_schema_list(ReadChampionStatsResponse, champions),
    )


def _to_schema(schema: type[_SchemaT], source: object) -> _SchemaT:
    return schema.model_validate(source, from_attributes=True)


def _to_schema_list(schema: type[_SchemaT], sources: Iterable[object]) -> list[_SchemaT]:
    return [schema.model_validate(source, from_attributes=True) for source in sources]
