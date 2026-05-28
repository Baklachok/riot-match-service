from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PlayerRefreshRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=128)


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


class MatchSyncResponse(BaseModel):
    queue: int
    requested_count: int
    match_ids_received: int
    new_matches_saved: int
    existing_matches_skipped: int
    player_matches_upserted: int
    backfilled_from_raw: int
    failed_matches: int
    failed_match_ids: list[str]


class RefreshSummaryResponse(BaseModel):
    matches_found: int
    new_matches_saved: int
    refreshed_at: datetime


class PlayerRefreshResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    player: PlayerProfileResponse
    ranked_entries: list[RankedEntryResponse]
    match_sync: MatchSyncResponse
    summary: RefreshSummaryResponse


class PlayerRefreshErrorDetail(BaseModel):
    code: str
    message: str
    upstream_status: int | None = None


class PlayerRefreshErrorResponse(BaseModel):
    detail: PlayerRefreshErrorDetail
