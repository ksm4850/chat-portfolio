import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from dependency_injector import providers
from fastapi.testclient import TestClient

from src.infrastructure.llm import ChatMessage, LLMClient, LLMError, TokenUsage
from src.interfaces.dependencies import get_current_superuser
from src.modules.character.exceptions import CharacterNotFoundError
from src.modules.character.schema import CharacterRead
from src.modules.character.service import SHORT_REPLY, CharacterService, build_system_prompt
from src.modules.chat.limits import ChatLimits
from src.modules.knowledge.schema import SearchHit
from src.modules.knowledge.service import KnowledgeService
from src.modules.users.schema import UserRead

SESSIONS = "/api/v1/chat/sessions"
NOW = datetime(2026, 11, 14, tzinfo=UTC)
CHARACTER = CharacterRead(
    id=uuid.uuid4(),
    slug="me",
    name="상명",
    greeting="안녕하세요, 상명입니다.",
    profile="백엔드 개발자다.",
    speaking_style="존댓말을 쓴다.",
    example_dialogues=[],
    is_public=True,
    created_at=NOW,
    updated_at=NOW,
)
LIMITS = ChatLimits(
    message_max_length=500,
    min_interval_seconds=0,
    messages_per_session=20,
    messages_per_visitor_per_day=50,
    messages_per_ip_per_hour=60,
    llm_calls_per_day=500,
    session_ttl_seconds=3600,
)


class FakeLLM(LLMClient):
    def __init__(self) -> None:
        self.fail = False
        self.calls: list[tuple[str, list[ChatMessage]]] = []

    async def stream(
        self, system: str, messages: Sequence[ChatMessage], usage: TokenUsage | None = None
    ) -> AsyncIterator[str]:
        self.calls.append((system, list(messages)))
        for part in ("안녕", "하세요"):
            yield part
        if self.fail:
            raise LLMError("down")


class FakeKnowledge(KnowledgeService):
    def __init__(self) -> None:
        self.character_ids: list[uuid.UUID] = []

    async def search(self, character_id: uuid.UUID, query: str, *, limit: int) -> list[SearchHit]:
        self.character_ids.append(character_id)
        return [SearchHit(document_id=uuid.uuid4(), title="소개", content="고향은 부산", score=0.8)]


class FakeCharacters(CharacterService):
    def __init__(self) -> None:
        pass

    async def get_public_character(self, slug: str) -> CharacterRead:
        if slug != CHARACTER.slug:
            raise CharacterNotFoundError()
        return CHARACTER

    async def system_prompt(
        self, character_id: uuid.UUID, memories: Sequence[str], reply: str = SHORT_REPLY
    ) -> str:
        return build_system_prompt(CHARACTER, memories, reply)


@pytest.fixture
def llm(container) -> FakeLLM:
    fake = FakeLLM()
    container.infrastructure.llm.override(fake)
    container.knowledge.service.override(FakeKnowledge())
    container.character.service.override(FakeCharacters())
    container.chat_limits.override(providers.Object(LIMITS))
    return fake


def _limit(container, **changes) -> None:
    container.chat_limits.override(providers.Object(replace(LIMITS, **changes)))


def _visitor(client: TestClient) -> dict[str, str]:
    token = client.post("/api/v1/visitors").json()["visitorToken"]
    return {"X-Visitor-Token": token}


