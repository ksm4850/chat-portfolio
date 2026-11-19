from collections.abc import AsyncIterator
from contextlib import aclosing

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status

from src.core.container import AppContainer
from src.core.exceptions import AppError
from src.modules.voice.service import VoiceService

router = APIRouter(tags=["voice"])


@router.websocket("/stt")
@inject
async def transcribe(
    websocket: WebSocket,
    service: VoiceService = Depends(Provide[AppContainer.voice.service]),
) -> None:
    """16kHz mono 16-bit PCM 을 바이너리 프레임으로 받아 인식 결과를 JSON 으로 보낸다.

    서버 → 클라이언트: `transcript`(text, isFinal) 가 이어지고 `done` 또는 `error` 로 끝난다.
    클라이언트가 텍스트 프레임(예: `{"type": "stop"}`)을 보내면 남은 결과를 보낸 뒤 닫는다.
    """
    await websocket.accept()
    try:
        async with aclosing(service.transcribe(_audio(websocket))) as segments:
            async for segment in segments:
                await websocket.send_json(
                    {"type": "transcript", **segment.model_dump(by_alias=True)}
                )
        await websocket.send_json({"type": "done"})
        await websocket.close()
    except WebSocketDisconnect:
        return
    except AppError as exc:
        await websocket.send_json({"type": "error", "code": exc.code, "message": exc.message})
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)


async def _audio(websocket: WebSocket) -> AsyncIterator[bytes]:
    while True:
        message = await websocket.receive()
        if message["type"] == "websocket.disconnect":
            return
        if message.get("bytes"):
            yield message["bytes"]
        elif message.get("text") is not None:
            return
