"""요청 횟수 제한 어댑터.

`InMemoryRateLimiter` 는 프로세스 안에서만 센다(테스트용). 운영은 여러 프로세스가 같은 숫자를 보는
`RedisRateLimiter` 를 쓴다.
"""

import math
import time
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Callable

from redis.asyncio import Redis


class RateLimiter(ABC):
    @abstractmethod
    async def hit(self, key: str, *, limit: int, window_seconds: int) -> int | None:
        """시도를 한 번 기록한다. 허용되면 None, 초과면 다시 시도할 수 있을 때까지의 초."""

    @abstractmethod
    async def count(self, key: str, *, window_seconds: int) -> int:
        """기록하지 않고 현재 window 안의 시도 수만 읽는다."""


class InMemoryRateLimiter(RateLimiter):
    """sliding window log 방식. 거부된 시도는 기록하지 않는다."""

    _SWEEP_EVERY = 1000

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._calls = 0
        self._longest_window = 0

    async def hit(self, key: str, *, limit: int, window_seconds: int) -> int | None:
        now = self._clock()
        self._longest_window = max(self._longest_window, window_seconds)
        self._maybe_sweep(now)

        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= now - window_seconds:
            hits.popleft()

        if len(hits) >= limit:
            return max(1, math.ceil(hits[0] + window_seconds - now))

        hits.append(now)
        return None

    async def count(self, key: str, *, window_seconds: int) -> int:
        now = self._clock()
        return sum(1 for hit in self._hits.get(key, ()) if hit > now - window_seconds)

    def _maybe_sweep(self, now: float) -> None:
        """오래 쓰이지 않은 key 가 메모리에 계속 남지 않도록 주기적으로 지운다."""
        self._calls += 1
        if self._calls % self._SWEEP_EVERY:
            return
        cutoff = now - self._longest_window
        expired = [key for key, hits in self._hits.items() if not hits or hits[-1] <= cutoff]
        for key in expired:
            del self._hits[key]


class RedisRateLimiter(RateLimiter):
    """fixed window 방식. 첫 시도 때 window 가 시작되고 만료되면 0 부터 다시 센다.

    INCR 과 EXPIRE 를 한 트랜잭션으로 보내 여러 프로세스가 동시에 세도 숫자가 어긋나지 않는다.
    거부된 시도도 세므로, 한도를 넘긴 뒤 계속 두드리면 window 가 끝날 때까지 계속 거부된다.
    """

    _PREFIX = "ratelimit:"

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def hit(self, key: str, *, limit: int, window_seconds: int) -> int | None:
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.incr(self._PREFIX + key)
            pipe.expire(self._PREFIX + key, window_seconds, nx=True)
            pipe.ttl(self._PREFIX + key)
            count, _, ttl = await pipe.execute()
        if count > limit:
            return max(1, ttl)
        return None

    async def count(self, key: str, *, window_seconds: int) -> int:
        value = await self._redis.get(self._PREFIX + key)
        return int(value or 0)
