import time
from collections.abc import AsyncIterator
from contextlib import aclosing

from src.infrastructure.logging import get_logger
from src.infrastructure.speech import (
    BYTES_PER_SECOND,
    SpeechToText,
    SpeechToTextError,
    SpeechToTextNotConfiguredError,
)
from src.modules.voice.exceptions import SpeechNotConfiguredError, SpeechRecognitionFailedError
from src.modules.voice.schema import TranscriptSegment

logger = get_logger(__name__)


class VoiceService:
    """음성 입출력. 지금은 STT 확인용 전사만 있고, 이후 음성 대화를 여기에 붙인다."""

    def __init__(self, stt: SpeechToText) -> None:
        self._stt = stt

    async def transcribe(self, audio: AsyncIterator[bytes]) -> AsyncIterator[TranscriptSegment]:
        started = time.perf_counter()
        received_bytes = 0
        final_count = 0

        async def counted() -> AsyncIterator[bytes]:
            nonlocal received_bytes
            async for chunk in audio:
                received_bytes += len(chunk)
                yield chunk

        try:
            async with aclosing(self._stt.transcribe(counted())) as transcripts:
                async for transcript in transcripts:
                    final_count += transcript.is_final
                    yield TranscriptSegment(text=transcript.text, is_final=transcript.is_final)
        except SpeechToTextNotConfiguredError as exc:
            raise SpeechNotConfiguredError() from exc
        except SpeechToTextError as exc:
            logger.warning("음성 인식 실패", extra={"error": str(exc)})
            raise SpeechRecognitionFailedError() from exc
        finally:
            # 클라이언트가 중간에 끊어도 과금 기준인 오디오 길이를 남긴다.
            logger.info(
                "음성 인식 종료",
                extra={
                    "audio_seconds": round(received_bytes / BYTES_PER_SECOND, 1),
                    "final_count": final_count,
                    "total_ms": round((time.perf_counter() - started) * 1000, 1),
                },
            )
