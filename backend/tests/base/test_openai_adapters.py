"""OpenAI 어댑터. SDK 클라이언트를 가짜로 바꿔 네트워크 없이 응답 해석·오류 번역만 확인한다."""

import math
from types import SimpleNamespace

import pytest
from openai import APIConnectionError, omit

from src.infrastructure.embedding import EmbeddingError, OpenAIEmbedder
from src.infrastructure.llm import ChatMessage, LLMError, OpenAIChatClient, TokenUsage


def _chunk(text: str | None):
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=text))], usage=None
    )


USAGE_CHUNK = SimpleNamespace(
    choices=[],
    usage=SimpleNamespace(
        prompt_tokens=900,
        completion_tokens=60,
        completion_tokens_details=SimpleNamespace(reasoning_tokens=20),
        prompt_tokens_details=SimpleNamespace(cached_tokens=768),
    ),
)


class _Stream:
    def __init__(self, texts):
        self._texts = iter(texts)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            item = next(self._texts)
        except StopIteration as exc:
            raise StopAsyncIteration from exc
        return item if isinstance(item, SimpleNamespace) else _chunk(item)


class _Completions:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.kwargs: dict = {}

    async def create(self, **kwargs):
        self.kwargs = kwargs
        if self.fail:
            raise APIConnectionError(request=None)
        return _Stream(["안녕", None, "하세요", USAGE_CHUNK])


async def test_chat_streams_text_deltas_with_system_prompt() -> None:
    client = OpenAIChatClient("key", model="m", max_output_tokens=50, timeout_seconds=5)
    completions = _Completions()
    client._client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

    parts = [p async for p in client.stream("시스템", [ChatMessage("user", "hi")])]

    assert parts == ["안녕", "하세요"]
    assert completions.kwargs["messages"][0] == {"role": "system", "content": "시스템"}
    assert completions.kwargs["max_completion_tokens"] == 50


async def test_chat_reports_usage_from_last_chunk() -> None:
    client = OpenAIChatClient("key", model="m", max_output_tokens=50, timeout_seconds=5)
    completions = _Completions()
    client._client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    usage = TokenUsage()

    [p async for p in client.stream("s", [ChatMessage("user", "hi")], usage)]

    assert completions.kwargs["stream_options"] == {"include_usage": True}
    assert (usage.input_tokens, usage.output_tokens, usage.reasoning_tokens) == (900, 60, 20)
    assert usage.cached_tokens == 768


async def test_chat_passes_cache_key_only_when_given() -> None:
    client = OpenAIChatClient("key", model="m", max_output_tokens=50, timeout_seconds=5)
    completions = _Completions()
    client._client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

    [p async for p in client.stream("s", [ChatMessage("user", "hi")], cache_key="guide:me")]
    assert completions.kwargs["prompt_cache_key"] == "guide:me"

    [p async for p in client.stream("s", [ChatMessage("user", "hi")])]
    assert completions.kwargs["prompt_cache_key"] is omit


async def test_chat_errors_become_llm_error() -> None:
    client = OpenAIChatClient("key", model="m", max_output_tokens=50, timeout_seconds=5)
    client._client = SimpleNamespace(chat=SimpleNamespace(completions=_Completions(fail=True)))

    with pytest.raises(LLMError):
        [p async for p in client.stream("s", [ChatMessage("user", "hi")])]


async def test_missing_key_fails_without_network() -> None:
    with pytest.raises(LLMError):
        [p async for p in OpenAIChatClient("", "m", 50, 5).stream("s", [])]
    with pytest.raises(EmbeddingError):
        await OpenAIEmbedder("", "m", 4, timeout_seconds=5).embed(["x"])


async def test_embeddings_keep_input_order_and_are_normalized() -> None:
    class _Embeddings:
        async def create(self, **kwargs):
            assert kwargs["dimensions"] == 2
            return SimpleNamespace(
                data=[
                    SimpleNamespace(index=1, embedding=[0.0, 2.0]),
                    SimpleNamespace(index=0, embedding=[3.0, 4.0]),
                ]
            )

    embedder = OpenAIEmbedder("key", "m", dimensions=2, timeout_seconds=5)
    embedder._client = SimpleNamespace(embeddings=_Embeddings())

    vectors = await embedder.embed(["a", "b"])

    assert vectors == [[0.6, 0.8], [0.0, 1.0]]
    assert all(math.isclose(math.hypot(*v), 1.0) for v in vectors)
