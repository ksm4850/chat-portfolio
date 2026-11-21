import json
import uuid
from collections.abc import AsyncIterator, Sequence
from dataclasses import replace
from datetime import UTC, date, datetime

import pytest
from dependency_injector import providers
from fastapi.testclient import TestClient

from src.infrastructure.llm import ChatMessage, LLMClient, LLMError, TokenUsage
from src.infrastructure.tracing import Step, Trace, Tracer
from src.interfaces.dependencies import get_current_superuser
from src.modules.character.service import SHORT_REPLY
from src.modules.chat.limits import ChatLimits
from src.modules.guide.history import InMemoryGuideHistory
from src.modules.guide.schema import (
    GuideDailyCount,
    GuideLatency,
    GuideLogCreate,
    GuideLogFilter,
    GuideLogPage,
    GuideLogRead,
    GuideModeCount,
    GuideOptions,
    GuideQuestionCount,
    GuideStats,
    GuideSummary,
)
from src.modules.guide.service import (
    GUIDE_REPLY,
    TEXT_NOTHING,
    TEXT_SOURCES_ONLY,
    GuideLogService,
)
from src.modules.knowledge.schema import SearchHit
from src.modules.knowledge.service import KnowledgeService
from src.modules.portfolio.markdown import contains_quote
from src.modules.portfolio.schema import SectionLocation
from src.modules.portfolio.service import PortfolioService
from src.modules.users.schema import UserRead
from tests.modules.portfolio.support import FakeCharacters, content_source, portfolio_service

RUN = "/api/v1/agui/run"
LIMITS = ChatLimits(
    message_max_length=500,
    min_interval_seconds=0,
    messages_per_session=20,
    messages_per_visitor_per_day=50,
    messages_per_ip_per_hour=60,
    llm_calls_per_day=500,
    session_ttl_seconds=3600,
)
OPTIONS = GuideOptions(
    character_slug="me",
    llm_enabled=True,
    search_limit=6,
    source_min_score=0.45,
    source_max_gap=1.0,
    action_min_score=0.55,
    history_turns=3,
    history_max_turns=8,
    history_answer_max_chars=400,
)
MEMORY_DOC = uuid.uuid4()
MANUAL_PLACEMENT = "어느 서비스를 어느 서버에 둘지 사람이 리소스 여유를 보고 직접 정하는 수동 배치"
ECS_DOC = uuid.uuid4()


def portfolio_hit(anchor: str, score: float, content: str = "본문") -> SearchHit:
    return SearchHit(
        document_id=ECS_DOC,
        title="AWS 인프라 구축·운영 및 ECS 전환 - 개요",
        content=content,
        score=score,
        meta={"view": "project", "anchor": anchor},
    )


def memory_hit(score: float) -> SearchHit:
    return SearchHit(
        document_id=MEMORY_DOC, title="경력 - 플레이아이디어랩", content="AWS 로 전환", score=score
    )


class FakeSearch(KnowledgeService):
    def __init__(self) -> None:
        self.hits: list[SearchHit] = []
        self.queries: list[list[str]] = []

    async def search_any(
        self, character_id: uuid.UUID, queries: Sequence[str], *, limit: int
    ) -> list[SearchHit]:
        self.queries.append(list(queries))
        return self.hits[:limit]


class ScriptedLLM(LLMClient):
    model = "fake-model"

    def __init__(self) -> None:
        self.deltas: list[str] = []
        self.fail = False
        self.calls: list[tuple[str, list[ChatMessage]]] = []
        self.cache_keys: list[str | None] = []

    async def stream(
        self,
        system: str,
        messages: Sequence[ChatMessage],
        usage: TokenUsage | None = None,
        *,
        cache_key: str | None = None,
    ) -> AsyncIterator[str]:
        self.calls.append((system, list(messages)))
        self.cache_keys.append(cache_key)
        if self.fail:
            raise LLMError("down")
        for delta in self.deltas:
            yield delta
        if usage is not None:
            usage.input_tokens, usage.output_tokens, usage.reasoning_tokens = 1200, 80, 16
            usage.cached_tokens = 1024


