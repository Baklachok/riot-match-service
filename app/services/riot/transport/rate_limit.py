import asyncio
import time


class TokenBucket:
    def __init__(self, rate_per_second: float, capacity: int) -> None:
        self._rate_per_second = max(0.1, rate_per_second)
        self._capacity = float(max(1, capacity))
        self._tokens = self._capacity
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


class HostRateLimiter:
    def __init__(self, rate_per_second: float, capacity: int) -> None:
        self._rate_per_second = max(0.1, rate_per_second)
        self._capacity = max(1, capacity)
        self._buckets_by_host: dict[str, TokenBucket] = {}
        self._buckets_lock = asyncio.Lock()

    async def acquire(self, host: str) -> None:
        bucket = await self._bucket_for_host(host)
        await bucket.acquire()

    async def _bucket_for_host(self, host: str) -> TokenBucket:
        bucket = self._buckets_by_host.get(host)
        if bucket is not None:
            return bucket

        async with self._buckets_lock:
            bucket = self._buckets_by_host.get(host)
            if bucket is None:
                bucket = TokenBucket(
                    rate_per_second=self._rate_per_second,
                    capacity=self._capacity,
                )
                self._buckets_by_host[host] = bucket
        return bucket
