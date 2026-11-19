"""캐릭터·기억 관리 통합 검증. 실제 DB(pgvector)가 필요하다.

관리자 인증은 dependency override 로 통과시키고, 임베딩은 키워드 기반 가짜 구현으로 바꾼다.
"""

import uuid
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from src.core.config import Settings, get_settings
from src.infrastructure.embedding import EMBEDDING_DIMENSIONS, Embedder
from src.interfaces.dependencies import get_current_superuser
from src.interfaces.main import create_app
from src.modules.knowledge.schema import ChunkDraft, DocumentDraft
from src.modules.users.schema import UserRead
from tests.conftest import use_in_memory_stores

pytestmark = pytest.mark.integration

SLUG_PREFIX = "it-"
ADMIN = "/api/v1/admin/characters"
KEYWORDS = ("고향", "직업", "취미")


class KeywordEmbedder(Embedder):
    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def _vector(self, value: str) -> list[float]:
        vector = [0.0] * EMBEDDING_DIMENSIONS
        for i, keyword in enumerate(KEYWORDS):
            if keyword in value:
                vector[i] = 1.0
        # 키워드가 하나도 없을 때 영벡터가 되면 코사인 거리가 정의되지 않는다.
        vector[-1] = 0.01
        return vector


def _sync_url(url: str) -> str:
    return url.replace("+asyncpg", "+psycopg2").replace("postgresql+psycopg2", "postgresql")


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
def client() -> Iterator[TestClient]:
    get_settings.cache_clear()
    settings = Settings(environment="local", jwt_secret_key="integration-test-secret")
    engine = create_engine(_sync_url(settings.database_url))
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM characters LIMIT 1"))
    except Exception as exc:
        engine.dispose()
        pytest.skip(f"실제 DB를 쓸 수 없다: {type(exc).__name__}")

    def purge() -> None:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM characters WHERE slug LIKE :p"), {"p": SLUG_PREFIX + "%"}
            )

    purge()
    app = use_in_memory_stores(create_app(settings))
    app.state.container.infrastructure.embedder.override(KeywordEmbedder())
    app.dependency_overrides[get_current_superuser] = _admin
    with TestClient(app) as test_client:
        yield test_client
    purge()
    engine.dispose()


