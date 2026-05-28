from dataclasses import dataclass
from enum import StrEnum


class HostKind(StrEnum):
    PLATFORM = "platform"
    REGIONAL = "regional"


class ResponseKind(StrEnum):
    OBJECT = "object"
    ARRAY = "array"


@dataclass(frozen=True)
class RiotEndpoint:
    path_template: str
    host_kind: HostKind
    response_kind: ResponseKind


ACCOUNT_BY_RIOT_ID = RiotEndpoint(
    path_template="/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}",
    host_kind=HostKind.REGIONAL,
    response_kind=ResponseKind.OBJECT,
)

ACCOUNT_BY_PUUID = RiotEndpoint(
    path_template="/riot/account/v1/accounts/by-puuid/{puuid}",
    host_kind=HostKind.REGIONAL,
    response_kind=ResponseKind.OBJECT,
)

SUMMONER_BY_PUUID = RiotEndpoint(
    path_template="/lol/summoner/v4/summoners/by-puuid/{puuid}",
    host_kind=HostKind.PLATFORM,
    response_kind=ResponseKind.OBJECT,
)

RANKED_ENTRIES_BY_PUUID = RiotEndpoint(
    path_template="/lol/league/v4/entries/by-puuid/{puuid}",
    host_kind=HostKind.PLATFORM,
    response_kind=ResponseKind.ARRAY,
)

MATCH_IDS_BY_PUUID = RiotEndpoint(
    path_template="/lol/match/v5/matches/by-puuid/{puuid}/ids",
    host_kind=HostKind.REGIONAL,
    response_kind=ResponseKind.ARRAY,
)

MATCH_BY_ID = RiotEndpoint(
    path_template="/lol/match/v5/matches/{match_id}",
    host_kind=HostKind.REGIONAL,
    response_kind=ResponseKind.OBJECT,
)
