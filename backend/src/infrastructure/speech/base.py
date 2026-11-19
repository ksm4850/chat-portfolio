from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass

# STT 입력 오디오 형식. 브라우저 테스트 화면도 이 형식으로 보낸다.
SAMPLE_RATE = 16_000
BYTES_PER_SECOND = SAMPLE_RATE * 2


@dataclass(frozen=True)
class Transcript:
    text: str
    # False 면 인식 도중의 중간 결과라 이후 결과로 바뀔 수 있다.
    is_final: bool


class SpeechToTextError(Exception):
    """STT 호출 실패. 서비스는 이를 자기 도메인 예외로 번역한다."""


class SpeechToTextNotConfiguredError(SpeechToTextError):
    """API 키 같은 필수 설정이 비어 있다."""


class SpeechToText(ABC):
    @abstractmethod
    def transcribe(self, audio: AsyncIterator[bytes]) -> AsyncIterator[Transcript]:
        """16kHz mono 16-bit PCM 스트림을 받아 인식 결과를 순서대로 돌려준다.

        오디오 스트림이 끝나면 남은 결과를 마저 돌려준 뒤 종료한다.
        """


class TextToSpeech(ABC):
    @abstractmethod
    def synthesize(self, text: AsyncIterator[str]) -> AsyncIterator[bytes]:
        """LLM 응답 조각을 받아 합성한 오디오 조각을 돌려준다."""
