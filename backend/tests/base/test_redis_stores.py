"""Redis 구현 통합 검증. 로컬 Redis(docker compose)가 없으면 건너뛴다."""

import uuid
from collections.abc import AsyncIterator

import pytest

from src.core.config import Settings
from src.infrastructure.llm import ChatMessage
from src.infrastructure.rate_limit import RedisRateLimiter
from src.infrastructure.redis import create_redis
from src.modules.chat.session_store import RedisSessionStore
from src.modules.guide.history import GuideTurn, RedisGuideHistory

pytestmark = pytest.mark.integration


@pytest.fixture
async def redis() -> AsyncIterator:
    client = create_redis(Settings(_env_file=None).redis_url)
    try:
        await client.ping()
    except Exception as exc:
        await client.aclose()
        pytest.skip(f"Redis 를 쓸 수 없다: {type(exc).__name__}")
    yield client
    await client.aclose()


async def test_rate_limiter_counts_in_fixed_window(redis) -> None:
    limiter = RedisRateLimiter(redis)
    key = f"test:{uuid.uuid4()}"
    try:
        results = [await limiter.hit(key, limit=2, window_seconds=60) for _ in range(3)]

        assert results[:2] == [None, None]
        assert 0 < results[2] <= 60
        assert await limiter.count(key, window_seconds=60) == 3
        assert await redis.ttl(f"ratelimit:{key}") > 0
    finally:
        await redis.delete(f"ratelimit:{key}")


async def test_session_store_keeps_recent_turns_with_ttl(redis) -> None:
    store = RedisSessionStore(redis, ttl_seconds=60, max_turns=1)
    character_id, visitor_id = uuid.uuid4(), uuid.uuid4()
    session_id = await store.create(character_id, visitor_id)
    try:
        await store.append(
            session_id, ChatMessage("user", "첫 질문"), ChatMessage("assistant", "a")
        )
        await store.append(session_id, ChatMessage("user", "둘째"), ChatMessage("assistant", "b"))

        session = await store.get(session_id)
        assert session is not None
        assert (session.character_id, session.visitor_id) == (character_id, visitor_id)
        assert [m.content for m in session.messages] == ["둘째", "b"]
        assert 0 < await redis.ttl(f"chat:session:{session_id}:messages") <= 60
    finally:
        assert await store.delete(session_id) is True

    assert await store.get(session_id) is None


async def test_guide_history_keeps_recent_turns_per_visitor_thread(redis) -> None:
    history = RedisGuideHistory(redis, ttl_seconds=60, max_turns=2)
    visitor_id = uuid.uuid4()
    key = f"guide:history:{visitor_id}:t1"
    try:
        for i in range(3):
            await history.append(visitor_id, "t1", GuideTurn(f"질문 {i}", "답", ["view:career"]))

        assert await history.recent(visitor_id, "t1") == [
            GuideTurn("질문 1", "답", ["view:career"]),
            GuideTurn("질문 2", "답", ["view:career"]),
        ]
        assert await history.recent(uuid.uuid4(), "t1") == []
        assert 0 < await redis.ttl(key) <= 60
    finally:
        await redis.delete(key)
