import asyncio
import random
import time
from collections.abc import Mapping
from typing import Any, cast
from urllib.parse import urlsplit

import httpx

from app.services.riot.endpoints import ResponseKind
from app.services.riot.errors import RiotApiError, RiotClientError, RiotConfigurationError


class _TokenBucket:
    def __init__(self, rate_per_second: float, capacity: int) -> None:
        self._rate_per_second = rate_per_second
        self._capacity = float(capacity)
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> None:
        while True:
            sleep_for = 0.0
            async with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                deficit = tokens - self._tokens
                sleep_for = deficit / self._rate_per_second

            await asyncio.sleep(sleep_for)

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        if elapsed <= 0:
            return
        self._tokens = min(self._capacity, self._tokens + elapsed * self._rate_per_second)
        self._last_refill = now


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
        self._max_retries: int = max(0, max_retries)
        self._backoff_base_seconds: float = max(0.0, backoff_base_seconds)
        self._rate_limit_rps: float = max(0.1, rate_limit_rps)
        self._rate_limit_capacity: int = max(1, rate_limit_capacity)
        self._buckets_by_host: dict[str, _TokenBucket] = {}
        self._buckets_lock: asyncio.Lock = asyncio.Lock()

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
        attempt = 0
        while True:
            attempt += 1
            await self._acquire_host_token(host)

            response = await self._send_request(url=url, params=params)
            if not response.is_error:
                return self._parse_success_payload(response=response, response_kind=response_kind)

            error = self._build_api_error(response=response, host=host, attempt=attempt)

            if error.status_code == 403:
                raise RiotApiError(
                    status_code=403,
                    message="Invalid or expired Riot API key",
                    retry_after=error.retry_after,
                    is_retryable=False,
                    host=host,
                    attempt=attempt,
                )

            if error.status_code == 404:
                raise error

            if error.status_code == 429:
                if self._can_retry(attempt):
                    await asyncio.sleep(float(error.retry_after or 1))
                    continue
                raise error

            if 500 <= error.status_code <= 599:
                if self._can_retry(attempt):
                    await asyncio.sleep(self._backoff_with_jitter(attempt))
                    continue
                raise error

            raise error

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

    def _parse_success_payload(
        self,
        *,
        response: httpx.Response,
        response_kind: ResponseKind,
    ) -> dict[str, Any] | list[Any]:
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

    def _build_api_error(
        self,
        *,
        response: httpx.Response,
        host: str,
        attempt: int,
    ) -> RiotApiError:
        retry_after = self._retry_after(response)
        message = self._response_message(response)
        status_code = response.status_code
        is_retryable = status_code == 429 or 500 <= status_code <= 599

        return RiotApiError(
            status_code=status_code,
            message=message,
            retry_after=retry_after,
            is_retryable=is_retryable,
            host=host,
            attempt=attempt,
        )

    def _retry_after(self, response: httpx.Response) -> int | None:
        value = response.headers.get("Retry-After")
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    def _response_message(self, response: httpx.Response) -> str:
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
                    return payload_message
        return message

    def _can_retry(self, attempt: int) -> bool:
        return attempt <= self._max_retries

    def _backoff_with_jitter(self, attempt: int) -> float:
        base = self._backoff_base_seconds * (2 ** (attempt - 1))
        jitter = cast(float, random.uniform(0.0, 0.1))
        return float(base + jitter)

    def _host_for_url(self, url: str) -> str:
        parsed = urlsplit(url)
        return parsed.netloc or "unknown-host"

    async def _acquire_host_token(self, host: str) -> None:
        bucket = await self._bucket_for_host(host)
        await bucket.acquire()

    async def _bucket_for_host(self, host: str) -> _TokenBucket:
        bucket = self._buckets_by_host.get(host)
        if bucket is not None:
            return bucket

        async with self._buckets_lock:
            bucket = self._buckets_by_host.get(host)
            if bucket is None:
                bucket = _TokenBucket(
                    rate_per_second=self._rate_limit_rps,
                    capacity=self._rate_limit_capacity,
                )
                self._buckets_by_host[host] = bucket
        return bucket