class FakeLogs(GuideLogService):
    def __init__(self) -> None:
        self.entries: list[GuideLogCreate] = []
        self.fail = False
        self.filters: GuideLogFilter | None = None
        self.page = GuideLogPage(items=[], total_count=0, offset=0, limit=50)
        self.stats_args: tuple[int, str] | None = None

    async def record(self, entry: GuideLogCreate) -> None:
        if self.fail:
            raise RuntimeError("db down")
        self.entries.append(entry)

    async def list(self, filters: GuideLogFilter, *, offset: int, limit: int) -> GuideLogPage:
        self.filters = filters
        return self.page

    async def stats(self, days: int, tz: str, *, top: int = 10, now=None) -> GuideStats:
        self.stats_args = (days, tz)
        return GuideStats(
            since=datetime(2026, 11, 18, 15, tzinfo=UTC),
            until=datetime(2026, 11, 19, 3, tzinfo=UTC),
            tz=tz,
            summary=GuideSummary(
                questions=3,
                visitors=2,
                threads=2,
                incomplete=1,
                latency=GuideLatency(
                    first_token_avg_ms=900.0,
                    first_token_p95_ms=1500.0,
                    total_avg_ms=4000.0,
                    total_p95_ms=7000.0,
                ),
            ),
            daily=[GuideDailyCount(date=date(2026, 11, 19), questions=3, visitors=2)],
            modes=[GuideModeCount(mode="llm", count=3)],
            top_questions=[GuideQuestionCount(question="AWS 전환은 왜?", count=2)],
        )


class RecordedStep(Step):
    def __init__(self, name: str, kind: str, input, model: str | None) -> None:
        self.name, self.kind, self.input, self.model = name, kind, input, model
        self.first_token_seen = False
        self.ended: dict | None = None

    def first_token(self) -> None:
        self.first_token_seen = True

    def end(self, *, output=None, usage=None, error=None) -> None:
        self.ended = {"output": output, "usage": usage, "error": error}


class RecordedTrace(Trace):
    def __init__(self, **start) -> None:
        self.start = start
        self.steps: list[RecordedStep] = []
        self.ended: dict | None = None

    @property
    def trace_id(self) -> str | None:
        return "trace-x"

    def step(self, name, *, kind, input, model=None) -> Step:
        step = RecordedStep(name, kind, input, model)
        self.steps.append(step)
        return step

    def end(self, *, output=None, metadata=None, error=None) -> None:
        self.ended = {"output": output, "metadata": metadata, "error": error}


class RecordingTracer(Tracer):
    def __init__(self) -> None:
        self.traces: list[RecordedTrace] = []

    def start(self, name, *, user_id, session_id, input, metadata) -> Trace:
        trace = RecordedTrace(
            name=name, user_id=user_id, session_id=session_id, input=input, metadata=metadata
        )
        self.traces.append(trace)
        return trace

    def shutdown(self) -> None:
        pass


@pytest.fixture
def tracer(container) -> RecordingTracer:
    fake = RecordingTracer()
    container.infrastructure.tracer.override(providers.Object(fake))
    return fake


@pytest.fixture
def logs(container) -> FakeLogs:
    fake = FakeLogs()
    container.guide.log_service.override(providers.Object(fake))
    return fake


@pytest.fixture
async def portfolio() -> PortfolioService:
    service = portfolio_service()
    await service.ingest(content_source())
    return service


@pytest.fixture
def search(
    container, portfolio: PortfolioService, logs: FakeLogs, tracer: RecordingTracer
) -> FakeSearch:
    fake = FakeSearch()
    container.knowledge.service.override(fake)
    container.portfolio.service.override(providers.Object(portfolio))
    container.character.service.override(FakeCharacters())
    container.chat_limits.override(providers.Object(LIMITS))
    container.guide_options.override(providers.Object(OPTIONS))
    return fake


@pytest.fixture
def llm(container, search: FakeSearch) -> ScriptedLLM:
    fake = ScriptedLLM()
    container.infrastructure.llm.override(fake)
    return fake


def _options(container, **changes) -> None:
    container.guide_options.override(providers.Object(replace(OPTIONS, **changes)))


