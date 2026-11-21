import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

from pydantic import ConfigDict

from src.shared.schema import CamelModel


class SourceLocation(CamelModel):
    project_id: str
    tab: str
    anchor: str


class Source(CamelModel):
    title: str
    snippet: str
    score: float
    location: SourceLocation | None


@dataclass(frozen=True)
class GuideOptions:
    character_slug: str
    llm_enabled: bool
    search_limit: int
    source_min_score: float
    source_max_gap: float
    action_min_score: float
    history_turns: int
    history_max_turns: int
    history_answer_max_chars: int


# 서비스가 내보내는 결과. 라우터가 AG-UI 이벤트로 바꾼다.
@dataclass(frozen=True)
class ModeChanged:
    mode: Literal["llm", "fallback"]


@dataclass(frozen=True)
class SourcesFound:
    sources: list[Source]


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class TextEnded:
    pass


@dataclass(frozen=True)
class ToolCalled:
    name: str
    args: dict[str, Any]


type GuideEvent = ModeChanged | SourcesFound | TextDelta | TextEnded | ToolCalled


@dataclass(frozen=True)
class GuideLogCreate:
    visitor_id: uuid.UUID
    thread_id: str | None
    ga_client_id: str | None
    question: str
    answer: str
    mode: str
    scores: list[float]
    anchors: list[str]
    first_token_ms: float | None
    total_ms: float
    completed: bool
    input_tokens: int | None
    output_tokens: int | None
    reasoning_tokens: int | None
    cached_tokens: int | None
    trace_id: str | None


@dataclass(frozen=True)
class GuideLogFilter:
    visitor_id: uuid.UUID | None = None
    thread_id: str | None = None
    ga_client_id: str | None = None
    query: str | None = None
    since: datetime | None = None
    until: datetime | None = None


class GuideLogRead(CamelModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    visitor_id: uuid.UUID
    thread_id: str | None
    ga_client_id: str | None
    question: str
    answer: str
    mode: str
    scores: list[float]
    anchors: list[str]
    first_token_ms: float | None
    total_ms: float
    completed: bool
    input_tokens: int | None
    output_tokens: int | None
    reasoning_tokens: int | None
    cached_tokens: int | None
    trace_id: str | None


class GuideLogPage(CamelModel):
    items: list[GuideLogRead]
    total_count: int
    offset: int
    limit: int


class GuideDailyCount(CamelModel):
    date: date
    questions: int
    visitors: int


class GuideModeCount(CamelModel):
    mode: str
    count: int


class GuideQuestionCount(CamelModel):
    question: str
    count: int


class GuideLatency(CamelModel):
    first_token_avg_ms: float | None
    first_token_p95_ms: float | None
    total_avg_ms: float | None
    total_p95_ms: float | None


class GuideSummary(CamelModel):
    questions: int
    visitors: int
    threads: int
    incomplete: int
    latency: GuideLatency


class GuideStats(CamelModel):
    """`since`~`until` 안내 기록 집계. 일별 값은 `tz` 기준 날짜이고 기록이 없는 날은 0."""

    since: datetime
    until: datetime
    tz: str
    summary: GuideSummary
    daily: list[GuideDailyCount]
    modes: list[GuideModeCount]
    top_questions: list[GuideQuestionCount]
