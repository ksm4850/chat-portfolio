"""Deepgram 실시간 STT 어댑터.

오디오를 WebSocket 으로 흘려보내는 쪽과 결과를 받는 쪽을 동시에 돌린다.
오디오가 끝나면 CloseStream 을 보내고, Deepgram 이 남은 결과를 보낸 뒤 연결을 닫으면 종료한다.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from urllib.parse import urlencode

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, ConnectionClosedError, InvalidStatus

from src.infrastructure.speech.base import (
    SAMPLE_RATE,
    SpeechToText,
    SpeechToTextError,
    SpeechToTextNotConfiguredError,
    Transcript,
)

DEEPGRAM_LISTEN_URL = "wss://api.deepgram.com/v1/listen"
_CLOSE_STREAM = json.dumps({"type": "CloseStream"})


class DeepgramSpeechToText(SpeechToText):
    def __init__(
        self, api_key: str, model: str, language: str, url: str = DEEPGRAM_LISTEN_URL
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._language = language
        self._url = url

    async def transcribe(self, audio: AsyncIterator[bytes]) -> AsyncIterator[Transcript]:
        if not self._api_key:
            raise SpeechToTextNotConfiguredError("DEEPGRAM_API_KEY 가 비어 있다")

        try:
            connection = await connect(
                self._listen_url(),
                additional_headers={"Authorization": f"Token {self._api_key}"},
            )
        except InvalidStatus as exc:
            raise SpeechToTextError(
                f"Deepgram 이 연결을 거부했다: HTTP {exc.response.status_code}"
            ) from exc
        except (OSError, TimeoutError) as exc:
            raise SpeechToTextError(f"Deepgram 에 연결하지 못했다: {exc}") from exc

        async with connection:
            sender = asyncio.create_task(_send_audio(connection, audio))
            try:
                async for message in connection:
                    transcript = parse_message(message)
                    if transcript is not None:
                        yield transcript
            except ConnectionClosedError as exc:
                raise SpeechToTextError(f"Deepgram 연결이 비정상 종료됐다: {exc.rcvd}") from exc
            finally:
                sender.cancel()
                await asyncio.wait([sender])

    def _listen_url(self) -> str:
        query = urlencode(
            {
                "model": self._model,
                "language": self._language,
                "encoding": "linear16",
                "sample_rate": SAMPLE_RATE,
                "channels": 1,
                "interim_results": "true",
                "punctuate": "true",
            }
        )
        return f"{self._url}?{query}"


async def _send_audio(connection: ClientConnection, audio: AsyncIterator[bytes]) -> None:
    try:
        async for chunk in audio:
            await connection.send(chunk)
        await connection.send(_CLOSE_STREAM)
    except ConnectionClosed:
        # 종료 사유는 수신 쪽이 close frame 으로 판단한다.
        return


def parse_message(raw: str | bytes) -> Transcript | None:
    message = json.loads(raw)
    if message.get("type") != "Results":
        return None
    alternatives = message.get("channel", {}).get("alternatives") or [{}]
    text = alternatives[0].get("transcript", "")
    if not text:
        return None
    return Transcript(text=text, is_final=bool(message.get("is_final")))