def _headers(client: TestClient) -> dict[str, str]:
    return {"X-Visitor-Token": client.post("/api/v1/visitors").json()["visitorToken"]}


def _body(question: str = "인프라를 AWS로 변경하면서 어떤 문제를 겪었나요?", **extra) -> dict:
    return {
        "threadId": "thread_1",
        "runId": "run_1",
        "messages": [
            {"id": "m0", "role": "user", "content": "이전 질문"},
            {"id": "a0", "role": "assistant", "content": "이전 답"},
            {"id": "m1", "role": "user", "content": question},
        ],
        "tools": [],
        "context": [],
        "state": {},
        "forwardedProps": {"capabilities": ["navigate@1", "highlight@1"]},
        **extra,
    }


def _run(
    client: TestClient, body: dict | None = None, headers: dict[str, str] | None = None
) -> list[dict]:
    response = client.post(RUN, json=body or _body(), headers=headers or _headers(client))
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    return [
        json.loads(block.removeprefix("data: "))
        for block in response.text.strip().split("\n\n")
        if block
    ]


def _shape(events: list[dict]) -> list[str]:
    """이벤트 순서를 읽기 쉽게 줄인다. 연속 TEXT_MESSAGE_CONTENT 는 하나로 본다."""
    shape: list[str] = []
    for event in events:
        kind = event["type"]
        if kind == "CUSTOM":
            label = f"CUSTOM:{event['name']}"
            if event["name"] == "mode":
                label += f"={event['value']}"
        elif kind == "TOOL_CALL_START":
            label = f"TOOL:{event['toolCallName']}"
        elif kind in ("TOOL_CALL_ARGS", "TOOL_CALL_END"):
            continue
        else:
            label = kind
        if not (shape and label == shape[-1] == "TEXT_MESSAGE_CONTENT"):
            shape.append(label)
    return shape


def _text(events: list[dict]) -> str:
    return "".join(e["delta"] for e in events if e["type"] == "TEXT_MESSAGE_CONTENT")


def _tools(events: list[dict]) -> list[tuple[str, dict]]:
    names = {e["toolCallId"]: e["toolCallName"] for e in events if e["type"] == "TOOL_CALL_START"}
    return [
        (names[e["toolCallId"]], json.loads(e["delta"]))
        for e in events
        if e["type"] == "TOOL_CALL_ARGS"
    ]


def _sources(events: list[dict]) -> list[dict]:
    return next(e["value"] for e in events if e["type"] == "CUSTOM" and e["name"] == "sources")


@pytest.fixture
async def locations(portfolio: PortfolioService) -> dict[str, SectionLocation]:
    return await portfolio.locations()


def test_fallback_opens_top_section_after_text(client, container, search, locations) -> None:
    _options(container, llm_enabled=False)
    search.hits = [
        portfolio_hit("ecs-overview-2", 0.66, "Traefik 단일 진입점"),
        portfolio_hit("ecs-overview-2", 0.65),
        memory_hit(0.6),
        portfolio_hit("ecs-overview-3", 0.5),
        portfolio_hit("ecs-overview-1", 0.47),
    ]

    events = _run(client)

    assert _shape(events) == [
        "RUN_STARTED",
        "CUSTOM:mode=fallback",
        "CUSTOM:sources",
        "TEXT_MESSAGE_START",
        "TEXT_MESSAGE_CONTENT",
        "TEXT_MESSAGE_END",
        "TOOL:navigate",
        "TOOL:highlight",
        "RUN_FINISHED",
    ]
    assert events[0] == {"type": "RUN_STARTED", "threadId": "thread_1", "runId": "run_1"}
    sources = _sources(events)
    assert [s["location"] and s["location"]["anchor"] for s in sources] == [
        "ecs-overview-2",
        None,
        "ecs-overview-3",
    ]
    assert sources[0]["title"] == (
        "AWS 인프라 구축·운영 및 ECS 전환 - 개요 > 1차: AWS + Docker Swarm 통합 - 요금 최적화"
    )
    assert sources[0]["snippet"] == "Traefik 단일 진입점"
    [(_, navigate), (_, highlight)] = _tools(events)
    assert navigate == {"view": "project", "projectId": "ecs", "tab": "overview"}
    assert highlight["anchor"] == "ecs-overview-2"
    assert contains_quote(locations["ecs-overview-2"].plain, highlight["quote"])
    assert len(highlight["quote"]) <= 80
    assert _text(events).startswith("관련 내용을 찾았습니다.")


