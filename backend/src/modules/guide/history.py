"""안내 대화의 최근 턴. 다음 질문의 맥락으로 LLM 에 넣는다.

운영은 Redis 에 두고 마지막 대화 뒤 TTL 이 지나면 사라진다. 최근 `max_turns` 턴만 남긴다.
관리자 확인용 기록(guide_logs)과는 따로다.
"""

import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass

from redis.asyncio import Redis

from src.infrastructure.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class GuideTurn:
    question: str
    # 위치 표시를 걷어낸 답변. 표시한 위치는 anchors(`view:career` 형식 포함)에 있다.
    answer: str
    anchors: list[str]


class GuideHistory(ABC):
    """대화는 방문자와 thread 로 찾는다. 다른 방문자의 thread 는 읽을 수 없다."""

    @abstractmethod
    async def recent(self, visitor_id: uuid.UUID, thread_id: str) -> list[GuideTurn]:
        """오래된 순."""

    @abstractmethod
    async def append(self, visitor_id: uuid.UUID, thread_id: str, turn: GuideTurn) -> None: ...


class InMemoryGuideHistory(GuideHistory):
    """테스트용. TTL 없이 프로세스가 끝나면 사라진다."""

    def __init__(self, max_turns: int = 8) -> None:
        self._max_turns = max_turns
        self._turns: dict[tuple[uuid.UUID, str], list[GuideTurn]] = {}

    async def recent(self, visitor_id: uuid.UUID, thread_id: str) -> list[GuideTurn]:
        return list(self._turns.get((visitor_id, thread_id), []))

    async def append(self, visitor_id: uuid.UUID, thread_id: str, turn: GuideTurn) -> None:
        turns = self._turns.setdefault((visitor_id, thread_id), [])
        turns.append(turn)
        del turns[: -self._max_turns]


class RedisGuideHistory(GuideHistory):
    """`guide:history:{visitor_id}:{thread_id}` 리스트에 턴을 JSON 으로 쌓는다."""

    def __init__(self, redis: Redis, ttl_seconds: int, max_turns: int) -> None:
        self._redis = redis
        self._ttl = ttl_seconds
        self._max_turns = max_turns

    async def recent(self, visitor_id: uuid.UUID, thread_id: str) -> list[GuideTurn]:
        raw_turns = await self._redis.lrange(self._key(visitor_id, thread_id), 0, -1)
        turns = [_parse(raw) for raw in raw_turns]
        if None in turns:
            logger.warning("형식이 맞지 않는 대화 맥락을 건너뜀", extra={"thread_id": thread_id})
        return [turn for turn in turns if turn is not None]

    async def append(self, visitor_id: uuid.UUID, thread_id: str, turn: GuideTurn) -> None:
        key = self._key(visitor_id, thread_id)
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.rpush(key, json.dumps(asdict(turn), ensure_ascii=False))
            pipe.ltrim(key, -self._max_turns, -1)
            pipe.expire(key, self._ttl)
            await pipe.execute()

    @staticmethod
    def _key(visitor_id: uuid.UUID, thread_id: str) -> str:
        return f"guide:history:{visitor_id}:{thread_id}"


def _parse(raw: str | bytes) -> GuideTurn | None:
    """저장 형식이 바뀌어도 TTL 동안 남은 이전 항목 때문에 대화가 깨지지 않게 한다.

    모르는 키는 무시하고, 필요한 값이 없거나 형식이 다르면 None.
    """
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    question, answer, anchors = data.get("question"), data.get("answer"), data.get("anchors", [])
    if not (isinstance(question, str) and isinstance(answer, str) and isinstance(anchors, list)):
        return None
    return GuideTurn(question, answer, [a for a in anchors if isinstance(a, str)])
