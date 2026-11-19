import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace

from src.modules.knowledge.service import KnowledgeService

CHARACTER = uuid.uuid4()
A, B, C = (
    SimpleNamespace(id=uuid.uuid4(), document_id=uuid.uuid4(), content=c, meta=None) for c in "abc"
)


class FakeEmbedder:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed(self, texts):
        self.calls.append(list(texts))
        return [[float(i)] for i, _ in enumerate(texts)]


class FakeChunks:
    """질의 벡터별로 정해 둔 (청크, 거리) 목록을 돌려준다."""

    rows = {
        0.0: [(A, 0.5), (B, 0.6)],
        1.0: [(B, 0.2), (C, 0.7)],
    }

    async def search(self, session, character_id, embedding, *, limit):
        return [(chunk, "문서", distance) for chunk, distance in self.rows[embedding[0]][:limit]]


class FakeDatabase:
    @asynccontextmanager
    async def read(self):
        yield None


def _service(embedder: FakeEmbedder) -> KnowledgeService:
    return KnowledgeService(
        db=FakeDatabase(),
        document_repository=None,
        chunk_repository=FakeChunks(),
        embedder=embedder,
        character_service=None,
        chunk_size=500,
        chunk_overlap=50,
    )


async def test_search_any_embeds_once_and_keeps_best_score_per_chunk() -> None:
    embedder = FakeEmbedder()

    hits = await _service(embedder).search_any(CHARACTER, ["질문", "직전 질문\n질문"], limit=2)

    assert embedder.calls == [["질문", "직전 질문\n질문"]]
    assert [(hit.content, round(hit.score, 2)) for hit in hits] == [("b", 0.8), ("a", 0.5)]


async def test_search_is_single_query_search_any() -> None:
    hits = await _service(FakeEmbedder()).search(CHARACTER, "질문", limit=5)

    assert [(hit.content, round(hit.score, 2)) for hit in hits] == [("a", 0.5), ("b", 0.4)]
