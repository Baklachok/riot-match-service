from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ReadPlayer:
    puuid: str
    game_name: str
    tag_line: str
    platform: str
    profile_icon_id: int | None
    summoner_level: int | None
    last_refreshed_at: datetime | None
    refresh_status: str | None
    refresh_error: str | None


@dataclass(frozen=True)
class ReadRankedEntry:
    queue_type: str
    tier: str | None
    rank: str | None
    league_points: int
    wins: int
    losses: int


@dataclass(frozen=True)
class ReadPlayerProfile:
    player: ReadPlayer
    ranked_entries: list[ReadRankedEntry]


@dataclass(frozen=True)
class ReadPlayerMatch:
    match_id: str
    champion_id: int
    champion_name: str
    lane: str | None
    win: bool
    kills: int
    deaths: int
    assists: int
    kda: float
    queue_id: int
    game_start: datetime
    duration_seconds: int
    patch: str | None


@dataclass(frozen=True)
class ReadChampionStats:
    champion_id: int
    champion_name: str
    games: int
    wins: int
    losses: int
    win_rate_percent: float
    kda: float
