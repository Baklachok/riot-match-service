from typing import Any

from app.services.integrations.riot.models import RiotAccount


def parse_account(payload: dict[str, Any]) -> RiotAccount:
    return RiotAccount.model_validate(payload)
