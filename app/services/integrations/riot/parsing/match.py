from typing import Any

from pydantic import TypeAdapter

from app.services.integrations.riot.models import RiotMatch

_match_ids_adapter = TypeAdapter(list[str])


def parse_match_ids(payload: list[Any]) -> list[str]:
    return _match_ids_adapter.validate_python(payload)


def parse_match(payload: dict[str, Any]) -> RiotMatch:
    return RiotMatch.from_payload(payload)
