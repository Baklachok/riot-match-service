from typing import Any

from pydantic import TypeAdapter

from app.services.riot.schemas import RiotAccount, RiotLeagueEntry, RiotMatch, RiotSummoner

league_entries_adapter = TypeAdapter(list[RiotLeagueEntry])
match_ids_adapter = TypeAdapter(list[str])


def parse_account(payload: dict[str, Any]) -> RiotAccount:
    return RiotAccount.model_validate(payload)


def parse_summoner(payload: dict[str, Any]) -> RiotSummoner:
    return RiotSummoner.model_validate(payload)


def parse_ranked_entries(payload: list[Any]) -> list[RiotLeagueEntry]:
    return league_entries_adapter.validate_python(payload)


def parse_match_ids(payload: list[Any]) -> list[str]:
    return match_ids_adapter.validate_python(payload)


def parse_match(payload: dict[str, Any]) -> RiotMatch:
    match = RiotMatch.model_validate(payload)
    match.raw_json = payload
    return match
