import random
from typing import cast

from app.services.riot.errors import RiotApiError


class RiotRetryPolicy:
    def __init__(self, max_retries: int, backoff_base_seconds: float) -> None:
        self._max_retries = max(0, max_retries)
        self._backoff_base_seconds = max(0.0, backoff_base_seconds)

    @property
    def total_attempts(self) -> int:
        # One initial call plus max_retries retries.
        return self._max_retries + 1

    def normalize_error(self, error: RiotApiError) -> RiotApiError:
        if error.status_code != 403:
            return error

        return RiotApiError(
            status_code=403,
            message="Invalid or expired Riot API key",
            retry_after=error.retry_after,
            is_retryable=False,
            host=error.host,
            attempt=error.attempt,
        )

    def should_retry(self, error: RiotApiError, attempt: int) -> bool:
        if attempt >= self.total_attempts:
            return False
        if error.status_code in {403, 404}:
            return False
        return error.status_code == 429 or 500 <= error.status_code <= 599

    def retry_delay_seconds(self, error: RiotApiError, attempt: int) -> float:
        if error.status_code == 429:
            return self._retry_after_delay(error.retry_after)
        return self._backoff_with_jitter(attempt)

    def _retry_after_delay(self, retry_after: int | None) -> float:
        if retry_after is None or retry_after <= 0:
            return 1.0
        return float(retry_after)

    def _backoff_with_jitter(self, attempt: int) -> float:
        base = self._backoff_base_seconds * (2 ** (attempt - 1))
        jitter = cast(float, random.uniform(0.0, 0.1))
        return float(base + jitter)
