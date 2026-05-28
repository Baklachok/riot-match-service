from pydantic import Field

from app.services.riot.models.base import RiotBaseModel


class RiotAccount(RiotBaseModel):
    puuid: str
    game_name: str = Field(alias="gameName")
    tag_line: str = Field(alias="tagLine")
