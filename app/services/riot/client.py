from collections.abc import Mapping
from typing import Any, cast

import httpx

from app.services.riot.endpoints import (
    ACCOUNT_BY_RIOT_ID,
    MATCH_BY_ID,
    MATCH_IDS_BY_PUUID,
    RANKED_ENTRIES_BY_PUUID,
    SUMMONER_BY_PUUID,
    RiotEndpoint,
)
from app.services.riot.parsers import (
    parse_account,
    parse_match,
    parse_match_ids,
    parse_ranked_entries,
    parse_summoner,
)
from app.services.riot.routing import RiotRouting
from app.services.riot.schemas import RiotAccount, RiotLeagueEntry, RiotMatch, RiotSummoner
from app.services.riot.transport import RiotTransport


class RiotClient:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        api_key: str,
        platform: str,
        region: str,
        *,
        max_retries: int = 3,
        backoff_base_seconds: float = 0.5,
        rate_limit_rps: float = 20.0,
        rate_limit_capacity: int = 20,
    ) -> None:
        self._routing = RiotRouting(platform=platform, region=region)
        self._transport = RiotTransport(
            http_client=http_client,
            api_key=api_key,
            max_retries=max_retries,
            backoff_base_seconds=backoff_base_seconds,
            rate_limit_rps=rate_limit_rps,
            rate_limit_capacity=rate_limit_capacity,
        )

    async def get_account_by_riot_id(self, game_name: str, tag_line: str) -> RiotAccount:
        payload = await self._fetch_json(
            ACCOUNT_BY_RIOT_ID,
            game_name=game_name,
            tag_line=tag_line,
        )
        return parse_account(cast(dict[str, Any], payload))

    async def get_summoner_by_puuid(self, puuid: str) -> RiotSummoner:
        payload = await self._fetch_json(SUMMONER_BY_PUUID, puuid=puuid)
        return parse_summoner(cast(dict[str, Any], payload))

    async def get_ranked_entries_by_puuid(self, puuid: str) -> list[RiotLeagueEntry]:
        payload = await self._fetch_json(RANKED_ENTRIES_BY_PUUID, puuid=puuid)
        return parse_ranked_entries(cast(list[Any], payload))

    async def get_match_ids_by_puuid(
        self,
        puuid: str,
        *,
        start: int = 0,
        count: int = 20,
        queue: int | None = None,
    ) -> list[str]:
        params: dict[str, int] = {"start": start, "count": count}
        if queue is not None:
            params["queue"] = queue

        payload = await self._fetch_json(MATCH_IDS_BY_PUUID, params=params, puuid=puuid)
        return parse_match_ids(cast(list[Any], payload))

    async def get_match(self, match_id: str) -> RiotMatch:
        payload = await self._fetch_json(MATCH_BY_ID, match_id=match_id)
        return parse_match(cast(dict[str, Any], payload))

    async def _fetch_json(
        self,
        endpoint: RiotEndpoint,
        params: Mapping[str, Any] | None = None,
        **path_parts: str,
    ) -> dict[str, Any] | list[Any]:
        path = self._routing.render_path(endpoint.path_template, **path_parts)
        url = self._routing.build_url(endpoint.host_kind, path)
        return await self._transport.get_json(
            url,
            response_kind=endpoint.response_kind,
            params=params,
        )
