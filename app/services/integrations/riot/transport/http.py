import asyncio
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.services.integrations.riot.errors import RiotClientError, RiotConfigurationError
from app.services.integrations.riot.routing import ResponseKind
from app.services.integrations.riot.transport.rate_limit import HostRateLimiter
from app.services.integrations.riot.transport.response_parser import RiotResponseParser
from app.services.integrations.riot.transport.retry_policy import RiotRetryPolicy


class RiotTransport:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        api_key: str,
        *,
        max_retries: int = 3,
        backoff_base_seconds: float = 0.5,
        rate_limit_rps: float = 20.0,
        rate_limit_capacity: int = 20,
    ) -> None:
        self._http_client: httpx.AsyncClient = http_client
        self._api_key: str = api_key.strip()
        self._rate_limiter = HostRateLimiter(
            rate_per_second=rate_limit_rps,
            capacity=rate_limit_capacity,
        )
        self._response_parser = RiotResponseParser()
        self._retry_policy = RiotRetryPolicy(
            max_retries=max_retries,
            backoff_base_seconds=backoff_base_seconds,
        )

    async def get_json(
        self,
        url: str,
        *,
        response_kind: ResponseKind,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any] | list[Any]:
        if not self._api_key:
            raise RiotConfigurationError("RIOT_API_KEY is not configured")

        host = self._host_for_url(url)
        for attempt in range(1, self._retry_policy.total_attempts + 1):
            await self._rate_limiter.acquire(host)

            response = await self._send_request(url=url, params=params)
            if not response.is_error:
                return self._response_parser.parse_success_payload(
                    response=response,
                    response_kind=response_kind,
                )

            error = self._response_parser.build_api_error(
                response=response,
                host=host,
                attempt=attempt,
            )
            normalized_error = self._retry_policy.normalize_error(error)
            if not self._retry_policy.should_retry(normalized_error, attempt):
                raise normalized_error

            delay = self._retry_policy.retry_delay_seconds(normalized_error, attempt)
            await asyncio.sleep(delay)

        raise RiotClientError("Riot API retry loop exited unexpectedly")

    async def _send_request(
        self,
        *,
        url: str,
        params: Mapping[str, Any] | None = None,
    ) -> httpx.Response:
        try:
            return await self._http_client.get(
                url,
                headers={"X-Riot-Token": self._api_key},
                params=params,
            )
        except httpx.HTTPError as exc:
            raise RiotClientError(f"Riot API request failed: {exc.__class__.__name__}") from exc

    @staticmethod
    def _host_for_url(url: str) -> str:
        parsed = urlsplit(url)
        return parsed.netloc or "unknown-host"
