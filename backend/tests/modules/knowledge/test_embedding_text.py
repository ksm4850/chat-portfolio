import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace

from src.modules.knowledge.schema import DocumentCreate, DocumentUpdate
from src.modules.knowledge.service import KnowledgeService, embedding_text

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_embedding_text_prefers_path_then_title() -> None:
    assert embedding_text("본문", {"path": "프로젝트 > 섹션"}, "제목") == "[프로젝트 > 섹션]\n본문"
    assert embedding_text("본문", None, "제목") == "[제목]\n본문"
    assert embedding_text("본문", None) == "본문"


class FakeEmbedder:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def embed(self, texts):
        self.calls.append(list(texts))
        return [[0.0] for _ in texts]


class FakeDatabase:
    @asynccontextmanager
    async def read(self):
        yield None

    @asynccontextmanager
    async def transaction(self):
        yield None


class FakeCharacters:
    async def ensure_exists(self, character_id):
        return None


class FakeDocuments:
    def __init__(self, current=None) -> None:
        self.current = current

    async def add(self, session, document):
        document.id = uuid.uuid4()
        document.created_at = document.updated_at = NOW
        return document

    async def find_one(self, session, *conditions):
        return self.current

    async def persist(self, session, document):
        return document


class FakeChunks:
    async def add_all(self, session, chunks):
        return chunks

    async def remove_where(self, session, *conditions):
        return None

    async def count(self, session, *conditions):
        return 1


def _service(embedder: FakeEmbedder, documents: FakeDocuments) -> KnowledgeService:
    return KnowledgeService(
        db=FakeDatabase(),
        document_repository=documents,
        chunk_repository=FakeChunks(),
        embedder=embedder,
        character_service=FakeCharacters(),
        chunk_size=500,
        chunk_overlap=50,
    )


async def test_add_document_embeds_chunks_with_title() -> None:
    embedder = FakeEmbedder()

    await _service(embedder, FakeDocuments()).add_document(
        uuid.uuid4(), DocumentCreate(title="사이트 구성", source="site", content="첫 문단")
    )

    assert embedder.calls == [["[사이트 구성]\n첫 문단"]]


async def test_update_title_only_reembeds_existing_content() -> None:
    embedder = FakeEmbedder()
    current = SimpleNamespace(
        id=uuid.uuid4(),
        title="옛 제목",
        source="site",
        content="본문",
        created_at=NOW,
        updated_at=NOW,
    )

    await _service(embedder, FakeDocuments(current)).update_document(
        uuid.uuid4(), current.id, DocumentUpdate(title="새 제목")
    )

    assert embedder.calls == [["[새 제목]\n본문"]]
