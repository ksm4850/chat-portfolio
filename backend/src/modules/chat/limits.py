"""방문자 대화 사용량 제한. 과금 없이 한 사람·한 IP·전체가 쓰는 양을 묶는다."""

import uuid
from dataclasses import dataclass

from src.infrastructure.rate_limit import RateLimiter
from src.modules.chat.exceptions import ChatLimitExceededError

_HOUR = 3600
_DAY = 86_400
GLOBAL_LLM_KEY = "chat:llm:global"

# (key, limit, window_seconds, code, message)
type _Check = tuple[str, int, int, str, str]


@dataclass(frozen=True)
class ChatLimits:
    message_max_length: int
    min_interval_seconds: int
    messages_per_session: int
    messages_per_visitor_per_day: int
    messages_per_ip_per_hour: int
    llm_calls_per_day: int
    session_ttl_seconds: int


class ChatUsageGuard:
    """좁은 범위부터 확인한다. 앞에서 거부되면 뒤의 카운터는 늘지 않는다."""

    def __init__(self, rate_limiter: RateLimiter, limits: ChatLimits) -> None:
        self._limiter = rate_limiter
        self._limits = limits

    async def check(self, session_id: uuid.UUID, visitor_id: uuid.UUID, client_ip: str) -> None:
        limits = self._limits
        await self._hit_all(
            [
                self._interval(visitor_id),
                (
                    f"chat:session:{session_id}",
                    limits.messages_per_session,
                    limits.session_ttl_seconds,
                    "session_message_limit",
                    "이 대화에서 보낼 수 있는 메시지를 다 썼어요. 새 대화를 시작해 주세요.",
                ),
                *self._visitor_and_ip(visitor_id, client_ip),
                self._global_llm(),
            ]
        )

    async def check_visitor(self, visitor_id: uuid.UUID, client_ip: str) -> None:
        """세션 없이 방문자·IP 한도만 본다. 전체 LLM 호출 수는 `try_llm_call` 이 따로 센다."""
        await self._hit_all(
            [self._interval(visitor_id), *self._visitor_and_ip(visitor_id, client_ip)]
        )

    async def try_llm_call(self) -> bool:
        """전체 일일 LLM 호출 수를 하나 쓴다. 한도를 넘었으면 False."""
        key, limit, window, _, _ = self._global_llm()
        return await self._limiter.hit(key, limit=limit, window_seconds=window) is None

    async def _hit_all(self, checks: list[_Check]) -> None:
        for key, limit, window, code, message in checks:
            retry_after = await self._limiter.hit(key, limit=limit, window_seconds=window)
            if retry_after is not None:
                # 세션 한도는 기다려도 풀리지 않으므로 Retry-After 를 주지 않는다.
                wait = None if code == "session_message_limit" else retry_after
                raise ChatLimitExceededError(code, message, wait)

    def _interval(self, visitor_id: uuid.UUID) -> _Check:
        return (
            f"chat:interval:visitor:{visitor_id}",
            1,
            self._limits.min_interval_seconds,
            "chat_too_fast",
            "조금 천천히 보내 주세요.",
        )

    def _visitor_and_ip(self, visitor_id: uuid.UUID, client_ip: str) -> list[_Check]:
        return [
            (
                f"chat:visitor:{visitor_id}",
                self._limits.messages_per_visitor_per_day,
                _DAY,
                "visitor_daily_limit",
                "오늘 대화할 수 있는 양을 다 썼어요. 내일 다시 와 주세요.",
            ),
            (
                f"chat:ip:{client_ip}",
                self._limits.messages_per_ip_per_hour,
                _HOUR,
                "ip_hourly_limit",
                "요청이 너무 많아요. 잠시 후 다시 시도해 주세요.",
            ),
        ]

    def _global_llm(self) -> _Check:
        return (
            GLOBAL_LLM_KEY,
            self._limits.llm_calls_per_day,
            _DAY,
            "daily_quota_exceeded",
            "오늘은 답변이 어려워요. 메일로 연락 주세요.",
        )

    async def llm_calls_today(self) -> int:
        return await self._limiter.count(GLOBAL_LLM_KEY, window_seconds=_DAY)
