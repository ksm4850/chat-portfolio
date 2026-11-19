import json
from collections.abc import AsyncIterator

import pytest
from websockets.asyncio.server import ServerConnection, serve
from websockets.datastructures import Headers
from websockets.http11 import Request, Response

from src.infrastructure.speech import (
    DeepgramSpeechToText,
    SpeechToTextError,
    SpeechToTextNotConfiguredError,
    Transcript,
)
from src.infrastructure.speech.deepgram import parse_message


def _result(text: str, *, is_final: bool) -> str:
    return json.dumps(
        {
            "type": "Results",
            "is_final": is_final,
            "channel": {"alternatives": [{"transcript": text, "confidence": 0.9}]},
        }
    )


def test_parse_message_reads_results_only() -> None:
    assert parse_message(_result("안녕", is_final=False)) == Transcript("안녕", is_final=False)
    assert parse_message(_result("안녕하세요", is_final=True)) == Transcript(
        "안녕하세요", is_final=True
    )
    assert parse_message(_result("", is_final=True)) is None
    assert parse_message(json.dumps({"type": "Metadata", "request_id": "x"})) is None


async def _chunks(*chunks: bytes) -> AsyncIterator[bytes]:
    for chunk in chunks:
        yield chunk


class FakeDeepgram:
    """오디오를 끝까지 받은 뒤 CloseStream 이 오면 결과를 보내고 닫는 서버."""

    def __init__(self) -> None:
        self.audio = b""
        self.request: Request | None = None
        self.close_code = 1000

    def check_request(self, connection: ServerConnection, request: Request) -> Response | None:
        self.request = request
        if request.headers.get("Authorization") != "Token good-key":
            return Response(401, "Unauthorized", Headers(), b"")
        return None

    async def handler(self, connection: ServerConnection) -> None:
        async for message in connection:
            if isinstance(message, bytes):
                self.audio += message
            elif json.loads(message)["type"] == "CloseStream":
                await connection.send(_result("안녕", is_final=False))
                await connection.send(_result("안녕하세요", is_final=True))
                await connection.send(json.dumps({"type": "Metadata"}))
                await connection.close(self.close_code, "DATA-0000")
                return


@pytest.fixture
async def deepgram() -> AsyncIterator[tuple[FakeDeepgram, str]]:
    fake = FakeDeepgram()
    async with serve(fake.handler, "127.0.0.1", 0, process_request=fake.check_request) as server:
        port = server.sockets[0].getsockname()[1]
        yield fake, f"ws://127.0.0.1:{port}/v1/listen"


def _client(url: str, api_key: str = "good-key") -> DeepgramSpeechToText:
    return DeepgramSpeechToText(api_key, model="nova-3", language="ko", url=url)


async def test_streams_audio_and_yields_transcripts(deepgram: tuple[FakeDeepgram, str]) -> None:
    fake, url = deepgram

    transcripts = [t async for t in _client(url).transcribe(_chunks(b"\x01\x02", b"\x03\x04"))]

    assert transcripts == [
        Transcript("안녕", is_final=False),
        Transcript("안녕하세요", is_final=True),
    ]
    assert fake.audio == b"\x01\x02\x03\x04"
    assert fake.request is not None
    query = fake.request.path.split("?", 1)[1]
    for param in ("model=nova-3", "language=ko", "encoding=linear16", "sample_rate=16000"):
        assert param in query


async def test_rejected_handshake_raises_stt_error(deepgram: tuple[FakeDeepgram, str]) -> None:
    _, url = deepgram

    with pytest.raises(SpeechToTextError, match="401"):
        [t async for t in _client(url, api_key="bad-key").transcribe(_chunks(b"\x00"))]


async def test_abnormal_close_raises_stt_error(deepgram: tuple[FakeDeepgram, str]) -> None:
    fake, url = deepgram
    fake.close_code = 1011

    with pytest.raises(SpeechToTextError, match="DATA-0000"):
        [t async for t in _client(url).transcribe(_chunks(b"\x00"))]


async def test_missing_api_key_raises_not_configured() -> None:
    with pytest.raises(SpeechToTextNotConfiguredError):
        [t async for t in _client("ws://unused", api_key="").transcribe(_chunks(b"\x00"))]
