from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReadApiErrorDetail(BaseModel):
    code: str
    message: str


class ReadApiErrorResponse(BaseModel):
    detail: ReadApiErrorDetail


class ReadPlayerResponse(BaseModel):
    puuid: str
    game_name: str
    tag_line: str
    platform: str
    profile_icon_id: int | None = None
    summoner_level: int | None = None
    last_refreshed_at: datetime | None = None
    refresh_status: str | None = None
    refresh_error: str | None = None


class ReadRankedEntryResponse(BaseModel):
    queue_type: str
    tier: str | None = None
    rank: str | None = None
    league_points: int
    wins: int
    losses: int


class ReadPlayerProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    player: ReadPlayerResponse
    ranked_entries: list[ReadRankedEntryResponse]


class ReadPlayerMatchResponse(BaseModel):
    match_id: str
    champion_id: int
    champion_name: str
    lane: str | None = None
    win: bool
    kills: int
    deaths: int
    assists: int
    kda: float
    queue_id: int
    game_start: datetime
    duration_seconds: int
    patch: str | None = None


class ReadPlayerMatchesResponse(BaseModel):
    limit: int
    items: list[ReadPlayerMatchResponse]


class ReadChampionStatsResponse(BaseModel):
    champion_id: int
    champion_name: str
    games: int
    wins: int
    losses: int
    win_rate_percent: float
    kda: float


class ReadPlayerChampionsResponse(BaseModel):
    queue_id: int
    limit: int
    items: list[ReadChampionStatsResponse]
