import asyncio
from collections import defaultdict
from pathlib import Path

from pydantic import ValidationError

from src.infrastructure.database import Database
from src.infrastructure.files import MediaDirectory, TextFileDirectory
from src.infrastructure.logging import get_logger
from src.modules.character.service import CharacterService
from src.modules.knowledge.chunking import split_text
from src.modules.knowledge.schema import ChunkDraft, DocumentDraft
from src.modules.knowledge.service import IMPORTED_SOURCE_PREFIX, KnowledgeService
from src.modules.portfolio.exceptions import (
    InvalidPortfolioSourceError,
    MediaNotFoundError,
    PortfolioNotIngestedError,
    ProjectNotFoundError,
    SourceFileNotFoundError,
)
from src.modules.portfolio.markdown import ParsedSection, plain_text, split_sections
from src.modules.portfolio.models import PortfolioCatalog, PortfolioSection
from src.modules.portfolio.repository import CATALOG_ID, CatalogRepository, SectionRepository
from src.modules.portfolio.schema import (
    IngestResult,
    Portfolio,
    PortfolioSource,
    ProjectDetail,
    ProjectSummary,
    SectionLocation,
    SectionRead,
    SourceCatalog,
    SourceFileContent,
    SourceFileRead,
    SourceProject,
    SourceTab,
    Tab,
    TabDetail,
)

logger = get_logger(__name__)

SOURCE_PREFIX = IMPORTED_SOURCE_PREFIX
CATALOG_FILE = "projects.json"
# 원본 md·projects.json 은 이미지를 `medias/...`(원본 디렉터리 기준 상대 경로)로 가리킨다.
MEDIA_DIR = "medias"
# SVG 는 스크립트를 담을 수 있어 받지 않는다.
MEDIA_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".webm"})

# 수집은 포트폴리오 문서 전체를 지우고 다시 넣는다. 동시에 돌면 문서가 겹쳐 들어간다.
_ingest_lock = asyncio.Lock()


