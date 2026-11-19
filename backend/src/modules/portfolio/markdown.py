"""포트폴리오 md 를 섹션으로 나누고 quote 를 비교하는 순수 함수.

규칙은 contracts/README.md 1장·6장.
"""

import re
from dataclasses import dataclass

_HEADING = re.compile(r"^(#{1,3}) (.+)$")
_IMAGE = re.compile(r"!\[[^\]]*]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]*)]\([^)]*\)")
_LINE_MARK = re.compile(r"^\s*(?:[-*+]|\d+\.|>)\s+", re.MULTILINE)
_STRONG_OR_CODE = re.compile(r"\*\*|__|`")
# 단어 안의 `_`(예: with_decryption)는 강조가 아니므로 남긴다.
_EMPHASIS = re.compile(r"(^|\W|_)[*_]([^*_\n]+)[*_](?![^\W_])")
_SPACES = re.compile(r"\s+")
_NOT_WORD = re.compile(r"[\W_]")
_MIN_QUOTE_LINE = 8


@dataclass(frozen=True)
class ParsedSection:
    anchor: str
    level: int
    title: str
    body: str


def split_sections(markdown: str, project_id: str, tab_id: str) -> list[ParsedSection]:
    """`##`·`###` 마다 섹션을 나눈다.

    첫 H1 은 제목으로만 쓰고, 그 아래 본문이 있을 때만 섹션이 된다.

    본문이 빈 섹션도 순서(anchor 번호)를 차지한다.
    """
    raw: list[tuple[int, str, list[str]]] = []
    current: tuple[int, str, list[str]] | None = None
    in_fence = False
    for line in markdown.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        heading = None if in_fence else _HEADING.match(line)
        if heading and len(heading[1]) == 1 and current is None and not raw:
            current = (1, heading[2].strip(), [])
            continue
        if heading and len(heading[1]) >= 2:
            if current is not None:
                raw.append(current)
            current = (len(heading[1]), heading[2].strip(), [])
            continue
        if current is not None:
            current[2].append(line)
    if current is not None:
        raw.append(current)

    sections = [
        (level, title, "\n".join(lines).strip())
        for level, title, lines in raw
        if level > 1 or "\n".join(lines).strip()
    ]
    return [
        ParsedSection(anchor=f"{project_id}-{tab_id}-{n}", level=level, title=title, body=body)
        for n, (level, title, body) in enumerate(sections, start=1)
    ]


def strip_markdown(markdown: str) -> str:
    text = _IMAGE.sub("", markdown)
    text = _LINK.sub(r"\1", text)
    text = _LINE_MARK.sub("", text)
    text = _STRONG_OR_CODE.sub("", text)
    return _EMPHASIS.sub(r"\1\2", text)


def collapse_whitespace(text: str) -> str:
    return _SPACES.sub(" ", text).strip()


def plain_text(markdown: str) -> str:
    """quote 비교용 텍스트. 화면에 렌더링된 글자와 같은 기준이다."""
    return collapse_whitespace(strip_markdown(markdown))


def contains_quote(section_plain: str, quote: str) -> bool:
    normalized = plain_text(quote)
    return bool(normalized) and normalized in section_plain


def best_quote(question: str, body: str, *, max_length: int = 80) -> str | None:
    """섹션 줄 가운데 질문과 글자 bigram 이 가장 많이 겹치는 줄. 동점이면 앞 줄."""
    grams = _bigrams(question)
    lines = [
        line
        for line in (collapse_whitespace(raw) for raw in strip_markdown(body).split("\n"))
        if len(line) >= _MIN_QUOTE_LINE
    ]
    if not lines:
        return None
    best = max(lines, key=lambda line: len(grams & _bigrams(line)))
    return best[:max_length]


def _bigrams(text: str) -> set[str]:
    letters = _NOT_WORD.sub("", text.lower())
    return {letters[i : i + 2] for i in range(len(letters) - 1)}
