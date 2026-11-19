from src.infrastructure.rate_limit import InMemoryRateLimiter


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


async def test_blocks_after_limit_and_reports_retry_after() -> None:
    clock = _Clock()
    limiter = InMemoryRateLimiter(clock)

    results = [await limiter.hit("k", limit=3, window_seconds=60) for _ in range(4)]

    assert results[:3] == [None, None, None]
    assert results[3] == 60


async def test_allows_again_after_window_passes() -> None:
    clock = _Clock()
    limiter = InMemoryRateLimiter(clock)
    for _ in range(3):
        await limiter.hit("k", limit=3, window_seconds=60)

    clock.now += 60

    assert await limiter.hit("k", limit=3, window_seconds=60) is None


async def test_keys_are_counted_separately() -> None:
    limiter = InMemoryRateLimiter(_Clock())
    await limiter.hit("a", limit=1, window_seconds=60)

    assert await limiter.hit("b", limit=1, window_seconds=60) is None
