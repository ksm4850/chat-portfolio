import json
import uuid
from collections.abc import AsyncIterator

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse

from src.core.container import AppContainer
from src.core.exceptions import AppError
from src.interfaces.dependencies import ClientIP, CurrentSuperUser, CurrentVisitor
from src.modules.chat.schema import (
    AdminSessionCreate,
    HistoryMessage,
    MessageCreate,
    SessionCreate,
    SessionCreated,
    UsageRead,
)
from src.modules.chat.service import ChatService

router = APIRouter(tags=["chat"])

# 인증은 조립 지점(api/v1)의 admin 라우터가 건다.
admin_router = APIRouter(tags=["admin: chat"])


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
@inject
async def create_session(
    payload: SessionCreate,
    visitor_id: CurrentVisitor,
    service: ChatService = Depends(Provide[AppContainer.chat.service]),
) -> SessionCreated:
    """공개된 캐릭터와 대화방을 연다. 응답의 인사말을 첫 메시지로 보여 주면 된다."""
    return await service.create_session(payload.character_slug, visitor_id)


@router.get("/sessions/{session_id}/messages")
@inject
async def read_history(
    session_id: uuid.UUID,
    visitor_id: CurrentVisitor,
    service: ChatService = Depends(Provide[AppContainer.chat.service]),
) -> list[HistoryMessage]:
    """새로고침 뒤 대화를 복원할 때 쓴다."""
    return await service.get_history(session_id, visitor_id)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_session(
    session_id: uuid.UUID,
    visitor_id: CurrentVisitor,
    service: ChatService = Depends(Provide[AppContainer.chat.service]),
) -> None:
    await service.delete_session(session_id, visitor_id)


@router.post("/sessions/{session_id}/messages")
@inject
async def send_message(
    session_id: uuid.UUID,
    payload: MessageCreate,
    visitor_id: CurrentVisitor,
    client_ip: ClientIP,
    service: ChatService = Depends(Provide[AppContainer.chat.service]),
) -> StreamingResponse:
    """응답을 SSE 로 흘려보낸다. `delta` 이벤트가 이어지고 `done` 또는 `error` 로 끝난다.

    사용량 제한에 걸리면 스트림을 열기 전에 429 로 응답한다.
    """
    stream = await service.reply(session_id, visitor_id, client_ip, payload.text)
    return StreamingResponse(_sse(stream), media_type="text/event-stream")


@admin_router.post("/chat/sessions", status_code=status.HTTP_201_CREATED)
@inject
async def create_test_session(
    payload: AdminSessionCreate,
    admin: CurrentSuperUser,
    service: ChatService = Depends(Provide[AppContainer.chat.service]),
) -> SessionCreated:
    """관리자 채팅 테스트. 비공개 캐릭터도 되고 사용량 제한에 잡히지 않는다."""
    return await service.create_test_session(payload.character_id, admin.id)


@admin_router.post("/chat/sessions/{session_id}/messages")
@inject
async def send_test_message(
    session_id: uuid.UUID,
    payload: MessageCreate,
    admin: CurrentSuperUser,
    service: ChatService = Depends(Provide[AppContainer.chat.service]),
) -> StreamingResponse:
    """SSE. 먼저 `context`(검색된 기억·시스템 프롬프트)를 보내고 `delta` → `done` | `error`."""
    context, stream = await service.test_reply(session_id, admin.id, payload.text)
    return StreamingResponse(
        _sse(stream, first=_event("context", context.model_dump(by_alias=True, mode="json"))),
        media_type="text/event-stream",
    )


@admin_router.get("/usage")
@inject
async def read_usage(
    service: ChatService = Depends(Provide[AppContainer.chat.service]),
) -> UsageRead:
    """오늘(최근 24시간 window) 전체 LLM 호출 수와 한도."""
    return await service.usage()


async def _sse(stream: AsyncIterator[str], first: str | None = None) -> AsyncIterator[str]:
    if first is not None:
        yield first
    # 스트림이 시작된 뒤에는 상태 코드를 바꿀 수 없어 오류도 이벤트로 알린다.
    try:
        async for delta in stream:
            yield _event("delta", {"text": delta})
    except AppError as exc:
        yield _event("error", {"code": exc.code, "message": exc.message})
        return
    yield _event("done", {})


def _event(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
