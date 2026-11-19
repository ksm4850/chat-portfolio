"""OpenAI Chat Completions 스트리밍 어댑터. 배포용."""

from collections.abc import AsyncIterator, Sequence

from openai import AsyncOpenAI, OpenAIError, omit

from src.infrastructure.llm.base import ChatMessage, LLMClient, LLMError, TokenUsage


class OpenAIChatClient(LLMClient):
    def __init__(
        self, api_key: str, model: str, max_output_tokens: int, timeout_seconds: float
    ) -> None:
        self._api_key = api_key
        self._model = model
        self.model = model
        self._max_output_tokens = max_output_tokens
        self._timeout_seconds = timeout_seconds
        # 키가 비어 있어도 앱이 뜨도록 클라이언트는 첫 호출 때 만든다.
        self._client: AsyncOpenAI | None = None

    async def stream(
        self,
        system: str,
        messages: Sequence[ChatMessage],
        usage: TokenUsage | None = None,
        *,
        cache_key: str | None = None,
    ) -> AsyncIterator[str]:
        if not self._api_key:
            raise LLMError("OPENAI_API_KEY 가 비어 있다")
        try:
            response = await self._get_client().chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    *({"role": m.role, "content": m.content} for m in messages),
                ],
                max_completion_tokens=self._max_output_tokens,
                stream=True,
                stream_options={"include_usage": True},
                prompt_cache_key=cache_key or omit,
            )
            async for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                # 사용량은 choices 가 빈 마지막 chunk 에만 온다.
                if usage is not None and getattr(chunk, "usage", None):
                    _fill(usage, chunk.usage)
        except OpenAIError as exc:
            raise LLMError(f"OpenAI 호출 실패: {type(exc).__name__}: {exc}") from exc

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self._api_key, timeout=self._timeout_seconds)
        return self._client


def _fill(usage: TokenUsage, reported) -> None:
    usage.input_tokens = reported.prompt_tokens
    usage.output_tokens = reported.completion_tokens
    details = getattr(reported, "completion_tokens_details", None)
    usage.reasoning_tokens = getattr(details, "reasoning_tokens", None)
    prompt_details = getattr(reported, "prompt_tokens_details", None)
    usage.cached_tokens = getattr(prompt_details, "cached_tokens", None)
