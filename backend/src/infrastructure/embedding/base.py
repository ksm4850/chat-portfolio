from abc import ABC, abstractmethod
from collections.abc import Sequence

# 저장 벡터 차원. OpenAI 임베딩을 dimensions 로 이 크기에 맞춰 받는다.
# 바꾸면 마이그레이션과 재임베딩이 필요하다.
EMBEDDING_DIMENSIONS = 1024


class EmbeddingError(Exception):
    """임베딩 호출 실패. 서비스는 이를 자기 도메인 예외로 번역한다."""


class Embedder(ABC):
    @abstractmethod
    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """텍스트마다 정규화된(길이 1) 벡터를 돌려준다."""