def _character(client: TestClient, slug: str, **fields) -> dict:
    payload = {"slug": SLUG_PREFIX + slug, "name": "상명", "profile": "백엔드 개발자", **fields}
    response = client.post(ADMIN, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _document(client: TestClient, character_id: str, title: str, content: str) -> dict:
    response = client.post(
        f"{ADMIN}/{character_id}/documents",
        json={"title": title, "source": "profile", "content": content},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_character_crud_and_slug_conflict(client: TestClient) -> None:
    created = _character(
        client,
        "crud",
        greeting="안녕하세요",
        exampleDialogues=[{"user": "뭐 해요?", "assistant": "코딩해요."}],
    )

    assert created["isPublic"] is False
    assert created["exampleDialogues"] == [{"user": "뭐 해요?", "assistant": "코딩해요."}]

    updated = client.patch(f"{ADMIN}/{created['id']}", json={"isPublic": True}).json()
    assert updated["isPublic"] is True
    assert updated["profile"] == "백엔드 개발자"

    conflict = client.post(ADMIN, json={"slug": SLUG_PREFIX + "crud", "name": "x", "profile": "x"})
    assert conflict.status_code == 409

    assert client.delete(f"{ADMIN}/{created['id']}").status_code == 204
    assert client.get(f"{ADMIN}/{created['id']}").status_code == 404


def test_only_public_characters_are_visible_to_visitors(client: TestClient) -> None:
    hidden = _character(client, "hidden")
    shown = _character(client, "shown", isPublic=True, greeting="반가워요")

    assert client.get(f"/api/v1/characters/{hidden['slug']}").status_code == 404
    assert client.get(f"/api/v1/characters/{shown['slug']}").json() == {
        "slug": shown["slug"],
        "name": "상명",
        "greeting": "반가워요",
    }


def test_search_is_scoped_to_character(client: TestClient) -> None:
    me = _character(client, "me")
    other = _character(client, "other")
    _document(client, me["id"], "자기소개", "Q: 고향은?\nA: 부산\n\nQ: 직업은?\nA: 개발자")
    _document(client, me["id"], "취미", "주말엔 취미로 등산을 간다.")
    _document(client, other["id"], "남의 취미", "취미는 낚시다.")

    hits = client.post(f"{ADMIN}/{me['id']}/search", json={"query": "취미가 뭐야?"}).json()

    assert [hit["title"] for hit in hits][:1] == ["취미"]
    assert "남의 취미" not in [hit["title"] for hit in hits]


def test_documents_belong_to_their_character(client: TestClient) -> None:
    me = _character(client, "owner")
    other = _character(client, "stranger")
    document = _document(client, me["id"], "직업", "직업은 개발자다.")

    assert client.delete(f"{ADMIN}/{other['id']}/documents/{document['id']}").status_code == 404
    assert [d["id"] for d in client.get(f"{ADMIN}/{me['id']}/documents").json()] == [document["id"]]
    assert client.delete(f"{ADMIN}/{me['id']}/documents/{document['id']}").status_code == 204


def test_documents_need_existing_character(client: TestClient) -> None:
    response = client.post(
        f"{ADMIN}/{uuid.uuid4()}/documents",
        json={"title": "t", "source": "profile", "content": "내용"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "character_not_found"


def test_blank_document_is_rejected(client: TestClient) -> None:
    me = _character(client, "blank")

    response = client.post(
        f"{ADMIN}/{me['id']}/documents",
        json={"title": "빈 문서", "source": "profile", "content": "  \n\n  "},
    )

    assert response.json()["error"]["code"] == "empty_document"


def test_deleting_character_removes_its_documents(client: TestClient) -> None:
    me = _character(client, "cascade")
    _document(client, me["id"], "직업", "직업은 개발자다.")

    client.delete(f"{ADMIN}/{me['id']}")

    assert client.get(f"{ADMIN}/{me['id']}/documents").status_code == 404


def test_document_detail_and_update_rechunks(client: TestClient) -> None:
    me = _character(client, "edit")
    document = _document(client, me["id"], "직업", "직업은 개발자다.")
    url = f"{ADMIN}/{me['id']}/documents/{document['id']}"

    detail = client.get(url).json()
    assert detail["content"] == "직업은 개발자다."
    assert [(c["position"], c["content"]) for c in detail["chunks"]] == [(0, "직업은 개발자다.")]

    renamed = client.patch(url, json={"title": "취미"}).json()
    assert renamed["title"] == "취미"
    assert renamed["chunkCount"] == 1

    client.patch(url, json={"content": "취미는 등산이다."})

    assert [c["content"] for c in client.get(url).json()["chunks"]] == ["취미는 등산이다."]
    hits = client.post(f"{ADMIN}/{me['id']}/search", json={"query": "취미", "limit": 1}).json()
    assert hits[0]["content"] == "취미는 등산이다."
    assert client.get(f"{ADMIN}/{me['id']}/documents").json()[0]["chunkCount"] == 1


def test_portfolio_documents_are_read_only(client: TestClient) -> None:
    me = _character(client, "imported")
    service = client.app.state.container.knowledge.service()
    client.portal.call(
        service.replace_documents,
        uuid.UUID(me["id"]),
        "portfolio:",
        [
            DocumentDraft(
                title="CQ - 개요",
                source="portfolio:cq-overview.md",
                content="# 개요",
                chunks=[ChunkDraft(content="직업 소개", meta={"anchor": "cq-overview-1"})],
            )
        ],
    )
    [imported] = client.get(f"{ADMIN}/{me['id']}/documents").json()
    url = f"{ADMIN}/{me['id']}/documents/{imported['id']}"

    assert client.get(url).json()["chunks"][0]["meta"] == {"anchor": "cq-overview-1"}
    for response in (
        client.patch(url, json={"title": "x"}),
        client.delete(url),
        client.post(
            f"{ADMIN}/{me['id']}/documents",
            json={"title": "t", "source": "portfolio:x.md", "content": "내용"},
        ),
    ):
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "imported_document"