def _session(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post(SESSIONS, json={"characterSlug": "me"}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()["sessionId"]


def _send(client: TestClient, headers: dict[str, str], session_id: str, text: str = "안녕"):
    return client.post(f"{SESSIONS}/{session_id}/messages", json={"text": text}, headers=headers)


def _events(body: str) -> list[str]:
    return [block.split("\n")[0].removeprefix("event: ") for block in body.strip().split("\n\n")]


def test_session_returns_public_character_without_prompt(client: TestClient, llm) -> None:
    headers = _visitor(client)

    body = client.post(SESSIONS, json={"characterSlug": "me"}, headers=headers).json()

    assert body["character"] == {
        "slug": "me",
        "name": "상명",
        "greeting": "안녕하세요, 상명입니다.",
    }


def test_chat_requires_visitor_token(client: TestClient, llm) -> None:
    missing = client.post(SESSIONS, json={"characterSlug": "me"})
    forged = client.post(
        SESSIONS, json={"characterSlug": "me"}, headers={"X-Visitor-Token": "forged"}
    )

    assert missing.status_code == 401
    assert forged.json()["error"]["code"] == "invalid_visitor_token"


def test_unknown_character_is_404(client: TestClient, llm) -> None:
    response = client.post(SESSIONS, json={"characterSlug": "nobody"}, headers=_visitor(client))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "character_not_found"


def test_reply_streams_and_keeps_history(client: TestClient, container, llm: FakeLLM) -> None:
    headers = _visitor(client)
    session_id = _session(client, headers)

    response = _send(client, headers, session_id, "고향이 어디야?")

    assert _events(response.text) == ["delta", "delta", "done"]
    system, messages = llm.calls[0]
    assert "백엔드 개발자다." in system
    assert "고향은 부산" in system
    assert messages == [ChatMessage("user", "고향이 어디야?")]
    assert container.knowledge.service().character_ids == [CHARACTER.id]
    assert client.get(f"{SESSIONS}/{session_id}/messages", headers=headers).json() == [
        {"role": "user", "content": "고향이 어디야?"},
        {"role": "assistant", "content": "안녕하세요"},
    ]


def test_other_visitor_cannot_use_session(client: TestClient, llm: FakeLLM) -> None:
    owner = _visitor(client)
    session_id = _session(client, owner)
    stranger = _visitor(client)

    assert _send(client, stranger, session_id).status_code == 404
    assert client.get(f"{SESSIONS}/{session_id}/messages", headers=stranger).status_code == 404
    assert llm.calls == []


def test_llm_failure_ends_stream_with_error_and_skips_history(
    client: TestClient, llm: FakeLLM
) -> None:
    llm.fail = True
    headers = _visitor(client)
    session_id = _session(client, headers)

    response = _send(client, headers, session_id)

    assert _events(response.text)[-1] == "error"
    assert client.get(f"{SESSIONS}/{session_id}/messages", headers=headers).json() == []


def test_message_longer_than_limit_is_rejected(client: TestClient, container, llm) -> None:
    _limit(container, message_max_length=5)
    headers = _visitor(client)
    session_id = _session(client, headers)

    response = _send(client, headers, session_id, "여섯 글자 넘음")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "message_too_long"


def test_session_limit_has_no_retry_after(client: TestClient, container, llm) -> None:
    _limit(container, messages_per_session=1)
    headers = _visitor(client)
    session_id = _session(client, headers)

    assert _send(client, headers, session_id).status_code == 200
    blocked = _send(client, headers, session_id)

    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "session_message_limit"
    assert "Retry-After" not in blocked.headers
    # 새 대화를 열면 다시 보낼 수 있다.
    assert _send(client, headers, _session(client, headers)).status_code == 200


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"min_interval_seconds": 60}, "chat_too_fast"),
        ({"messages_per_visitor_per_day": 1}, "visitor_daily_limit"),
        ({"messages_per_ip_per_hour": 1}, "ip_hourly_limit"),
        ({"llm_calls_per_day": 1}, "daily_quota_exceeded"),
    ],
)
def test_limits_reject_second_message_with_retry_after(
    client: TestClient, container, llm: FakeLLM, changes: dict, code: str
) -> None:
    _limit(container, **changes)
    headers = _visitor(client)
    session_id = _session(client, headers)

    assert _send(client, headers, session_id).status_code == 200
    blocked = _send(client, headers, session_id)

    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == code
    assert int(blocked.headers["Retry-After"]) > 0
    assert len(llm.calls) == 1


def test_visitor_limit_survives_new_session(client: TestClient, container, llm) -> None:
    _limit(container, messages_per_visitor_per_day=1)
    headers = _visitor(client)
    _send(client, headers, _session(client, headers))

    blocked = _send(client, headers, _session(client, headers))

    assert blocked.json()["error"]["code"] == "visitor_daily_limit"


def test_visitor_tokens_are_limited_per_ip(client: TestClient, container, settings) -> None:
    container.settings.override(
        providers.Object(settings.model_copy(update={"visitor_tokens_per_ip_per_hour": 2}))
    )

    statuses = [client.post("/api/v1/visitors").status_code for _ in range(3)]

    assert statuses == [201, 201, 429]


def test_usage_is_admin_only(app, client: TestClient, llm) -> None:
    assert client.get("/api/v1/admin/usage").status_code == 401

    headers = _visitor(client)
    _send(client, headers, _session(client, headers))
    app.dependency_overrides[get_current_superuser] = lambda: UserRead(
        id=uuid.uuid4(),
        email="admin@example.com",
        full_name=None,
        is_active=True,
        is_superuser=True,
        created_at=NOW,
        updated_at=NOW,
    )

    assert client.get("/api/v1/admin/usage").json() == {
        "llmCallsToday": 1,
        "llmCallsPerDay": 500,
    }


def _as_admin(app) -> uuid.UUID:
    admin_id = uuid.uuid4()
    app.dependency_overrides[get_current_superuser] = lambda: UserRead(
        id=admin_id,
        email="admin@example.com",
        full_name=None,
        is_active=True,
        is_superuser=True,
        created_at=NOW,
        updated_at=NOW,
    )
    return admin_id


class FakeAllCharacters(FakeCharacters):
    async def get(self, character_id: uuid.UUID) -> CharacterRead:
        if character_id != CHARACTER.id:
            raise CharacterNotFoundError()
        return CHARACTER.model_copy(update={"is_public": False})


def test_admin_test_chat_shows_context_and_skips_limits(app, client, container, llm) -> None:
    container.character.service.override(FakeAllCharacters())
    _limit(container, messages_per_session=1, llm_calls_per_day=1)
    _as_admin(app)
    session = client.post(
        "/api/v1/admin/chat/sessions", json={"characterId": str(CHARACTER.id)}
    ).json()
    url = f"/api/v1/admin/chat/sessions/{session['sessionId']}/messages"

    first = client.post(url, json={"text": "고향이 어디예요?"})
    second = client.post(url, json={"text": "취미는요?"})

    assert _events(first.text) == ["context", "delta", "delta", "done"]
    context = first.text.split("\n\n")[0]
    assert "고향은 부산" in context and "systemPrompt" in context
    assert second.status_code == 200
    assert llm.calls[1][1][0] == ChatMessage("user", "고향이 어디예요?")
    assert client.get("/api/v1/admin/usage").json()["llmCallsToday"] == 0


def test_admin_test_chat_requires_admin(client, llm) -> None:
    response = client.post("/api/v1/admin/chat/sessions", json={"characterId": str(uuid.uuid4())})

    assert response.status_code == 401


def test_admin_page_is_served(client) -> None:
    response = client.get("/admin/")

    assert response.status_code == 200
    assert "/admin/characters" in response.text
