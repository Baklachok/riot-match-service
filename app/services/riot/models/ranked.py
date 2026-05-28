from pydantic import Field

from app.services.riot.models.base import RiotBaseModel


class RiotLeagueEntry(RiotBaseModel):
    queue_type: str = Field(alias="queueType")
    tier: str | None = None
    rank: str | None = None
    league_points: int = Field(default=0, alias="leaguePoints")
    wins: int = 0
    losses: int = 0
    hot_streak: bool | None = Field(default=None, alias="hotStreak")
    veteran: bool | None = None
    fresh_blood: bool | None = Field(default=None, alias="freshBlood")
    inactive: bool | None = None
