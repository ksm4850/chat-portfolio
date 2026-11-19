import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import text

from src.core.config import Settings
from src.core.container import AppContainer
from src.infrastructure.database import Database
from src.modules.guide.exceptions import UnknownTimezoneError
from src.modules.guide.models import GuideLog
from src.modules.guide.schema import GuideLogCreate, GuideLogFilter
from src.modules.guide.service import GuideLogService

pytestmark = pytest.mark.integration

THREAD = "thread_it"


@pytest.fixture
async def container() -> AsyncIterator[AppContainer]:
    container = AppContainer(
        settings=Settings(environment="local", jwt_secret_key="integration-test-secret")
    )
    database = container.infrastructure().database()
    try:
        await database.ping()
    except Exception as exc:
        await database.dispose()
        pytest.skip(f"실제 DB를 쓸 수 없다: {type(exc).__name__}")
    yield container
    async with database.transaction() as session:
        await session.execute(text("DELETE FROM guide_logs WHERE thread_id = :t"), {"t": THREAD})
    await database.dispose()


@pytest.fixture
def service(container: AppContainer) -> GuideLogService:
    return container.guide().log_service()


@pytest.fixture
def database(container: AppContainer) -> Database:
    return container.infrastructure().database()


def _entry(visitor_id: uuid.UUID, question: str, ga_client_id: str | None = None) -> GuideLogCreate:
    return GuideLogCreate(
        visitor_id=visitor_id,
        thread_id=THREAD,
        ga_client_id=ga_client_id,
        question=question,
        answer="답",
        mode="llm",
        scores=[0.61, 0.5],
        anchors=["cq-decisions-2"],
        first_token_ms=12.5,
        total_ms=40.0,
        completed=True,
        input_tokens=1500,
        output_tokens=120,
        reasoning_tokens=None,
        cached_tokens=768,
        trace_id="trace-it",
    )


async def test_record_and_filter(service: GuideLogService) -> None:
    visitor = uuid.uuid4()
    await service.record(_entry(visitor, "AWS 전환은 왜 했나요?", "111.222"))
    await service.record(_entry(visitor, "NATS 를 고른 이유는?"))

    page = await service.list(GuideLogFilter(visitor_id=visitor), offset=0, limit=10)
    assert page.total_count == 2
    assert [log.question for log in page.items] == ["NATS 를 고른 이유는?", "AWS 전환은 왜 했나요?"]
    assert page.items[1].scores == [0.61, 0.5]
    assert page.items[1].anchors == ["cq-decisions-2"]
    assert (page.items[1].input_tokens, page.items[1].output_tokens) == (1500, 120)

    by_ga = await service.list(
        GuideLogFilter(visitor_id=visitor, ga_client_id="111.222"), offset=0, limit=10
    )
    assert [log.question for log in by_ga.items] == ["AWS 전환은 왜 했나요?"]

    by_text = await service.list(
        GuideLogFilter(visitor_id=visitor, query="nats"), offset=0, limit=10
    )
    assert by_text.total_count == 1

    later = await service.list(
        GuideLogFilter(visitor_id=visitor, since=datetime.now(UTC) + timedelta(minutes=1)),
        offset=0,
        limit=10,
    )
    assert later.total_count == 0


# 실제 기록과 섞이지 않도록 아주 오래전 시각에 넣는다.
PAST = datetime(2001, 3, 10, 12, tzinfo=UTC)


def _log(at: datetime, visitor: uuid.UUID, question: str, **fields) -> GuideLog:
    values = vars(_entry(visitor, question)) | fields
    return GuideLog(created_at=at, **values)


async def test_stats_by_local_day(service: GuideLogService, database: Database) -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    async with database.transaction() as session:
        session.add_all(
            [
                # 서울 기준 3월 10일 00:30. UTC 로는 9일이다.
                _log(datetime(2001, 3, 9, 15, 30, tzinfo=UTC), a, "AWS 전환은 왜 했나요?"),
                _log(PAST, a, "aws 전환은 왜 했나요? ", total_ms=100.0, completed=False),
                _log(PAST, b, "NATS 를 고른 이유는?", mode="fallback", first_token_ms=None),
                # 범위 밖(3일 전)
                _log(PAST - timedelta(days=3), b, "범위 밖"),
            ]
        )

    stats = await service.stats(2, "Asia/Seoul", now=PAST + timedelta(hours=1))

    assert stats.since == datetime(2001, 3, 8, 15, tzinfo=UTC)
    assert stats.summary.questions == 3
    assert stats.summary.visitors == 2
    assert stats.summary.threads == 1
    assert stats.summary.incomplete == 1
    assert stats.summary.latency.first_token_avg_ms == 12.5
    assert stats.summary.latency.total_avg_ms == pytest.approx(60.0)
    assert [(d.date, d.questions, d.visitors) for d in stats.daily] == [
        (date(2001, 3, 9), 0, 0),
        (date(2001, 3, 10), 3, 2),
    ]
    assert [(m.mode, m.count) for m in stats.modes] == [("llm", 2), ("fallback", 1)]
    assert [(q.question, q.count) for q in stats.top_questions] == [
        ("aws 전환은 왜 했나요? ", 2),
        ("NATS 를 고른 이유는?", 1),
    ]


async def test_stats_rejects_unknown_timezone(service: GuideLogService) -> None:
    with pytest.raises(UnknownTimezoneError):
        await service.stats(7, "Mars/Olympus")
