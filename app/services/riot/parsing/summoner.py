from typing import Any

from app.services.riot.models import RiotSummoner


def parse_summoner(payload: dict[str, Any]) -> RiotSummoner:
    return RiotSummoner.model_validate(payload)
