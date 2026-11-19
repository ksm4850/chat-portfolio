from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["user", "assistant"]
    content: str


@dataclass
class TokenUsage:
    """호출 한 번의 토큰 사용량. 공급자가 알려 주기 전에 스트림이 끝나면 None 으로 남는다."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    # output_tokens 중 내부 추론에 쓴 양. 추론하지 않는 모델·공급자는 None.
    reasoning_tokens: int | None = None
    # input_tokens 중 프롬프트 캐시에서 읽은 양.
    cached_tokens: int | None = None


class LLMError(Exception):
    """LLM 호출 실패. 서비스는 이를 자기 도메인 예외로 번역한다."""


class LLMClient(ABC):
    # 추적·기록에 남길 모델 이름. 어댑터가 정한다.
    model: str = ""

    @abstractmethod
    def stream(
        self,
        system: str,
        messages: Sequence[ChatMessage],
        usage: TokenUsage | None = None,
        *,
        cache_key: str | None = None,
    ) -> AsyncIterator[str]:
        """응답 텍스트를 생성되는 대로 조각(delta) 단위로 돌려준다.

        `usage` 를 넘기면 스트림이 끝날 때 사용량을 채운다. 클라이언트는 여러 요청이 함께 쓰므로
        사용량을 클라이언트에 두지 않고 호출마다 받은 객체에 담는다.
        `cache_key` 는 프롬프트 앞부분이 같은 요청끼리 묶어 캐시를 잘 맞추게 하는 힌트다.
        지원하지 않는 공급자는 무시한다.
        """
