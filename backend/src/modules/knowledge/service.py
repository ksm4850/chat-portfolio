import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database import Database
from src.infrastructure.embedding import Embedder, EmbeddingError
from src.infrastructure.logging import get_logger
from src.modules.character.service import CharacterService
from src.modules.knowledge.chunking import split_text
from src.modules.knowledge.exceptions import (
    DocumentNotFoundError,
    EmbeddingFailedError,
    EmptyDocumentError,
    ImportedDocumentError,
)
from src.modules.knowledge.models import Chunk, Document
from src.modules.knowledge.repository import ChunkRepository, DocumentRepository
from src.modules.knowledge.schema import (
    ChunkRead,
    DocumentCreate,
    DocumentDetail,
    DocumentDraft,
    DocumentRead,
    DocumentUpdate,
    SearchHit,
)

logger = get_logger(__name__)

_REEMBED_BATCH = 64

# 포트폴리오 수집이 원본 md 로 만드는 문서. 재수집하면 덮어써지므로
# 관리자 API 로 만들거나 고치지 않는다.
IMPORTED_SOURCE_PREFIX = "portfolio:"


class KnowledgeService:
    """캐릭터가 아는 사실(문서)을 적재하고 질의와 가까운 청크를 찾는다.

    임베딩은 느린 계산·외부 호출이라 트랜잭션을 열기 전에 끝낸다.
    """

    def __init__(
        self,
        db: Database,
        document_repository: DocumentRepository,
        chunk_repository: ChunkRepository,
        embedder: Embedder,
        character_service: CharacterService,
        chunk_size: int,
        chunk_overlap: int,
    ) -> None:
        self._db = db
        self._documents = document_repository
        self._chunks = chunk_repository
        self._embedder = embedder
        self._characters = character_service
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    async def add_document(self, character_id: uuid.UUID, payload: DocumentCreate) -> DocumentRead:
        _ensure_editable_source(payload.source)
        await self._characters.ensure_exists(character_id)
        texts = self._split(payload.content)
        embeddings = await self._embed(texts)

        async with self._db.transaction() as session:
            document = await self._documents.add(
                session,
                Document(
                    character_id=character_id,
                    title=payload.title,
                    source=payload.source,
                    content=payload.content,
                ),
            )
            await self._chunks.add_all(session, _chunks(document.id, texts, embeddings))
            result = _document_read(document, len(texts))

        logger.info(
            "문서 적재",
            extra={
                "character_id": str(character_id),
                "document_id": str(result.id),
                "source": result.source,
                "chunks": len(texts),
            },
        )
        return result

    async def get_document(self, character_id: uuid.UUID, document_id: uuid.UUID) -> DocumentDetail:
        async with self._db.read() as session:
            document = await self._find_document(session, character_id, document_id)
            chunks = await self._chunks.find(
                session,
                Chunk.document_id == document_id,
                order_by=[Chunk.position],
                limit=10_000,
            )
            return DocumentDetail(
                **_document_read(document, len(chunks)).model_dump(),
                content=document.content,
                chunks=[ChunkRead.model_validate(chunk) for chunk in chunks],
            )

    async def update_document(
        self, character_id: uuid.UUID, document_id: uuid.UUID, payload: DocumentUpdate
    ) -> DocumentRead:
        async with self._db.read() as session:
            current = await self._find_document(session, character_id, document_id)
            _ensure_editable_source(current.source)
        if payload.source is not None:
            _ensure_editable_source(payload.source)

        texts: list[str] | None = None
        embeddings: list[list[float]] = []
        if payload.content is not None:
            texts = self._split(payload.content)
            embeddings = await self._embed(texts)

        async with self._db.transaction() as session:
            document = await self._find_document(session, character_id, document_id)
            for field, value in payload.model_dump(exclude_unset=True, exclude_none=True).items():
                setattr(document, field, value)
            if texts is not None:
                await self._chunks.remove_where(session, Chunk.document_id == document_id)
                await self._chunks.add_all(session, _chunks(document_id, texts, embeddings))
            document = await self._documents.persist(session, document)
            count = await self._chunks.count(session, Chunk.document_id == document_id)
            result = _document_read(document, count)

        logger.info(
            "문서 수정",
            extra={"document_id": str(document_id), "rechunked": texts is not None},
        )
        return result

    async def replace_documents(
        self, character_id: uuid.UUID, source_prefix: str, drafts: Sequence[DocumentDraft]
    ) -> int:
        """`source` 가 `source_prefix` 로 시작하는 문서를 모두 지우고 `drafts` 로 바꾼다.

        다시 실행해도 결과가 같다. 다른 출처의 문서는 건드리지 않는다. 적재한 청크 수를 돌려준다.
        """
        await self._characters.ensure_exists(character_id)
        chunks = [chunk for draft in drafts for chunk in draft.chunks]
        embeddings = await self._embed([embedding_text(c.content, c.meta) for c in chunks])
        vectors = iter(embeddings)

        async with self._db.transaction() as session:
            removed = await self._documents.delete_by_source_prefix(
                session, character_id, source_prefix
            )
            for draft in drafts:
                document = await self._documents.add(
                    session,
                    Document(
                        character_id=character_id,
                        title=draft.title,
                        source=draft.source,
                        content=draft.content,
                    ),
                )
                await self._chunks.add_all(
                    session,
                    [
                        Chunk(
                            document_id=document.id,
                            position=i,
                            content=chunk.content,
                            embedding=next(vectors),
                            meta=chunk.meta,
                        )
                        for i, chunk in enumerate(draft.chunks)
                    ],
                )

        logger.info(
            "문서 일괄 교체",
            extra={
                "character_id": str(character_id),
                "source_prefix": source_prefix,
                "removed": removed,
                "documents": len(drafts),
                "chunks": len(chunks),
            },
        )
        return len(chunks)

    async def list_documents(self, character_id: uuid.UUID) -> list[DocumentRead]:
        await self._characters.ensure_exists(character_id)
        async with self._db.read() as session:
            rows = await self._documents.list_with_chunk_counts(session, character_id)
            return [_document_read(document, count) for document, count in rows]

    async def delete_document(self, character_id: uuid.UUID, document_id: uuid.UUID) -> None:
        async with self._db.transaction() as session:
            document = await self._find_document(session, character_id, document_id)
            _ensure_editable_source(document.source)
            await self._documents.remove(session, document)

        logger.info("문서 삭제", extra={"document_id": str(document_id)})

    async def search(self, character_id: uuid.UUID, query: str, *, limit: int) -> list[SearchHit]:
        return await self.search_any(character_id, [query], limit=limit)

    async def search_any(
        self, character_id: uuid.UUID, queries: Sequence[str], *, limit: int
    ) -> list[SearchHit]:
        """질의 여러 개로 찾아 합친다. 같은 청크는 가장 높은 점수 하나만 남긴다.

        임베딩은 한 번에 요청한다.
        """
        embeddings = await self._embed(queries)
        best: dict[uuid.UUID, SearchHit] = {}
        async with self._db.read() as session:
            for embedding in embeddings:
                rows = await self._chunks.search(session, character_id, embedding, limit=limit)
                for chunk, title, distance in rows:
                    score = 1 - distance
                    if chunk.id in best and best[chunk.id].score >= score:
                        continue
                    best[chunk.id] = SearchHit(
                        document_id=chunk.document_id,
                        title=title,
                        content=chunk.content,
                        score=score,
                        meta=chunk.meta,
                    )
        return sorted(best.values(), key=lambda hit: hit.score, reverse=True)[:limit]

    async def reembed_all(self) -> int:
        """임베딩 공급자를 바꾼 뒤 모든 청크의 벡터를 다시 만든다. 처리한 청크 수를 돌려준다."""
        total = 0
        after: uuid.UUID | None = None
        while True:
            async with self._db.read() as session:
                batch = [
                    (chunk.id, embedding_text(chunk.content, chunk.meta))
                    for chunk in await self._chunks.list_after(session, after, limit=_REEMBED_BATCH)
                ]
            if not batch:
                break
            vectors = await self._embed([text for _, text in batch])
            async with self._db.transaction() as session:
                for (chunk_id, _), vector in zip(batch, vectors, strict=True):
                    chunk = await self._chunks.get(session, chunk_id)
                    if chunk is not None:
                        chunk.embedding = vector
            total += len(batch)
            after = batch[-1][0]
            logger.info("재임베딩 진행", extra={"done": total})
        return total

    async def _find_document(
        self, session: AsyncSession, character_id: uuid.UUID, document_id: uuid.UUID
    ) -> Document:
        document = await self._documents.find_one(
            session, Document.id == document_id, Document.character_id == character_id
        )
        if document is None:
            raise DocumentNotFoundError()
        return document

    def _split(self, content: str) -> list[str]:
        texts = split_text(content, size=self._chunk_size, overlap=self._chunk_overlap)
        if not texts:
            raise EmptyDocumentError()
        return texts

    async def _embed(self, texts: Sequence[str]) -> list[list[float]]:
        try:
            return await self._embedder.embed(texts)
        except EmbeddingError as exc:
            logger.warning("임베딩 실패", extra={"error": str(exc)})
            raise EmbeddingFailedError() from exc


def embedding_text(content: str, meta: dict | None) -> str:
    """위치 문맥(`meta.path`)이 있으면 앞에 붙여 임베딩한다.

    짧은 섹션도 어느 프로젝트 얘기인지 검색되게 한다.
    """
    path = (meta or {}).get("path")
    return f"[{path}]\n{content}" if path else content


def _ensure_editable_source(source: str) -> None:
    if source.startswith(IMPORTED_SOURCE_PREFIX):
        raise ImportedDocumentError()


def _chunks(
    document_id: uuid.UUID, texts: Sequence[str], embeddings: Sequence[list[float]]
) -> list[Chunk]:
    return [
        Chunk(document_id=document_id, position=i, content=text, embedding=vector)
        for i, (text, vector) in enumerate(zip(texts, embeddings, strict=True))
    ]


def _document_read(document: Document, chunk_count: int) -> DocumentRead:
    return DocumentRead(
        id=document.id,
        title=document.title,
        source=document.source,
        chunk_count=chunk_count,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )
