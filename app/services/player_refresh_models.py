from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RefreshedPlayer:
    puuid: str
    game_name: str
    tag_line: str
    platform: str
    profile_icon_id: int | None
    summoner_level: int | None
    last_refreshed_at: datetime
    refresh_status: str
    refresh_error: str | None


@dataclass(frozen=True)
class RefreshedRankedEntry:
    queue_type: str
    tier: str | None
    rank: str | None
    league_points: int
    wins: int
    losses: int


@dataclass(frozen=True)
class PlayerRefreshResult:
    player: RefreshedPlayer
    ranked_entries: list[RefreshedRankedEntry]
