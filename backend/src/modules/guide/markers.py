"""LLM 답변 안의 표시를 텍스트와 분리한다.

위치 표시 `[[show:{anchor}|{quote}]]`, 화면 전환 `[[view:{view}]]`.

규칙은 contracts/README.md 5장.
"""

import re
from dataclasses import dataclass

MAX_MARKER_LENGTH = 200
_MARKER = re.compile(r"^show:([\w-]+)(?:\|([\s\S]+))?$")
_VIEW = re.compile(r"^view:(\w+)$")


@dataclass(frozen=True)
class TextPiece:
    text: str


@dataclass(frozen=True)
class ShowPiece:
    anchor: str
    quote: str | None


@dataclass(frozen=True)
class ViewPiece:
    view: str


type Piece = TextPiece | ShowPiece | ViewPiece


class MarkerParser:
    """스트림 조각을 받아 표시가 끝난 부분까지만 내보낸다.

    조각 경계에서 잘린 `[[` 는 다음 조각을 기다린다.

    `[[` 뒤 200자 안에 `]]` 가 없으면 표시가 아닌 일반 텍스트로 본다. 형식이 틀린 표시는 버린다.
    """

    def __init__(self) -> None:
        self._buffer = ""
        self.dropped = 0

    def feed(self, delta: str) -> list[Piece]:
        self._buffer += delta
        out: list[Piece] = []
        while self._buffer:
            buffer = self._buffer
            start = buffer.find("[[")
            if start == -1:
                keep = 1 if buffer.endswith("[") else 0
                if len(buffer) > keep:
                    out.append(TextPiece(buffer[: len(buffer) - keep]))
                self._buffer = buffer[len(buffer) - keep :]
                break
            if start > 0:
                out.append(TextPiece(buffer[:start]))
                self._buffer = buffer[start:]
                continue
            end = buffer.find("]]")
            if end == -1:
                if len(buffer) <= MAX_MARKER_LENGTH:
                    break
                out.append(TextPiece("[["))
                self._buffer = buffer[2:]
                continue
            body = buffer[2:end].strip()
            self._buffer = buffer[end + 2 :]
            if match := _MARKER.match(body):
                quote = (match[2] or "").strip() or None
                out.append(ShowPiece(anchor=match[1], quote=quote))
            elif match := _VIEW.match(body):
                out.append(ViewPiece(view=match[1]))
            else:
                self.dropped += 1
        return out

    def flush(self) -> list[Piece]:
        text, self._buffer = self._buffer, ""
        return [TextPiece(text)] if text else []
