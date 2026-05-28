from pydantic import Field

from app.services.riot.models.base import RiotBaseModel


class RiotSummoner(RiotBaseModel):
    puuid: str
    id: str | None = None
    account_id: str | None = Field(default=None, alias="accountId")
    profile_icon_id: int | None = Field(default=None, alias="profileIconId")
    revision_date: int | None = Field(default=None, alias="revisionDate")
    summoner_level: int | None = Field(default=None, alias="summonerLevel")
