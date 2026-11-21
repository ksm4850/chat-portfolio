import uuid
from collections.abc import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database import BaseRepository
from src.modules.knowledge.models import Chunk, Document


class DocumentRepository(BaseRepository[Document]):
    model = Document

    async def delete_by_source_prefix(
        self, session: AsyncSession, character_id: uuid.UUID, prefix: str
    ) -> int:
        statement = delete(Document).where(
            Document.character_id == character_id, Document.source.startswith(prefix)
        )
        result = await session.execute(statement)
        return result.rowcount

    async def list_with_chunk_counts(
        self, session: AsyncSession, character_id: uuid.UUID
    ) -> Sequence[tuple[Document, int]]:
        statement = (
            select(Document, func.count(Chunk.id))
            .outerjoin(Chunk, Chunk.document_id == Document.id)
            .where(Document.character_id == character_id)
            .group_by(Document.id)
            .order_by(Document.created_at.desc())
        )
        return [(document, count) for document, count in await session.execute(statement)]


class ChunkRepository(BaseRepository[Chunk]):
    model = Chunk

    async def search(
        self,
        session: AsyncSession,
        character_id: uuid.UUID,
        embedding: Sequence[float],
        *,
        limit: int,
    ) -> Sequence[tuple[Chunk, str, float]]:
        """한 캐릭터의 청크 중 코사인 거리가 가까운 순으로 (청크, 문서 제목, 거리)를 돌려준다."""
        distance = Chunk.embedding.cosine_distance(embedding).label("distance")
        statement = (
            select(Chunk, Document.title, distance)
            .join(Document, Document.id == Chunk.document_id)
            .where(Document.character_id == character_id)
            .order_by(distance)
            .limit(limit)
        )
        result = await session.execute(statement)
        return [(row.Chunk, row.title, row.distance) for row in result]

    async def list_after(
        self, session: AsyncSession, after: uuid.UUID | None, *, limit: int
    ) -> Sequence[tuple[Chunk, str]]:
        """재임베딩용. 문서 제목과 함께 id 순으로 끊어 읽는다."""
        statement = (
            select(Chunk, Document.title)
            .join(Document, Document.id == Chunk.document_id)
            .order_by(Chunk.id)
            .limit(limit)
        )
        if after is not None:
            statement = statement.where(Chunk.id > after)
        return [(chunk, title) for chunk, title in (await session.execute(statement)).all()]