def test_fallback_without_location_on_top_sends_sources_only(client, container, search) -> None:
    _options(container, llm_enabled=False)
    search.hits = [memory_hit(0.7), portfolio_hit("ecs-overview-2", 0.6)]

    events = _run(client)

    assert _text(events) == TEXT_SOURCES_ONLY
    assert _tools(events) == []
    assert len(_sources(events)) == 2


def test_fallback_below_action_score_does_not_move_screen(client, container, search) -> None:
    _options(container, llm_enabled=False)
    search.hits = [portfolio_hit("ecs-overview-2", 0.5)]

    events = _run(client)

    assert _text(events) == TEXT_SOURCES_ONLY
    assert _tools(events) == []


def test_unrelated_question_gets_no_sources(client, container, search) -> None:
    _options(container, llm_enabled=False)
    search.hits = [memory_hit(0.44), portfolio_hit("ecs-overview-2", 0.4)]

    events = _run(client, _body("좋아하는 음식은?"))

    assert _sources(events) == []
    assert _text(events) == TEXT_NOTHING
    assert "TEXT_MESSAGE_END" in _shape(events)


def test_llm_markers_become_tool_calls_inside_text(client, search, llm: ScriptedLLM) -> None:
    search.hits = [portfolio_hit("ecs-overview-2", 0.66), memory_hit(0.6)]
    answer = (
        "수동 배치였습니다."
        f"[[show:ecs-overview-1|{MANUAL_PLACEMENT}]]"
        " Swarm 으로 합쳤습니다.[[show:ecs-overview-2|서버마다 각자 운영하던 Nginx를 없애고]]"
        " 없는 위치[[show:nope-x-1]]"
        " 틀린 인용[[show:ecs-overview-3|이런 문장은 없습니다]] 끝입니다."
    )
    llm.deltas = [answer[i : i + 7] for i in range(0, len(answer), 7)]

    events = _run(client)

    assert _shape(events) == [
        "RUN_STARTED",
        "CUSTOM:mode=llm",
        "CUSTOM:sources",
        "TEXT_MESSAGE_START",
        "TEXT_MESSAGE_CONTENT",
        "TOOL:navigate",
        "TOOL:highlight",
        "TEXT_MESSAGE_CONTENT",
        # 같은 탭이라 navigate 없이 highlight 만
        "TOOL:highlight",
        "TEXT_MESSAGE_CONTENT",
        "TOOL:highlight",
        "TEXT_MESSAGE_CONTENT",
        "TEXT_MESSAGE_END",
        "RUN_FINISHED",
    ]
    assert _tools(events) == [
        ("navigate", {"view": "project", "projectId": "ecs", "tab": "overview"}),
        (
            "highlight",
            {
                "anchor": "ecs-overview-1",
                "quote": MANUAL_PLACEMENT,
            },
        ),
        (
            "highlight",
            {"anchor": "ecs-overview-2", "quote": "서버마다 각자 운영하던 Nginx를 없애고"},
        ),
        ("highlight", {"anchor": "ecs-overview-3"}),
    ]
    assert (
        _text(events) == "수동 배치였습니다. Swarm 으로 합쳤습니다. 없는 위치 틀린 인용 끝입니다."
    )
    tool_parents = {e["parentMessageId"] for e in events if e["type"] == "TOOL_CALL_START"}
    assert tool_parents == {events[3]["messageId"]}


