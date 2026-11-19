"""DB 없이 PortfolioService 를 실제 content/portfolio 원본으로 돌리기 위한 가짜 구현.

portfolio 테이블은 캐릭터별이 아니라 전역이라, 실제 DB 로 수집 테스트를 하면 개발 데이터를 지운다.
"""

import uuid
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from src.infrastructure.files import MediaDirectory, TextFileDirectory
from src.interfaces.cli.ingest_portfolio import load_source
from src.modules.character.schema import CharacterRead
from src.modules.character.service import SHORT_REPLY, CharacterService, build_system_prompt
from src.modules.knowledge.schema import DocumentDraft
from src.modules.knowledge.service import KnowledgeService
from src.modules.portfolio.models import PortfolioCatalog, PortfolioSection
from src.modules.portfolio.repository import CatalogRepository, SectionRepository
from src.modules.portfolio.schema import PortfolioSource
from src.modules.portfolio.service import MEDIA_DIR, MEDIA_EXTENSIONS, PortfolioService

CONTENT = Path(__file__).resolve().parents[4] / "content" / "portfolio"
NOW = datetime(2026, 11, 16, tzinfo=UTC)
CHARACTER = CharacterRead(
    id=uuid.uuid4(),
    slug="me",
    name="김상명",
    greeting="안녕하세요.",
    profile="백엔드 개발자다.",
    speaking_style="합니다체로 말한다.",
    example_dialogues=[],
    is_public=False,
    created_at=NOW,
    updated_at=NOW,
)


class FakeDatabase:
    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        yield None

    @asynccontextmanager
    async def read(self) -> AsyncIterator[None]:
        yield None


class FakeCatalogs(CatalogRepository):
    def __init__(self) -> None:
        self.rows: dict[int, PortfolioCatalog] = {}

    async def get(self, session, id_):
        return self.rows.get(id_)

    async def add(self, session, obj):
        self.rows[obj.id] = obj
        return obj


class FakeSections(SectionRepository):
    def __init__(self) -> None:
        self.rows: list[PortfolioSection] = []

    async def delete_all(self, session) -> None:
        self.rows = []

    async def add_all(self, session, objs):
        self.rows.extend(objs)
        return objs

    async def list_ordered(self, session, project_id: str | None = None):
        rows = [r for r in self.rows if project_id is None or r.project_id == project_id]
        return sorted(rows, key=lambda r: (r.project_id, r.tab, r.position))


class FakeKnowledge(KnowledgeService):
    def __init__(self) -> None:
        self.replaced: list[tuple[str, list[DocumentDraft]]] = []

    async def replace_documents(
        self, character_id: uuid.UUID, source_prefix: str, drafts: Sequence[DocumentDraft]
    ) -> int:
        self.replaced.append((source_prefix, list(drafts)))
        return sum(len(d.chunks) for d in drafts)


class FakeCharacters(CharacterService):
    def __init__(self) -> None:
        pass

    async def get_by_slug(self, slug: str) -> CharacterRead:
        return CHARACTER

    async def system_prompt(
        self, character_id: uuid.UUID, memories: Sequence[str], reply: str = SHORT_REPLY
    ) -> str:
        return build_system_prompt(CHARACTER, memories, reply)


def portfolio_service(
    knowledge: KnowledgeService | None = None, content_dir: Path = CONTENT
) -> PortfolioService:
    return PortfolioService(
        db=FakeDatabase(),
        catalog_repository=FakeCatalogs(),
        section_repository=FakeSections(),
        knowledge_service=knowledge or FakeKnowledge(),
        character_service=FakeCharacters(),
        files=TextFileDirectory(content_dir),
        media=MediaDirectory(content_dir / MEDIA_DIR, MEDIA_EXTENSIONS),
        character_slug="me",
        chunk_size=500,
        chunk_overlap=100,
    )


def content_source() -> PortfolioSource:
    return load_source(CONTENT)
