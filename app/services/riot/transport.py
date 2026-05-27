from collections.abc import Mapping
from typing import Any

import httpx

from app.services.riot.endpoints import ResponseKind
from app.services.riot.errors import RiotApiError, RiotClientError, RiotConfigurationError


class RiotTransport:
    def __init__(self, http_client: httpx.AsyncClient, api_key: str) -> None:
        self._http_client = http_client
        self._api_key = api_key.strip()

    async def get_json(
        self,
        url: str,
        *,
        response_kind: ResponseKind,
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

        payload = self._decode_json(response)
        if response_kind is ResponseKind.OBJECT:
            if not isinstance(payload, dict):
                raise RiotClientError("Riot API returned an unexpected JSON response")
            return payload

        if not isinstance(payload, list):
            raise RiotClientError("Riot API returned an unexpected JSON response")
        return payload

    def _decode_json(self, response: httpx.Response) -> object:
        try:
            return response.json()
        except ValueError as exc:
            raise RiotClientError("Riot API returned a non-JSON response") from exc

    def _api_error(self, response: httpx.Response) -> RiotApiError:
        retry_after = self._retry_after(response)
        message = response.reason_phrase

        try:
            payload = response.json()
        except ValueError:
            payload = None

        if isinstance(payload, dict):
            status_payload = payload.get("status")
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
