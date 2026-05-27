from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import TypeAdapter

from app.services.riot.errors import RiotApiError, RiotClientError, RiotConfigurationError
from app.services.riot.schemas import RiotAccount, RiotLeagueEntry, RiotMatch, RiotSummoner


class RiotClient:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        api_key: str,
        platform: str,
        region: str,
    ) -> None:
        self._http_client = http_client
        self._api_key = api_key.strip()
        self._platform = platform.strip().lower()
        self._region = region.strip().lower()

    async def get_account_by_riot_id(self, game_name: str, tag_line: str) -> RiotAccount:
        path = (
            "/riot/account/v1/accounts/by-riot-id/"
            f"{self._path_part(game_name)}/{self._path_part(tag_line)}"
        )
        data = await self._get_object_json(self._regional_url(path))
        return RiotAccount.model_validate(data)

    async def get_summoner_by_puuid(self, puuid: str) -> RiotSummoner:
        path = f"/lol/summoner/v4/summoners/by-puuid/{self._path_part(puuid)}"
        data = await self._get_object_json(self._platform_url(path))
        return RiotSummoner.model_validate(data)

    async def get_ranked_entries_by_puuid(self, puuid: str) -> list[RiotLeagueEntry]:
        path = f"/lol/league/v4/entries/by-puuid/{self._path_part(puuid)}"
        data = await self._get_array_json(self._platform_url(path))
        return TypeAdapter(list[RiotLeagueEntry]).validate_python(data)

    async def get_match_ids_by_puuid(
        self,
        puuid: str,
        *,
        start: int = 0,
        count: int = 20,
        queue: int | None = None,
    ) -> list[str]:
        path = f"/lol/match/v5/matches/by-puuid/{self._path_part(puuid)}/ids"
        params: dict[str, int] = {"start": start, "count": count}
        if queue is not None:
            params["queue"] = queue

        data = await self._get_array_json(self._regional_url(path), params=params)
        return TypeAdapter(list[str]).validate_python(data)

    async def get_match(self, match_id: str) -> RiotMatch:
        path = f"/lol/match/v5/matches/{self._path_part(match_id)}"
        data = await self._get_object_json(self._regional_url(path))
        match = RiotMatch.model_validate(data)
        match.raw_json = data
        return match

    async def _get_object_json(
        self,
        url: str,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = await self._get_json(url, params=params)
        if not isinstance(data, dict):
            raise RiotClientError("Riot API returned an unexpected JSON response")
        return data

    async def _get_array_json(
        self,
        url: str,
        params: Mapping[str, Any] | None = None,
    ) -> list[Any]:
        data = await self._get_json(url, params=params)
        if not isinstance(data, list):
            raise RiotClientError("Riot API returned an unexpected JSON response")
        return data

    async def _get_json(
        self,
        url: str,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any] | list[Any]:
        if not self._api_key:
            raise RiotConfigurationError("RIOT_API_KEY is not configured")

        try:
            response = await self._http_client.get(
                url,
                headers={"X-Riot-Token": self._api_key},
                params=params,
            )
        except httpx.HTTPError as exc:
            raise RiotClientError(f"Riot API request failed: {exc.__class__.__name__}") from exc

        if response.is_error:
            raise self._api_error(response)

        try:
            data = response.json()
        except ValueError as exc:
            raise RiotClientError("Riot API returned a non-JSON response") from exc

        if not isinstance(data, dict | list):
            raise RiotClientError("Riot API returned an unexpected JSON response")

        return data

    def _api_error(self, response: httpx.Response) -> RiotApiError:
        retry_after = self._retry_after(response)
        message = response.reason_phrase

        try:
            error_payload = response.json()
        except ValueError:
            error_payload = None

        if isinstance(error_payload, dict):
            status_payload = error_payload.get("status")
            if isinstance(status_payload, dict):
                payload_message = status_payload.get("message")
                if isinstance(payload_message, str) and payload_message:
                    message = payload_message

        return RiotApiError(
            status_code=response.status_code,
            message=message,
            retry_after=retry_after,
        )

    def _retry_after(self, response: httpx.Response) -> int | None:
        value = response.headers.get("Retry-After")
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    def _regional_url(self, path: str) -> str:
        return f"https://{self._region}.api.riotgames.com{path}"

    def _platform_url(self, path: str) -> str:
        return f"https://{self._platform}.api.riotgames.com{path}"

    def _path_part(self, value: str) -> str:
        return quote(value, safe="")