def test_view_markers_switch_screens(client, search, llm: ScriptedLLM, logs) -> None:
    search.hits = [portfolio_hit("ecs-overview-2", 0.66)]
    llm.deltas = [
        "모은넷에서 일했습니다.[[view:career]]",
        " 같은 화면[[view:career]] 없는 화면[[view:blog]]",
        " ECS 로 옮겼습니다.[[show:ecs-overview-2]] 다시 경력[[view:career]] 끝.",
    ]

    events = _run(client)

    assert _tools(events) == [
        ("navigate", {"view": "career"}),
        ("navigate", {"view": "project", "projectId": "ecs", "tab": "overview"}),
        ("highlight", {"anchor": "ecs-overview-2"}),
        ("navigate", {"view": "career"}),
    ]
    assert _text(events) == (
        "모은넷에서 일했습니다. 같은 화면 없는 화면 ECS 로 옮겼습니다. 다시 경력 끝."
    )
    assert logs.entries[0].anchors == [
        "view:career",
        "view:career",
        "ecs-overview-2",
        "view:career",
    ]


def test_view_marker_needs_navigate_capability(client, search, llm: ScriptedLLM) -> None:
    llm.deltas = ["기술 스택입니다.[[view:skills]]"]
    body = _body(forwardedProps={"capabilities": ["highlight@1"]})

    events = _run(client, body)

    assert _tools(events) == []
    assert _text(events) == "기술 스택입니다."


def test_llm_prompt_puts_materials_with_question_not_client_history(client, search, llm) -> None:
    search.hits = [portfolio_hit("ecs-overview-2", 0.66), memory_hit(0.6), memory_hit(0.3)]
    llm.deltas = ["답입니다."]

    _run(client)

    system, messages = llm.calls[0]
    assert "[[show:" in system
    assert GUIDE_REPLY in system
    assert "## 답할 범위" in system
    assert SHORT_REPLY not in system
    assert "[자료" not in system
    # 클라이언트가 보낸 이전 메시지("이전 질문")는 믿지 않는다.
    [message] = messages
    content = message.content
    assert message.role == "user"
    assert "[자료 1] anchor=ecs-overview-2 (AWS 인프라 구축·운영 및 ECS 전환 > 개요 > " in content
    assert "[자료 2] (기억 문서: 경력 - 플레이아이디어랩)" in content
    assert "[자료 3]" not in content
    assert "이전 질문" not in content
    assert content.endswith("## 질문\n인프라를 AWS로 변경하면서 어떤 문제를 겪었나요?")
    assert llm.cache_keys == ["guide:me"]


def test_llm_failure_switches_to_fallback_in_same_run(client, search, llm: ScriptedLLM) -> None:
    search.hits = [portfolio_hit("ecs-overview-2", 0.66)]
    llm.fail = True

    events = _run(client)

    assert _shape(events) == [
        "RUN_STARTED",
        "CUSTOM:mode=llm",
        "CUSTOM:sources",
        "CUSTOM:mode=fallback",
        "TEXT_MESSAGE_START",
        "TEXT_MESSAGE_CONTENT",
        "TEXT_MESSAGE_END",
        "TOOL:navigate",
        "TOOL:highlight",
        "RUN_FINISHED",
    ]


def test_daily_llm_quota_exceeded_falls_back_instead_of_429(
    client, container, search, llm: ScriptedLLM
) -> None:
    container.chat_limits.override(providers.Object(replace(LIMITS, llm_calls_per_day=1)))
    search.hits = [portfolio_hit("ecs-overview-2", 0.66)]
    llm.deltas = ["답입니다."]

    first = _run(client)
    second = _run(client)

    assert _shape(first)[1] == "CUSTOM:mode=llm"
    assert _shape(second)[1] == "CUSTOM:mode=fallback"
    assert len(llm.calls) == 1


def test_capabilities_filter_tools(client, container, search) -> None:
    _options(container, llm_enabled=False)
    search.hits = [portfolio_hit("ecs-overview-2", 0.66)]
    body = _body(forwardedProps={"capabilities": ["highlight@1", "navigate@2"]})

    events = _run(client, body)

    assert [name for name, _ in _tools(events)] == ["highlight"]


def test_run_requires_visitor_token(client, search) -> None:
    response = client.post(RUN, json=_body())

    assert response.status_code == 401


def test_run_without_user_message_is_422(client, search) -> None:
    body = _body()
    body["messages"] = [{"id": "a0", "role": "assistant", "content": "답"}]

    response = client.post(RUN, json=body, headers=_headers(client))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "no_user_message"