class PortfolioService:
    """포트폴리오 원본(projects.json + md)을 화면용 섹션과 캐릭터 기억 청크로 저장하고 읽어 준다."""

    def __init__(
        self,
        db: Database,
        catalog_repository: CatalogRepository,
        section_repository: SectionRepository,
        knowledge_service: KnowledgeService,
        character_service: CharacterService,
        files: TextFileDirectory,
        media: MediaDirectory,
        character_slug: str,
        chunk_size: int,
        chunk_overlap: int,
    ) -> None:
        self._db = db
        self._files = files
        self._media = media
        self._catalogs = catalog_repository
        self._sections = section_repository
        self._knowledge = knowledge_service
        self._characters = character_service
        self._character_slug = character_slug
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    async def ingest(self, source: PortfolioSource) -> IngestResult:
        """다시 실행해도 결과가 같다. 관리자 화면에서 넣은 기억 문서는 건드리지 않는다."""
        character = await self._characters.get_by_slug(self._character_slug)
        rows: list[PortfolioSection] = []
        drafts: list[DocumentDraft] = []
        for project in source.catalog.projects:
            # 탭이 없는 프로젝트는 목록에만 보인다.
            for tab in project.tabs:
                markdown = source.files.get(tab.file)
                if markdown is None:
                    raise InvalidPortfolioSourceError(f"md 파일이 없다: {tab.file}")
                sections = split_sections(markdown, project.id, tab.id)
                rows.extend(
                    PortfolioSection(
                        project_id=project.id,
                        tab=tab.id,
                        anchor=section.anchor,
                        position=position,
                        level=section.level,
                        title=section.title,
                        body=section.body,
                    )
                    for position, section in enumerate(sections)
                )
                drafts.append(self._document(project, tab, markdown, sections))
            for note in project.notes:
                if not project.tabs:
                    raise InvalidPortfolioSourceError(
                        f"탭이 없는 프로젝트에는 노트를 둘 수 없다: {note}"
                    )
                tab = project.tabs[0]
                anchor = next(
                    (r.anchor for r in rows if r.project_id == project.id and r.tab == tab.id),
                    None,
                )
                if anchor is None:
                    raise InvalidPortfolioSourceError(f"노트가 빌릴 섹션이 없다: {note}")
                drafts.append(self._note(project, tab, anchor, note, _markdown(source, note)))

        chunks = await self._knowledge.replace_documents(character.id, SOURCE_PREFIX, drafts)
        async with self._db.transaction() as session:
            data = source.catalog.model_dump(by_alias=True, mode="json")
            catalog = await self._catalogs.get(session, CATALOG_ID)
            if catalog is None:
                await self._catalogs.add(session, PortfolioCatalog(id=CATALOG_ID, data=data))
            else:
                catalog.data = data
            await self._sections.delete_all(session)
            await self._sections.add_all(session, rows)

        result = IngestResult(
            projects=len(source.catalog.projects),
            documents=len(drafts),
            sections=len(rows),
            chunks=chunks,
        )
        logger.info("포트폴리오 수집", extra=result.model_dump())
        return result

    async def load_source(self) -> PortfolioSource:
        try:
            catalog = await self._files.read(CATALOG_FILE)
            files = await self._files.read_many("*.md")
        except OSError as exc:
            raise InvalidPortfolioSourceError(f"원본을 읽지 못했다: {exc.strerror}") from exc
        try:
            return PortfolioSource(catalog=SourceCatalog.model_validate_json(catalog), files=files)
        except ValidationError as exc:
            raise InvalidPortfolioSourceError(f"{CATALOG_FILE} 형식이 올바르지 않다.") from exc

    async def reingest(self) -> IngestResult:
        async with _ingest_lock:
            return await self.ingest(await self.load_source())

    async def list_source_files(self) -> list[SourceFileRead]:
        catalog = (await self.load_source()).catalog
        return [_source_file(project, tab) for project in catalog.projects for tab in project.tabs]

    async def read_source_file(self, file: str) -> SourceFileContent:
        source = await self.load_source()
        project, tab = _find_tab(source.catalog, file)
        return SourceFileContent(
            **_source_file(project, tab).model_dump(), content=_markdown(source, file)
        )

    async def update_source_file(self, file: str, content: str) -> IngestResult:
        """원본 md 를 바꾸고 다시 수집한다. 수집이 실패하면 파일을 되돌린다."""
        async with _ingest_lock:
            source = await self.load_source()
            _find_tab(source.catalog, file)
            previous = _markdown(source, file)
            source.files[file] = content
            await self._write(file, content)
            try:
                return await self.ingest(source)
            except BaseException:
                await self._write(file, previous)
                raise

    async def _write(self, file: str, content: str) -> None:
        try:
            await self._files.write(file, content)
        except OSError as exc:
            raise InvalidPortfolioSourceError(f"원본을 쓰지 못했다: {exc.strerror}") from exc

    async def media_file(self, path: str) -> Path:
        """`medias/` 아래 경로(예: play/cq-graph.png)의 실제 파일."""
        found = await self._media.find(path)
        if found is None:
            raise MediaNotFoundError()
        return found

    async def get_portfolio(self) -> Portfolio:
        catalog = await self._catalog()
        return Portfolio(
            profile=catalog.profile,
            careers=catalog.careers,
            projects=[_summary(project) for project in catalog.projects],
            skills=catalog.skills,
        )

    async def get_project(self, project_id: str) -> ProjectDetail:
        catalog = await self._catalog()
        project = next((p for p in catalog.projects if p.id == project_id), None)
        if project is None:
            raise ProjectNotFoundError()
        async with self._db.read() as session:
            rows = await self._sections.list_ordered(session, project_id)
            by_tab: dict[str, list[SectionRead]] = defaultdict(list)
            for row in rows:
                by_tab[row.tab].append(SectionRead.model_validate(row, from_attributes=True))
        return ProjectDetail(
            **_summary(project).model_dump(exclude={"tabs"}),
            tabs=[
                TabDetail(id=tab.id, label=tab.label, sections=by_tab.get(tab.id, []))
                for tab in project.tabs
            ],
        )

    async def locations(self) -> dict[str, SectionLocation]:
        """anchor → 화면 위치. 수집 전이면 비어 있다."""
        async with self._db.read() as session:
            catalog = await self._catalogs.get(session, CATALOG_ID)
            rows = await self._sections.list_ordered(session)
            if catalog is None:
                return {}
            projects = SourceCatalog.model_validate(catalog.data).projects
        titles = {p.id: p.title for p in projects}
        labels = {(p.id, t.id): t.label for p in projects for t in p.tabs}
        return {
            row.anchor: SectionLocation(
                anchor=row.anchor,
                project_id=row.project_id,
                project_title=titles.get(row.project_id, row.project_id),
                tab=row.tab,
                tab_label=labels.get((row.project_id, row.tab), row.tab),
                title=row.title,
                body=row.body,
                plain=plain_text(row.body),
            )
            for row in rows
        }

    async def _catalog(self) -> SourceCatalog:
        async with self._db.read() as session:
            catalog = await self._catalogs.get(session, CATALOG_ID)
            if catalog is None:
                raise PortfolioNotIngestedError()
            return SourceCatalog.model_validate(catalog.data)

    def _document(
        self,
        project: SourceProject,
        tab: SourceTab,
        markdown: str,
        sections: list[ParsedSection],
    ) -> DocumentDraft:
        chunks = [
            ChunkDraft(
                content=text,
                meta={
                    "view": "project",
                    "projectId": project.id,
                    "tab": tab.id,
                    "anchor": section.anchor,
                    "sectionTitle": section.title,
                    "path": f"{project.title} > {tab.label} > {section.title}",
                },
            )
            for section in sections
            if section.body
            for text in split_text(section.body, size=self._chunk_size, overlap=self._chunk_overlap)
        ]
        return DocumentDraft(
            title=f"{project.title} - {tab.label}",
            source=f"{SOURCE_PREFIX}{tab.file}",
            content=markdown,
            chunks=chunks,
        )

    def _note(
        self, project: SourceProject, tab: SourceTab, anchor: str, file: str, markdown: str
    ) -> DocumentDraft:
        """노트는 화면 섹션이 없어 답변 중 화면은 첫 탭의 첫 섹션(`anchor`)으로 연다."""
        chunks = [
            ChunkDraft(
                content=text,
                meta={
                    "view": "project",
                    "projectId": project.id,
                    "tab": tab.id,
                    "anchor": anchor,
                    "sectionTitle": section.title,
                    "path": f"{project.title} > {section.title}",
                },
            )
            for section in split_sections(markdown, project.id, "note")
            if section.body
            for text in split_text(section.body, size=self._chunk_size, overlap=self._chunk_overlap)
        ]
        return DocumentDraft(
            title=f"{project.title} - {tab.label}",
            source=f"{SOURCE_PREFIX}{file}",
            content=markdown,
            chunks=chunks,
        )


def _find_tab(catalog: SourceCatalog, file: str) -> tuple[SourceProject, SourceTab]:
    for project in catalog.projects:
        for tab in project.tabs:
            if tab.file == file:
                return project, tab
    raise SourceFileNotFoundError()


def _markdown(source: PortfolioSource, file: str) -> str:
    markdown = source.files.get(file)
    if markdown is None:
        raise InvalidPortfolioSourceError(f"md 파일이 없다: {file}")
    return markdown


def _source_file(project: SourceProject, tab: SourceTab) -> SourceFileRead:
    return SourceFileRead(
        file=tab.file,
        source=f"{SOURCE_PREFIX}{tab.file}",
        project_id=project.id,
        project_title=project.title,
        tab_id=tab.id,
        tab_label=tab.label,
    )


def _summary(project: SourceProject) -> ProjectSummary:
    return ProjectSummary(
        **project.model_dump(exclude={"tabs", "notes"}),
        tabs=[Tab(id=tab.id, label=tab.label) for tab in project.tabs],
    )
