from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RiotBaseModel(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class RiotAccount(RiotBaseModel):
    puuid: str
    game_name: str = Field(alias="gameName")
    tag_line: str = Field(alias="tagLine")


class RiotSummoner(RiotBaseModel):
    puuid: str
    id: str | None = None
    account_id: str | None = Field(default=None, alias="accountId")
    profile_icon_id: int | None = Field(default=None, alias="profileIconId")
    revision_date: int | None = Field(default=None, alias="revisionDate")
    summoner_level: int | None = Field(default=None, alias="summonerLevel")


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


class RiotMatchMetadata(RiotBaseModel):
    data_version: str | None = Field(default=None, alias="dataVersion")
    match_id: str = Field(alias="matchId")
    participants: list[str]


class RiotParticipant(RiotBaseModel):
    puuid: str
    champion_id: int = Field(alias="championId")
    champion_name: str = Field(alias="championName")
    team_position: str | None = Field(default=None, alias="teamPosition")
    win: bool
    kills: int
    deaths: int
    assists: int
    gold_earned: int = Field(default=0, alias="goldEarned")
    total_minions_killed: int = Field(default=0, alias="totalMinionsKilled")
    neutral_minions_killed: int = Field(default=0, alias="neutralMinionsKilled")
    vision_score: int = Field(default=0, alias="visionScore")
    total_damage_dealt_to_champions: int = Field(
        default=0,
        alias="totalDamageDealtToChampions",
    )
    summoner_spell_1_id: int = Field(alias="summoner1Id")
    summoner_spell_2_id: int = Field(alias="summoner2Id")
    item0: int = 0
    item1: int = 0
    item2: int = 0
    item3: int = 0
    item4: int = 0
    item5: int = 0
    item6: int = 0
    challenges: dict[str, Any] | None = None


class RiotMatchInfo(RiotBaseModel):
    game_creation: int | None = Field(default=None, alias="gameCreation")
    game_start_timestamp: int | None = Field(default=None, alias="gameStartTimestamp")
    game_end_timestamp: int | None = Field(default=None, alias="gameEndTimestamp")
    game_duration: int = Field(alias="gameDuration")
    game_id: int = Field(alias="gameId")
    game_mode: str = Field(alias="gameMode")
    game_name: str | None = Field(default=None, alias="gameName")
    game_version: str = Field(alias="gameVersion")
    queue_id: int = Field(alias="queueId")
    participants: list[RiotParticipant]


class RiotMatch(RiotBaseModel):
    metadata: RiotMatchMetadata
    info: RiotMatchInfo
    raw_json: dict[str, Any] = Field(default_factory=dict, exclude=True)
