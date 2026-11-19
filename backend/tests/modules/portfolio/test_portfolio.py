import pytest
from dependency_injector import providers
from fastapi.testclient import TestClient

from src.modules.portfolio.service import PortfolioService
from tests.modules.portfolio.support import FakeKnowledge, content_source, portfolio_service


@pytest.fixture
def knowledge() -> FakeKnowledge:
    return FakeKnowledge()


@pytest.fixture
async def service(knowledge: FakeKnowledge) -> PortfolioService:
    service = portfolio_service(knowledge)
    await service.ingest(content_source())
    return service


async def test_ingest_creates_one_document_per_md_with_located_chunks(
    service: PortfolioService, knowledge: FakeKnowledge
) -> None:
    [(prefix, drafts)] = knowledge.replaced

    assert prefix == "portfolio:"
    assert len(drafts) == 17
    decisions = next(d for d in drafts if d.source == "portfolio:cq-decisions.md")
    assert decisions.title.endswith(" - 기술적 고민")
    chunk = next(c for c in decisions.chunks if c.meta["anchor"] == "cq-decisions-2")
    assert chunk.meta["view"] == "project"
    assert chunk.meta["projectId"] == "cq"
    assert chunk.meta["tab"] == "decisions"
    assert chunk.meta["sectionTitle"].startswith("2. 방화벽 뒤 워커 접근")
    assert chunk.meta["path"].endswith("> 기술적 고민 > " + chunk.meta["sectionTitle"])


async def test_ingest_is_idempotent(service: PortfolioService, knowledge: FakeKnowledge) -> None:
    first = await service.locations()

    await service.ingest(content_source())

    assert await service.locations() == first
    assert len(knowledge.replaced) == 2


async def test_projects_without_tabs_are_listed_but_not_ingested(
    service: PortfolioService, knowledge: FakeKnowledge
) -> None:
    portfolio = await service.get_portfolio()
    detail = await service.get_project("moeun-mvno")

    assert "moeun-mvno" in [p.id for p in portfolio.projects]
    assert detail.tabs == []
    assert detail.url is None
    assert not any(anchor.startswith("moeun-") for anchor in await service.locations())
    assert not any("moeun" in draft.source for draft in knowledge.replaced[0][1])


async def test_notes_are_ingested_as_memory_located_at_first_section(
    service: PortfolioService, knowledge: FakeKnowledge
) -> None:
    note = next(d for d in knowledge.replaced[0][1] if d.source == "portfolio:phenotype-best.md")
    detail = await service.get_project("phenotype")

    assert note.chunks
    assert {c.meta["anchor"] for c in note.chunks} == {"phenotype-overview-1"}
    assert {c.meta["tab"] for c in note.chunks} == {"overview"}
    assert note.chunks[0].meta["sectionTitle"] == "가장 자신 있는 프로젝트로 꼽는 이유"
    assert "note" not in [t.id for t in detail.tabs]
    assert not any("note" in anchor for anchor in await service.locations())


@pytest.fixture
def api(container, client: TestClient, service: PortfolioService) -> TestClient:
    container.portfolio.service.override(providers.Object(service))
    return client


def test_portfolio_api_hides_tab_files(api: TestClient) -> None:
    body = api.get("/api/v1/portfolio").json()

    assert set(body) == {"profile", "careers", "projects", "skills"}
    cq = next(p for p in body["projects"] if p["id"] == "cq")
    assert cq["url"] == "http://cq.pilab.co.kr"
    assert cq["tabs"][0] == {"id": "overview", "label": "개요"}
    assert "projectIds" in body["careers"][0]
    phenotype = next(p for p in body["projects"] if p["id"] == "phenotype")
    assert "notes" not in phenotype


def test_project_detail_returns_sections_per_tab(api: TestClient) -> None:
    body = api.get("/api/v1/portfolio/projects/cq").json()

    decisions = next(t for t in body["tabs"] if t["id"] == "decisions")
    anchors = [s["anchor"] for s in decisions["sections"]]
    assert anchors == [f"cq-decisions-{n}" for n in range(1, 6)]
    assert decisions["sections"][1]["level"] == 3
    assert decisions["sections"][1]["body"].startswith("> 워커·릴레이 모두 NATS")


def test_unknown_project_is_404(api: TestClient) -> None:
    response = api.get("/api/v1/portfolio/projects/nope")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "project_not_found"


def test_portfolio_before_ingest_is_404(container, client: TestClient) -> None:
    container.portfolio.service.override(providers.Object(portfolio_service()))

    response = client.get("/api/v1/portfolio")

    assert response.json()["error"]["code"] == "portfolio_not_ingested"
