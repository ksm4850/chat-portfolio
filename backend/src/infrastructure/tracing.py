"""LLM 호출 추적(Langfuse). 키가 없으면 아무것도 보내지 않는 구현을 쓴다.

추적은 부가 기능이다. SDK 오류는 여기서 잡아 경고만 남기고 서비스로 올리지 않는다.
SDK 는 기록을 모아 백그라운드에서 보내므로 응답 시간에 끼어들지 않는다.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal

from src.infrastructure.llm import TokenUsage
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

type StepKind = Literal["span", "retriever", "generation"]


class Step(ABC):
    """trace 안의 한 단계(검색, LLM 생성 등)."""

    @abstractmethod
    def first_token(self) -> None:
        """생성 단계에서 첫 토큰이 나온 시각을 남긴다."""

    @abstractmethod
    def end(
        self,
        *,
        output: Any = None,
        usage: TokenUsage | None = None,
        error: str | None = None,
    ) -> None: ...


class Trace(ABC):
    """요청 하나(질문 하나와 답변)의 추적."""

    @property
    @abstractmethod
    def trace_id(self) -> str | None: ...

    @abstractmethod
    def step(self, name: str, *, kind: StepKind, input: Any, model: str | None = None) -> Step: ...

    @abstractmethod
    def end(
        self,
        *,
        output: Any = None,
        metadata: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None: ...


class Tracer(ABC):
    @abstractmethod
    def start(
        self,
        name: str,
        *,
        user_id: str,
        session_id: str | None,
        input: Any,
        metadata: dict[str, str],
    ) -> Trace: ...

    @abstractmethod
    def shutdown(self) -> None:
        """남은 기록을 보내고 정리한다. 앱이 끝날 때 부른다."""


class _NoopStep(Step):
    def first_token(self) -> None:
        pass

    def end(self, *, output=None, usage=None, error=None) -> None:
        pass


class _NoopTrace(Trace):
    @property
    def trace_id(self) -> str | None:
        return None

    def step(self, name, *, kind, input, model=None) -> Step:
        return _NoopStep()

    def end(self, *, output=None, metadata=None, error=None) -> None:
        pass


class NoopTracer(Tracer):
    def start(self, name, *, user_id, session_id, input, metadata) -> Trace:
        return _NoopTrace()

    def shutdown(self) -> None:
        pass


def _safe[T](action: Callable[[], T], fallback: T) -> T:
    try:
        return action()
    except Exception:
        logger.warning("추적 기록 실패", exc_info=True)
        return fallback


class _LangfuseStep(Step):
    def __init__(self, observation: Any) -> None:
        self._observation = observation

    def first_token(self) -> None:
        _safe(lambda: self._observation.update(completion_start_time=datetime.now(UTC)), None)

    def end(self, *, output=None, usage=None, error=None) -> None:
        def run() -> None:
            fields: dict[str, Any] = {"output": output}
            if usage is not None:
                fields["usage_details"] = _usage_details(usage)
            if error:
                fields.update(level="ERROR", status_message=error)
            self._observation.update(**fields)
            self._observation.end()

        _safe(run, None)


class _LangfuseTrace(Trace):
    def __init__(self, root: Any, attributes: Callable[[], Any]) -> None:
        self._root = root
        self._attributes = attributes

    @property
    def trace_id(self) -> str | None:
        return self._root.trace_id

    def step(self, name, *, kind, input, model=None) -> Step:
        def run() -> Step:
            with self._attributes():
                observation = self._root.start_observation(
                    name=name, as_type=kind, input=input, model=model
                )
            return _LangfuseStep(observation)

        return _safe(run, _NoopStep())

    def end(self, *, output=None, metadata=None, error=None) -> None:
        def run() -> None:
            fields: dict[str, Any] = {"output": output, "metadata": metadata}
            if error:
                fields.update(level="ERROR", status_message=error)
            self._root.update(**fields)
            self._root.end()

        _safe(run, None)


class LangfuseTracer(Tracer):
    def __init__(self, public_key: str, secret_key: str, base_url: str, environment: str) -> None:
        from langfuse import Langfuse

        self._client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            base_url=base_url or None,
            environment=environment,
        )

    def start(self, name, *, user_id, session_id, input, metadata) -> Trace:
        from langfuse import propagate_attributes

        # trace 단위 속성은 이 컨텍스트 안에서 만든 observation 에만 붙는다.
        def attributes():
            return propagate_attributes(
                user_id=user_id, session_id=session_id, trace_name=name, metadata=metadata
            )

        def run() -> Trace:
            with attributes():
                root = self._client.start_observation(name=name, input=input)
            return _LangfuseTrace(root, attributes)

        return _safe(run, _NoopTrace())

    def shutdown(self) -> None:
        _safe(self._client.shutdown, None)


def _usage_details(usage: TokenUsage) -> dict[str, int]:
    # Langfuse 는 키별로 단가를 매긴다. 하위 항목(캐시 입력, 추론 출력)은 상위에서 빼서 따로 적는다.
    details = {
        "input": _minus(usage.input_tokens, usage.cached_tokens),
        "input_cached_tokens": usage.cached_tokens,
        "output": _minus(usage.output_tokens, usage.reasoning_tokens),
        "output_reasoning": usage.reasoning_tokens,
    }
    return {key: value for key, value in details.items() if value is not None}


def _minus(total: int | None, part: int | None) -> int | None:
    return total - part if total is not None and part else total


def create_tracer(public_key: str, secret_key: str, base_url: str, environment: str) -> Tracer:
    if not (public_key and secret_key):
        return NoopTracer()
    return LangfuseTracer(public_key, secret_key, base_url, environment)
