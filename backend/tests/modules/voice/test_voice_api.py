from collections.abc import AsyncIterator

import pytest
from fastapi.testclient import TestClient

from src.infrastructure.speech import (
    SpeechToText,
    SpeechToTextError,
    SpeechToTextNotConfiguredError,
    Transcript,
)

URL = "/api/v1/voice/stt"


class FakeSTT(SpeechToText):
    def __init__(self, error: SpeechToTextError | None = None) -> None:
        self.error = error
        self.audio = b""

    async def transcribe(self, audio: AsyncIterator[bytes]) -> AsyncIterator[Transcript]:
        if self.error:
            raise self.error
        async for chunk in audio:
            self.audio += chunk
            yield Transcript("안녕", is_final=False)
        yield Transcript("안녕하세요", is_final=True)


@pytest.fixture
def stt(container) -> FakeSTT:
    fake = FakeSTT()
    container.infrastructure.stt.override(fake)
    return fake


def test_streams_transcripts_until_stop(client: TestClient, stt: FakeSTT) -> None:
    with client.websocket_connect(URL) as ws:
        ws.send_bytes(b"\x01\x02")
        assert ws.receive_json() == {"type": "transcript", "text": "안녕", "isFinal": False}

        ws.send_bytes(b"\x03\x04")
        ws.receive_json()
        ws.send_json({"type": "stop"})

        assert ws.receive_json() == {"type": "transcript", "text": "안녕하세요", "isFinal": True}
        assert ws.receive_json() == {"type": "done"}

    assert stt.audio == b"\x01\x02\x03\x04"


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (SpeechToTextNotConfiguredError("no key"), "speech_not_configured"),
        (SpeechToTextError("HTTP 401"), "speech_recognition_failed"),
    ],
)
def test_stt_failure_is_sent_as_error_event(
    client: TestClient, container, error: SpeechToTextError, code: str
) -> None:
    container.infrastructure.stt.override(FakeSTT(error=error))

    with client.websocket_connect(URL) as ws:
        message = ws.receive_json()

    assert message["type"] == "error"
    assert message["code"] == code
    assert "401" not in message["message"]
