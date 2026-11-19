import math
from collections.abc import Sequence

from openai import AsyncOpenAI, OpenAIError

from src.infrastructure.embedding.base import Embedder, EmbeddingError


class OpenAIEmbedder(Embedder):
    """text-embedding-3 계열. `dimensions` 로 DB 컬럼 차원(1024)에 맞춰 받는다."""

    def __init__(self, api_key: str, model: str, dimensions: int, timeout_seconds: float) -> None:
        self._api_key = api_key
        self._model = model
        self._dimensions = dimensions
        self._timeout_seconds = timeout_seconds
        self._client: AsyncOpenAI | None = None

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self._api_key:
            raise EmbeddingError("OPENAI_API_KEY 가 비어 있다")
        try:
            response = await self._get_client().embeddings.create(
                model=self._model, input=list(texts), dimensions=self._dimensions
            )
        except OpenAIError as exc:
            raise EmbeddingError(f"OpenAI 임베딩 실패: {type(exc).__name__}: {exc}") from exc
        ordered = sorted(response.data, key=lambda item: item.index)
        return [_normalize(item.embedding) for item in ordered]

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self._api_key, timeout=self._timeout_seconds)
        return self._client


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]
