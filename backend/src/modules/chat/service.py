import time
import uuid
from collections.abc import AsyncIterator

from src.infrastructure.llm import ChatMessage, LLMClient, LLMError
from src.infrastructure.logging import get_logger
from src.modules.character.schema import CharacterPublic
from src.modules.character.service import CharacterService
from src.modules.chat.exceptions import (
    ChatSessionNotFoundError,
    MessageTooLongError,
    ReplyFailedError,
)
from src.modules.chat.limits import ChatLimits, ChatUsageGuard
from src.modules.chat.schema import HistoryMessage, ReplyContext, SessionCreated, UsageRead
from src.modules.chat.session_store import ChatSession, SessionStore
from src.modules.knowledge.service import KnowledgeService

logger = get_logger(__name__)


class ChatService:
    """방문자 발화 → 사용량 확인 → 기억 검색 → 캐릭터 프롬프트 → LLM 스트리밍.

    세션은 만든 방문자만 쓸 수 있다. 남의 세션은 없는 것처럼 404 로 숨긴다.
    """

    def __init__(
        self,
        llm: LLMClient,
        knowledge_service: KnowledgeService,
        character_service: CharacterService,
        session_store: SessionStore,
        usage_guard: ChatUsageGuard,
        limits: ChatLimits,
        rag_top_k: int,
        history_turns: int,
    ) -> None:
        self._llm = llm
        self._knowledge = knowledge_service
        self._characters = character_service
        self._sessions = session_store
        self._guard = usage_guard
        self._limits = limits
        self._rag_top_k = rag_top_k
        self._history_turns = history_turns

    async def create_session(self, character_slug: str, visitor_id: uuid.UUID) -> SessionCreated:
        character = await self._characters.get_public_character(character_slug)
        session_id = await self._sessions.create(character.id, visitor_id)
        logger.info(
            "대화 시작",
            extra={
                "session_id": str(session_id),
                "visitor_id": str(visitor_id),
                "character_id": str(character.id),
            },
        )
        return SessionCreated(
            session_id=session_id, character=CharacterPublic.model_validate(character)
        )

    async def delete_session(self, session_id: uuid.UUID, visitor_id: uuid.UUID) -> None:
        await self._owned(session_id, visitor_id)
        await self._sessions.delete(session_id)

    async def get_history(
        self, session_id: uuid.UUID, visitor_id: uuid.UUID
    ) -> list[HistoryMessage]:
        session = await self._owned(session_id, visitor_id)
        return [HistoryMessage(role=m.role, content=m.content) for m in session.messages]

    async def reply(
        self, session_id: uuid.UUID, visitor_id: uuid.UUID, client_ip: str, text: str
    ) -> AsyncIterator[str]:
        """응답 스트림을 돌려준다.

        세션 확인·사용량 확인·검색·프롬프트 조립은 여기서 끝낸다.
        실패하면 스트림을 열기 전에 예외가 나서 일반 HTTP 오류로 응답된다.
        """
        text = text.strip()
        if len(text) > self._limits.message_max_length:
            raise MessageTooLongError(self._limits.message_max_length)
        session = await self._owned(session_id, visitor_id)
        await self._guard.check(session_id, visitor_id, client_ip)
        context, messages = await self._prepare(session_id, session, text)
        return self._stream(session_id, context.system_prompt, messages)

    async def create_test_session(
        self, character_id: uuid.UUID, admin_id: uuid.UUID
    ) -> SessionCreated:
        """관리자 테스트용. 비공개 캐릭터와도 대화할 수 있다."""
        character = await self._characters.get(character_id)
        session_id = await self._sessions.create(character.id, admin_id)
        return SessionCreated(
            session_id=session_id, character=CharacterPublic.model_validate(character)
        )

    async def test_reply(
        self, session_id: uuid.UUID, admin_id: uuid.UUID, text: str
    ) -> tuple[ReplyContext, AsyncIterator[str]]:
        """관리자 테스트용. 사용량 제한을 거치지 않고, 검색된 기억과 프롬프트를 함께 돌려준다."""
        session = await self._owned(session_id, admin_id)
        context, messages = await self._prepare(session_id, session, text.strip())
        return context, self._stream(session_id, context.system_prompt, messages)

    async def _prepare(
        self, session_id: uuid.UUID, session: ChatSession, text: str
    ) -> tuple[ReplyContext, list[ChatMessage]]:
        hits = await self._knowledge.search(session.character_id, text, limit=self._rag_top_k)
        system = await self._characters.system_prompt(
            session.character_id, [hit.content for hit in hits]
        )
        recent = session.messages[-self._history_turns * 2 :] if self._history_turns else []

        logger.info(
            "기억 검색",
            extra={"session_id": str(session_id), "scores": [round(h.score, 3) for h in hits]},
        )
        context = ReplyContext(memories=hits, system_prompt=system)
        return context, [*recent, ChatMessage("user", text)]

    async def usage(self) -> UsageRead:
        return UsageRead(
            llm_calls_today=await self._guard.llm_calls_today(),
            llm_calls_per_day=self._limits.llm_calls_per_day,
        )

    async def _stream(
        self, session_id: uuid.UUID, system: str, messages: list[ChatMessage]
    ) -> AsyncIterator[str]:
        started = time.perf_counter()
        first_token_ms: float | None = None
        parts: list[str] = []
        try:
            async for delta in self._llm.stream(system, messages):
                if first_token_ms is None:
                    first_token_ms = round((time.perf_counter() - started) * 1000, 1)
                parts.append(delta)
                yield delta
        except LLMError as exc:
            logger.warning(
                "응답 생성 실패", extra={"session_id": str(session_id), "error": str(exc)}
            )
            raise ReplyFailedError() from exc

        await self._sessions.append(
            session_id, messages[-1], ChatMessage("assistant", "".join(parts))
        )
        logger.info(
            "응답 완료",
            extra={
                "session_id": str(session_id),
                "first_token_ms": first_token_ms,
                "total_ms": round((time.perf_counter() - started) * 1000, 1),
            },
        )

    async def _owned(self, session_id: uuid.UUID, visitor_id: uuid.UUID) -> ChatSession:
        session = await self._sessions.get(session_id)
        if session is None or session.visitor_id != visitor_id:
            raise ChatSessionNotFoundError()
        return session
