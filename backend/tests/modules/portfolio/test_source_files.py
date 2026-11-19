import shutil
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest
from dependency_injector import providers
from fastapi.testclient import TestClient

from src.core.exceptions import AppError
from src.interfaces.dependencies import get_current_superuser
from src.modules.knowledge.schema import DocumentDraft
from src.modules.portfolio.exceptions import SourceFileNotFoundError
from src.modules.portfolio.service import PortfolioService
from src.modules.users.schema import UserRead
from tests.modules.portfolio.support import CONTENT, FakeKnowledge, portfolio_service

FILE = "cq-decisions.md"


class FailingKnowledge(FakeKnowledge):
    async def replace_documents(
        self, character_id: uuid.UUID, source_prefix: str, drafts: Sequence[DocumentDraft]
    ) -> int:
        raise AppError("임베딩 실패")


@pytest.fixture
def content_dir(tmp_path: Path) -> Path:
    return Path(shutil.copytree(CONTENT, tmp_path / "portfolio"))


@pytest.fixture
def knowledge() -> FakeKnowledge:
    return FakeKnowledge()


@pytest.fixture
def service(knowledge: FakeKnowledge, content_dir: Path) -> PortfolioService:
    return portfolio_service(knowledge, content_dir)


async def test_source_files_follow_catalog_tabs(service: PortfolioService) -> None:
    files = await service.list_source_files()

    decisions = next(f for f in files if f.file == FILE)
    assert decisions.source == "portfolio:" + FILE
    assert decisions.project_id == "cq"
    assert decisions.tab_id == "decisions"
    assert not any(f.project_id == "moeun-mvno" for f in files)


async def test_update_writes_file_and_reingests(
    service: PortfolioService, knowledge: FakeKnowledge, content_dir: Path
) -> None:
    content = "## 1. 새 고민\n\n바꾼 본문이다.\n"

    result = await service.update_source_file(FILE, content)

    assert (content_dir / FILE).read_text(encoding="utf-8") == content
    [(_, drafts)] = knowledge.replaced
    assert result.documents == len(drafts)
    draft = next(d for d in drafts if d.source == "portfolio:" + FILE)
    assert [c.content for c in draft.chunks] == ["바꾼 본문이다."]
    assert (await service.read_source_file(FILE)).content == content


async def test_failed_ingest_restores_file(content_dir: Path) -> None:
    original = (content_dir / FILE).read_text(encoding="utf-8")
    service = portfolio_service(FailingKnowledge(), content_dir)

    with pytest.raises(AppError):
        await service.update_source_file(FILE, "## 바뀐 내용\n\n본문\n")

    assert (content_dir / FILE).read_text(encoding="utf-8") == original


@pytest.mark.parametrize("file", ["nope.md", "../portfolio/cq-decisions.md", "projects.json"])
async def test_only_catalog_files_are_editable(
    service: PortfolioService, content_dir: Path, file: str
) -> None:
    with pytest.raises(SourceFileNotFoundError):
        await service.update_source_file(file, "내용")

    assert not (content_dir / "nope.md").exists()


def _admin() -> UserRead:
    now = datetime.now(UTC)
    return UserRead(
        id=uuid.uuid4(),
        email="admin@example.com",
        full_name=None,
        is_active=True,
        is_superuser=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def api(app, container, client: TestClient, service: PortfolioService) -> TestClient:
    container.portfolio.service.override(providers.Object(service))
    app.dependency_overrides[get_current_superuser] = _admin
    return client


def test_admin_source_file_api(api: TestClient, content_dir: Path) -> None:
    listed = api.get("/api/v1/admin/portfolio/files").json()
    assert {"file", "source", "projectId", "projectTitle", "tabId", "tabLabel"} <= set(listed[0])

    read = api.get(f"/api/v1/admin/portfolio/files/{FILE}").json()
    assert read["content"] == (content_dir / FILE).read_text(encoding="utf-8")

    saved = api.put(f"/api/v1/admin/portfolio/files/{FILE}", json={"content": "## 제목\n\n본문"})
    assert saved.status_code == 200
    assert set(saved.json()) == {"projects", "documents", "sections", "chunks"}

    missing = api.put("/api/v1/admin/portfolio/files/nope.md", json={"content": "x"})
    assert missing.json()["error"]["code"] == "source_file_not_found"

    assert api.post("/api/v1/admin/portfolio/ingest").status_code == 200