def test_visitor_limit_is_429_before_stream(client, container, search) -> None:
    _options(container, llm_enabled=False)
    container.chat_limits.override(
        providers.Object(replace(LIMITS, messages_per_visitor_per_day=1))
    )
    headers = _headers(client)

    assert client.post(RUN, json=_body(), headers=headers).status_code == 200
    blocked = client.post(RUN, json=_body(), headers=headers)

    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "visitor_daily_limit"


def _with_ga(ga_client_id: str) -> dict:
    return _body(
        forwardedProps={"capabilities": ["navigate@1", "highlight@1"], "gaClientId": ga_client_id}
    )


def test_run_is_recorded_with_ga_client_id(client, llm, search, logs) -> None:
    search.hits = [portfolio_hit("ecs-overview-2", 0.7), memory_hit(0.5)]
    llm.deltas = ["Traefik 으로 합쳤습니다.", "[[show:ecs-overview-2]]"]

    events = _run(client, _with_ga("1234567890.1700000000"))

    [entry] = logs.entries
    assert entry.question == "인프라를 AWS로 변경하면서 어떤 문제를 겪었나요?"
    assert entry.answer == _text(events) == "Traefik 으로 합쳤습니다."
    assert entry.mode == "llm"
    assert entry.anchors == ["ecs-overview-2"]
    assert entry.scores == [0.7, 0.5]
    assert entry.thread_id == "thread_1"
    assert entry.ga_client_id == "1234567890.1700000000"
    assert entry.completed is True
    assert entry.first_token_ms is not None
    assert (entry.input_tokens, entry.output_tokens, entry.reasoning_tokens) == (1200, 80, 16)
    assert entry.cached_tokens == 1024


@pytest.mark.parametrize("value", ["GA1.1.123.456", "<script>", "1.2.3", ""])
def test_malformed_ga_client_id_is_dropped(client, llm, search, logs, value) -> None:
    _run(client, _with_ga(value))

    assert logs.entries[0].ga_client_id is None


def test_llm_failure_is_recorded_as_fallback(client, llm, search, logs) -> None:
    search.hits = [portfolio_hit("ecs-overview-2", 0.7)]
    llm.fail = True

    events = _run(client)

    [entry] = logs.entries
    assert entry.mode == "fallback"
    assert entry.answer == _text(events)
    assert entry.input_tokens is None
    assert entry.anchors == ["ecs-overview-2"]


def test_record_failure_does_not_break_run(client, llm, search, logs) -> None:
    logs.fail = True
    llm.deltas = ["답변입니다."]

    events = _run(client)

    assert _text(events) == "답변입니다."
    assert events[-1]["type"] == "RUN_FINISHED"


