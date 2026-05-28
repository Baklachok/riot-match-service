from typing import Any

from pydantic import TypeAdapter

from app.services.riot.models import RiotLeagueEntry

_league_entries_adapter = TypeAdapter(list[RiotLeagueEntry])


def parse_ranked_entries(payload: list[Any]) -> list[RiotLeagueEntry]:
    return _league_entries_adapter.validate_python(payload)
