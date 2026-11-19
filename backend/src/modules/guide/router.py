import json
import uuid
from collections.abc import AsyncIterator
from datetime import datetime

from ag_ui.core import BaseEvent as AgUiEvent
from ag_ui.core import (
    CustomEvent,
    RunAgentInput,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
)
from ag_ui.encoder import EventEncoder
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from src.core.container import AppContainer
from src.core.exceptions import AppError
from src.interfaces.dependencies import ClientIP, CurrentVisitor
from src.modules.guide.exceptions import NoUserMessageError
from src.modules.guide.schema import (
    GuideEvent,
    GuideLogFilter,
    GuideLogPage,
    GuideStats,
    ModeChanged,
    SourcesFound,
    TextDelta,
    TextEnded,
    ToolCalled,
)
from src.modules.guide.service import GuideLogService, GuideService

router = APIRouter(tags=["guide"])

# 인증은 조립 지점(api/v1)의 admin 라우터가 건다.
admin_router = APIRouter(tags=["admin: guide"])


@router.post("/run")
@inject
async def run_agent(
    payload: RunAgentInput,
    visitor_id: CurrentVisitor,
    client_ip: ClientIP,
    service: GuideService = Depends(Provide[AppContainer.guide.service]),
) -> StreamingResponse:
    """AG-UI run. 마지막 user 메시지에 답하면서 화면 제어(navigate·highlight) 툴 호출을 섞어 보낸다.

    이벤트 순서와 폴백 규칙은 contracts/README.md 3·5장.
    사용량 제한에 걸리면 스트림을 열기 전에 429.
    """
    question = _last_user_text(payload)
    props = payload.forwarded_props if isinstance(payload.forwarded_props, dict) else {}
    capabilities = props.get("capabilities")
    ga_client_id = props.get("gaClientId")
    events = await service.start(
        visitor_id,
        client_ip,
        question,
        capabilities if isinstance(capabilities, list) else None,
        thread_id=payload.thread_id[:100] or None,
        ga_client_id=ga_client_id if isinstance(ga_client_id, str) else None,
    )
    encoder = EventEncoder()
    return StreamingResponse(
        (encoder.encode(event) async for event in _agui(payload, events)),
        media_type=encoder.get_content_type(),
    )


@admin_router.get("/logs")
@inject
async def list_logs(
    visitor_id: uuid.UUID | None = Query(default=None, alias="visitorId"),
    thread_id: str | None = Query(default=None, alias="threadId", max_length=100),
    ga_client_id: str | None = Query(default=None, alias="gaClientId", max_length=64),
    query: str | None = Query(default=None, alias="q", max_length=200),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    service: GuideLogService = Depends(Provide[AppContainer.guide.log_service]),
) -> GuideLogPage:
    """안내 대화 기록. 최신순. `q` 는 질문 본문 부분 일치."""
    filters = GuideLogFilter(
        visitor_id=visitor_id,
        thread_id=thread_id,
        ga_client_id=ga_client_id,
        query=query,
        since=since,
        until=until,
    )
    return await service.list(filters, offset=offset, limit=limit)


@admin_router.get("/stats")
@inject
async def read_stats(
    days: int = Query(default=7, ge=1, le=90),
    tz: str = Query(default="Asia/Seoul", max_length=64),
    service: GuideLogService = Depends(Provide[AppContainer.guide.log_service]),
) -> GuideStats:
    """대시보드 집계. `tz` 기준 오늘을 포함한 최근 `days` 일."""
    return await service.stats(days, tz)


async def _agui(
    payload: RunAgentInput, events: AsyncIterator[GuideEvent]
) -> AsyncIterator[AgUiEvent]:
    yield RunStartedEvent(thread_id=payload.thread_id, run_id=payload.run_id)
    message_id = f"msg_{uuid.uuid4().hex}"
    opened = closed = False
    # 스트림이 시작된 뒤에는 상태 코드를 바꿀 수 없어 오류도 이벤트로 알린다.
    try:
        async for event in events:
            if isinstance(event, ModeChanged):
                yield CustomEvent(name="mode", value=event.mode)
            elif isinstance(event, SourcesFound):
                yield CustomEvent(
                    name="sources",
                    value=[
                        source.model_dump(by_alias=True, mode="json") for source in event.sources
                    ],
                )
            elif isinstance(event, TextEnded):
                if opened and not closed:
                    closed = True
                    yield TextMessageEndEvent(message_id=message_id)
            else:
                # 툴 호출의 parentMessageId 가 가리킬 메시지를 먼저 연다.
                if not opened:
                    opened = True
                    yield TextMessageStartEvent(message_id=message_id, role="assistant")
                if isinstance(event, TextDelta):
                    yield TextMessageContentEvent(message_id=message_id, delta=event.text)
                else:
                    for tool_event in _tool_call(event, message_id):
                        yield tool_event
    except AppError as exc:
        yield RunErrorEvent(message=exc.message, code=exc.code)
        return
    if opened and not closed:
        yield TextMessageEndEvent(message_id=message_id)
    yield RunFinishedEvent(thread_id=payload.thread_id, run_id=payload.run_id)


def _tool_call(event: ToolCalled, message_id: str) -> list[AgUiEvent]:
    call_id = f"call_{uuid.uuid4().hex}"
    return [
        ToolCallStartEvent(
            tool_call_id=call_id, tool_call_name=event.name, parent_message_id=message_id
        ),
        ToolCallArgsEvent(tool_call_id=call_id, delta=json.dumps(event.args, ensure_ascii=False)),
        ToolCallEndEvent(tool_call_id=call_id),
    ]


def _last_user_text(payload: RunAgentInput) -> str:
    for message in reversed(payload.messages):
        if message.role != "user":
            continue
        content = message.content
        if isinstance(content, str):
            text = content
        else:
            text = " ".join(getattr(part, "text", "") or "" for part in content)
        if text.strip():
            return text
    raise NoUserMessageError()