def _superuser() -> UserRead:
    return UserRead(
        id=uuid.uuid4(),
        email="admin@example.com",
        full_name=None,
        is_active=True,
        is_superuser=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def test_admin_lists_logs_with_filters(app, client, logs) -> None:
    app.dependency_overrides[get_current_superuser] = _superuser
    visitor = uuid.uuid4()
    log = GuideLogRead(
        id=uuid.uuid4(),
        created_at=datetime.now(UTC),
        visitor_id=visitor,
        thread_id="thread_1",
        ga_client_id="1.2",
        question="질문",
        answer="답",
        mode="llm",
        scores=[0.5],
        anchors=[],
        first_token_ms=10.0,
        total_ms=20.0,
        completed=True,
        input_tokens=1200,
        output_tokens=80,
        reasoning_tokens=None,
        cached_tokens=None,
        trace_id="trace-x",
    )
    logs.page = GuideLogPage(items=[log], total_count=1, offset=0, limit=20)

    response = client.get(
        "/api/v1/admin/guide/logs",
        params={"visitorId": str(visitor), "gaClientId": "1.2", "q": "AWS", "limit": 20},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["totalCount"] == 1
    assert body["items"][0]["gaClientId"] == "1.2"
    assert body["items"][0]["firstTokenMs"] == 10.0
    assert body["items"][0]["inputTokens"] == 1200
    assert body["items"][0]["traceId"] == "trace-x"
    assert logs.filters == GuideLogFilter(visitor_id=visitor, ga_client_id="1.2", query="AWS")


def test_admin_reads_stats(app, client, logs) -> None:
    app.dependency_overrides[get_current_superuser] = _superuser

    response = client.get("/api/v1/admin/guide/stats", params={"days": 30, "tz": "UTC"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert logs.stats_args == (30, "UTC")
    assert body["summary"]["latency"]["firstTokenP95Ms"] == 1500.0
    assert body["daily"] == [{"date": "2026-11-19", "questions": 3, "visitors": 2}]
    assert body["topQuestions"] == [{"question": "AWS 전환은 왜?", "count": 2}]


def test_admin_stats_defaults_and_limits(app, client, logs) -> None:
    app.dependency_overrides[get_current_superuser] = _superuser

    assert client.get("/api/v1/admin/guide/stats").status_code == 200
    assert logs.stats_args == (7, "Asia/Seoul")
    assert client.get("/api/v1/admin/guide/stats", params={"days": 91}).status_code == 422


def test_run_is_traced_step_by_step(client, llm, search, logs, tracer) -> None:
    search.hits = [portfolio_hit("ecs-overview-2", 0.7, "Traefik 단일 진입점"), memory_hit(0.5)]
    llm.deltas = ["Traefik 으로 합쳤습니다.", "[[show:ecs-overview-2]]"]

    events = _run(client, _with_ga("1234567890.1700000000"))

    [trace] = tracer.traces
    assert trace.start["user_id"] == str(logs.entries[0].visitor_id)
    assert trace.start["session_id"] == "thread_1"
    assert trace.start["metadata"] == {"gaClientId": "1234567890.1700000000"}
    retrieval, generation = trace.steps
    assert (retrieval.name, retrieval.kind) == ("retrieval", "retriever")
    assert [hit["anchor"] for hit in retrieval.ended["output"]] == ["ecs-overview-2", None]
    assert (generation.kind, generation.model) == ("generation", "fake-model")
    assert generation.input[0]["role"] == "system"
    assert generation.first_token_seen
    assert generation.ended["output"] == "Traefik 으로 합쳤습니다.[[show:ecs-overview-2]]"
    assert generation.ended["usage"].input_tokens == 1200
    assert generation.ended["error"] is None
    assert trace.ended["output"] == _text(events)
    assert trace.ended["metadata"]["mode"] == "llm"
    assert logs.entries[0].trace_id == "trace-x"


def test_llm_failure_is_traced_as_error(client, llm, search, tracer) -> None:
    llm.fail = True

    _run(client)

    [trace] = tracer.traces
    generation = trace.steps[-1]
    assert generation.ended["error"] == "down"
    assert trace.ended["metadata"]["mode"] == "fallback"


def test_failure_before_stream_closes_trace(client, container, search, tracer) -> None:
    class BrokenSearch(FakeSearch):
        async def search_any(self, character_id, queries, *, limit):
            raise RuntimeError("search down")

    container.knowledge.service.override(BrokenSearch())

    with pytest.raises(RuntimeError):
        client.post(RUN, json=_body(), headers=_headers(client))

    [trace] = tracer.traces
    assert trace.ended["error"] == "RuntimeError: search down"


def _ask(question: str, thread: str = "thread_1") -> dict:
    return _body(question, threadId=thread)


def test_follow_up_question_gets_previous_turn_as_conversation(client, search, llm) -> None:
    search.hits = [portfolio_hit("ecs-overview-2", 0.66)]
    headers = _headers(client)
    llm.deltas = ["Traefik 으로 합쳤습니다.", "[[show:ecs-overview-2]]", "[[view:career]]"]
    _run(client, _ask("진입점은 어떻게 바꿨나요?"), headers)

    llm.deltas = ["설정이 단순해서입니다."]
    _run(client, _ask("그건 왜 골랐어요?"), headers)

    first_system, _ = llm.calls[0]
    system, messages = llm.calls[1]
    # 자료가 system 밖에 있어 앞부분이 매번 같다(프롬프트 캐시).
    assert system == first_system
    assert messages[:2] == [
        ChatMessage("user", "진입점은 어떻게 바꿨나요?"),
        ChatMessage("assistant", "Traefik 으로 합쳤습니다.[[show:ecs-overview-2]][[view:career]]"),
    ]
    assert messages[2].content.endswith("## 질문\n그건 왜 골랐어요?")
    assert "## 앞서 나온 질문" not in messages[2].content
    assert search.queries[1] == [
        "그건 왜 골랐어요?",
        "진입점은 어떻게 바꿨나요?\n그건 왜 골랐어요?",
    ]


def test_old_turns_keep_only_questions_and_long_answers_are_cut(
    client, container, search, llm
) -> None:
    _options(container, history_turns=2, history_answer_max_chars=10)
    headers = _headers(client)
    for i in range(4):
        llm.deltas = [f"{i}번 답변은 열 글자를 훌쩍 넘습니다."]
        _run(client, _ask(f"질문 {i}"), headers)

    _, messages = llm.calls[-1]
    assert [m.content for m in messages[:-1]] == [
        "질문 1",
        "1번 답변은 열 글…",
        "질문 2",
        "2번 답변은 열 글…",
    ]
    assert "## 앞서 나온 질문\n- 질문 0\n\n## 자료" in messages[-1].content


def test_history_is_per_visitor_and_thread(client, search, llm) -> None:
    llm.deltas = ["답입니다."]
    headers = _headers(client)
    _run(client, _ask("첫 질문"), headers)

    _run(client, _ask("다른 방문자 질문"), _headers(client))
    _run(client, _ask("새 대화 질문", thread="thread_2"), headers)

    for _, messages in llm.calls[1:]:
        assert len(messages) == 1
        assert "첫 질문" not in messages[0].content
    assert search.queries[1:] == [["다른 방문자 질문"], ["새 대화 질문"]]


def test_fallback_answer_is_remembered(client, search, llm) -> None:
    search.hits = [portfolio_hit("ecs-overview-2", 0.66)]
    headers = _headers(client)
    llm.fail = True
    _run(client, _ask("진입점은 어떻게 바꿨나요?"), headers)

    llm.fail = False
    llm.deltas = ["답입니다."]
    _run(client, _ask("더 자세히요"), headers)

    _, messages = llm.calls[-1]
    assert messages[0] == ChatMessage("user", "진입점은 어떻게 바꿨나요?")
    assert messages[1].content.startswith("관련 내용을 찾았습니다.")
    assert messages[1].content.endswith("[[show:ecs-overview-2]]")


def test_history_failure_does_not_break_reply(client, container, search, llm) -> None:
    class BrokenHistory(InMemoryGuideHistory):
        async def append(self, visitor_id, thread_id, turn) -> None:
            raise ConnectionError("redis down")

    container.guide.history.override(BrokenHistory())
    llm.deltas = ["답입니다."]

    events = _run(client, _ask("질문"))

    assert _text(events) == "답입니다."


def test_history_read_failure_answers_without_context(client, container, search, llm) -> None:
    class BrokenHistory(InMemoryGuideHistory):
        async def recent(self, visitor_id, thread_id):
            raise ConnectionError("redis down")

    container.guide.history.override(BrokenHistory())
    llm.deltas = ["답입니다."]

    events = _run(client, _ask("질문"))

    assert _text(events) == "답입니다."
    _, messages = llm.calls[0]
    assert len(messages) == 1


def test_no_thread_id_neither_reads_nor_writes_history(client, container, search, llm) -> None:
    llm.deltas = ["답입니다."]
    headers = _headers(client)

    _run(client, _ask("첫 질문", thread=""), headers)
    _run(client, _ask("둘째 질문", thread=""), headers)

    _, messages = llm.calls[1]
    assert len(messages) == 1
    assert container.guide.history()._turns == {}


async def test_disconnected_run_is_logged_but_not_remembered(container, search, llm, logs) -> None:
    llm.deltas = ["답의 ", "앞부분만 ", "보냈다."]
    visitor_id = uuid.uuid4()
    service = container.guide.service()

    events = await service.start(visitor_id, "127.0.0.1", "질문", None, thread_id="thread_1")
    await anext(events)
    await events.aclose()

    [entry] = logs.entries
    assert entry.completed is False
    assert await container.guide.history().recent(visitor_id, "thread_1") == []
