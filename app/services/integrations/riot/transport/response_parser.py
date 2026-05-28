from typing import Any, cast

import httpx

from app.services.integrations.riot.errors import RiotApiError, RiotClientError
from app.services.integrations.riot.routing import ResponseKind


class RiotResponseParser:
    def parse_success_payload(
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

    def build_api_error(
        self,
        *,
        response: httpx.Response,
        host: str,
        attempt: int,
    ) -> RiotApiError:
        payload = self._decode_json_or_none(response)
        status_code = response.status_code

        return RiotApiError(
            status_code=status_code,
            message=self._response_message(response=response, payload=payload),
            retry_after=self._retry_after(response),
            is_retryable=status_code == 429 or 500 <= status_code <= 599,
            host=host,
            attempt=attempt,
        )

    def _decode_json(self, response: httpx.Response) -> object:
        try:
            return response.json()
        except ValueError as exc:
            raise RiotClientError("Riot API returned a non-JSON response") from exc

    def _decode_json_or_none(self, response: httpx.Response) -> object | None:
        try:
            return cast(object, response.json())
        except ValueError:
            return None

    def _response_message(self, *, response: httpx.Response, payload: object | None) -> str:
        if isinstance(payload, dict):
            status_payload = payload.get("status")
            if isinstance(status_payload, dict):
                payload_message = status_payload.get("message")
                if isinstance(payload_message, str) and payload_message:
                    return payload_message
        return response.reason_phrase

    def _retry_after(self, response: httpx.Response) -> int | None:
        value = response.headers.get("Retry-After")
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None
