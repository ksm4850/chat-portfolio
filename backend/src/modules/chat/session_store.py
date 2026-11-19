"""방문자 대화방(세션)과 최근 대화 저장소.

운영은 Redis 에 두고 마지막 대화 뒤 TTL 이 지나면 사라진다. 최근 `max_turns` 턴만 남긴다.
"""

import json
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass

from redis.asyncio import Redis

from src.infrastructure.llm import ChatMessage


@dataclass(frozen=True)
class ChatSession:
    character_id: uuid.UUID
    visitor_id: uuid.UUID
    messages: list[ChatMessage]


class SessionStore(ABC):
    @abstractmethod
    async def create(self, character_id: uuid.UUID, visitor_id: uuid.UUID) -> uuid.UUID: ...

    @abstractmethod
    async def get(self, session_id: uuid.UUID) -> ChatSession | None: ...

    @abstractmethod
    async def append(self, session_id: uuid.UUID, *messages: ChatMessage) -> None: ...

    @abstractmethod
    async def delete(self, session_id: uuid.UUID) -> bool: ...


class InMemorySessionStore(SessionStore):
    """테스트용. TTL 없이 프로세스가 끝나면 사라진다."""

    def __init__(self, max_turns: int = 10) -> None:
        self._max_messages = max_turns * 2
        self._sessions: dict[uuid.UUID, ChatSession] = {}

    async def create(self, character_id: uuid.UUID, visitor_id: uuid.UUID) -> uuid.UUID:
        session_id = uuid.uuid4()
        self._sessions[session_id] = ChatSession(character_id, visitor_id, [])
        return session_id

    async def get(self, session_id: uuid.UUID) -> ChatSession | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        return ChatSession(session.character_id, session.visitor_id, list(session.messages))

    async def append(self, session_id: uuid.UUID, *messages: ChatMessage) -> None:
        session = self._sessions[session_id]
        session.messages.extend(messages)
        del session.messages[: -self._max_messages]

    async def delete(self, session_id: uuid.UUID) -> bool:
        return self._sessions.pop(session_id, None) is not None


class RedisSessionStore(SessionStore):
    """`chat:session:{id}` 해시에 소유 정보, `...:messages` 리스트에 최근 대화를 둔다."""

    def __init__(self, redis: Redis, ttl_seconds: int, max_turns: int) -> None:
        self._redis = redis
        self._ttl = ttl_seconds
        # 한 턴 = 방문자 발화 + 응답
        self._max_messages = max_turns * 2

    async def create(self, character_id: uuid.UUID, visitor_id: uuid.UUID) -> uuid.UUID:
        session_id = uuid.uuid4()
        meta = self._meta_key(session_id)
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.hset(
                meta, mapping={"character_id": str(character_id), "visitor_id": str(visitor_id)}
            )
            pipe.expire(meta, self._ttl)
            await pipe.execute()
        return session_id

    async def get(self, session_id: uuid.UUID) -> ChatSession | None:
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.hgetall(self._meta_key(session_id))
            pipe.lrange(self._messages_key(session_id), 0, -1)
            meta, raw_messages = await pipe.execute()
        if not meta:
            return None
        return ChatSession(
            character_id=uuid.UUID(meta["character_id"]),
            visitor_id=uuid.UUID(meta["visitor_id"]),
            messages=[ChatMessage(**json.loads(raw)) for raw in raw_messages],
        )

    async def append(self, session_id: uuid.UUID, *messages: ChatMessage) -> None:
        key = self._messages_key(session_id)
        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.rpush(
                key,
                *(
                    json.dumps({"role": m.role, "content": m.content}, ensure_ascii=False)
                    for m in messages
                ),
            )
            pipe.ltrim(key, -self._max_messages, -1)
            # 대화가 이어지는 동안에는 세션이 사라지지 않게 TTL 을 다시 건다.
            pipe.expire(key, self._ttl)
            pipe.expire(self._meta_key(session_id), self._ttl)
            await pipe.execute()

    async def delete(self, session_id: uuid.UUID) -> bool:
        deleted = await self._redis.delete(
            self._meta_key(session_id), self._messages_key(session_id)
        )
        return deleted > 0

    @staticmethod
    def _meta_key(session_id: uuid.UUID) -> str:
        return f"chat:session:{session_id}"

    @staticmethod
    def _messages_key(session_id: uuid.UUID) -> str:
        return f"chat:session:{session_id}:messages"
