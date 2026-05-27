from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PlayerRefreshRequest(BaseModel):
    game_name: str = Field(min_length=1, max_length=64)
    tag_line: str = Field(min_length=1, max_length=16)


class RankedEntryResponse(BaseModel):
    queue_type: str
    tier: str | None = None
    rank: str | None = None
    league_points: int
    wins: int
    losses: int


class PlayerProfileResponse(BaseModel):
    puuid: str
    game_name: str
    tag_line: str
    platform: str
    profile_icon_id: int | None = None
    summoner_level: int | None = None
    last_refreshed_at: datetime
    refresh_status: str
    refresh_error: str | None = None


class PlayerRefreshResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    player: PlayerProfileResponse
    ranked_entries: list[RankedEntryResponse]
