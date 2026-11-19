from collections.abc import Sequence
from datetime import date, datetime

from sqlalchemy import ColumnElement, func, select, text
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database import BaseRepository
from src.modules.guide.models import GuideLog
from src.modules.guide.schema import (
    GuideLatency,
    GuideLogFilter,
    GuideModeCount,
    GuideQuestionCount,
    GuideSummary,
)


class GuideLogRepository(BaseRepository[GuideLog]):
    model = GuideLog

    async def search(
        self, session: AsyncSession, filters: GuideLogFilter, *, offset: int, limit: int
    ) -> tuple[Sequence[GuideLog], int]:
        """최신순 목록과 필터에 맞는 전체 건수."""
        where = _conditions(filters)
        total = await self.count(session, *where)
        rows = await self.find(
            session,
            *where,
            order_by=(GuideLog.created_at.desc(), GuideLog.id),
            offset=offset,
            limit=limit,
        )
        return rows, total

    async def summary(
        self, session: AsyncSession, since: datetime, until: datetime
    ) -> GuideSummary:
        p95 = func.percentile_cont(0.95)
        row = (
            await session.execute(
                select(
                    func.count(),
                    func.count(GuideLog.visitor_id.distinct()),
                    func.count(GuideLog.thread_id.distinct()),
                    func.count().filter(GuideLog.completed.is_(False)),
                    func.avg(GuideLog.first_token_ms),
                    p95.within_group(GuideLog.first_token_ms),
                    func.avg(GuideLog.total_ms),
                    p95.within_group(GuideLog.total_ms),
                ).where(*_window(since, until))
            )
        ).one()
        return GuideSummary(
            questions=row[0],
            visitors=row[1],
            threads=row[2],
            incomplete=row[3],
            latency=GuideLatency(
                first_token_avg_ms=row[4],
                first_token_p95_ms=row[5],
                total_avg_ms=row[6],
                total_p95_ms=row[7],
            ),
        )

    async def daily(
        self, session: AsyncSession, since: datetime, until: datetime, tz: str
    ) -> list[tuple[date, int, int]]:
        """`tz` 날짜별 (날짜, 질문 수, 방문자 수). 기록이 없는 날은 빠진다."""
        day = func.date(func.timezone(tz, GuideLog.created_at))
        # tz 가 바인드 파라미터라 GROUP BY 에 같은 식을 다시 쓰면 다른 식으로 본다. 위치로 묶는다.
        rows = await session.execute(
            select(day, func.count(), func.count(GuideLog.visitor_id.distinct()))
            .where(*_window(since, until))
            .group_by(text("1"))
            .order_by(text("1"))
        )
        return [(row[0], row[1], row[2]) for row in rows]

    async def modes(
        self, session: AsyncSession, since: datetime, until: datetime
    ) -> list[GuideModeCount]:
        count = func.count()
        rows = await session.execute(
            select(GuideLog.mode, count)
            .where(*_window(since, until))
            .group_by(GuideLog.mode)
            .order_by(count.desc(), GuideLog.mode)
        )
        return [GuideModeCount(mode=row[0], count=row[1]) for row in rows]

    async def top_questions(
        self, session: AsyncSession, since: datetime, until: datetime, limit: int
    ) -> list[GuideQuestionCount]:
        """대소문자·앞뒤 공백만 다른 질문은 같은 질문으로 센다. 표시는 가장 최근 원문."""
        key = func.lower(func.btrim(GuideLog.question))
        count = func.count()
        latest = func.max(GuideLog.created_at)
        question = func.array_agg(
            aggregate_order_by(GuideLog.question, GuideLog.created_at.desc())
        )[1]
        rows = await session.execute(
            select(question, count)
            .where(*_window(since, until))
            .group_by(key)
            .order_by(count.desc(), latest.desc())
            .limit(limit)
        )
        return [GuideQuestionCount(question=row[0], count=row[1]) for row in rows]


def _window(since: datetime, until: datetime) -> list[ColumnElement[bool]]:
    return [GuideLog.created_at >= since, GuideLog.created_at < until]


def _conditions(filters: GuideLogFilter) -> list[ColumnElement[bool]]:
    where: list[ColumnElement[bool]] = []
    if filters.visitor_id is not None:
        where.append(GuideLog.visitor_id == filters.visitor_id)
    if filters.thread_id:
        where.append(GuideLog.thread_id == filters.thread_id)
    if filters.ga_client_id:
        where.append(GuideLog.ga_client_id == filters.ga_client_id)
    if filters.query:
        where.append(GuideLog.question.icontains(filters.query, autoescape=True))
    if filters.since is not None:
        where.append(GuideLog.created_at >= filters.since)
    if filters.until is not None:
        where.append(GuideLog.created_at < filters.until)
    return where
