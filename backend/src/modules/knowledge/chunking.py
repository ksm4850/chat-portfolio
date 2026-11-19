import re

_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")


def split_text(text: str, *, size: int, overlap: int) -> list[str]:
    """빈 줄로 나눈 문단을 `size` 글자 이내로 묶는다.

    Q&A 한 쌍처럼 의미 단위가 문단으로 끊어진 문서를 전제로 한다.
    `size` 보다 긴 문단만 `overlap` 만큼 겹치게 잘라 문맥이 끊기지 않게 한다.
    """
    if overlap >= size:
        raise ValueError("overlap 은 size 보다 작아야 한다")

    chunks: list[str] = []
    current = ""
    for paragraph in _paragraphs(text):
        if len(paragraph) > size:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_window(paragraph, size=size, overlap=overlap))
        elif not current:
            current = paragraph
        elif len(current) + 2 + len(paragraph) <= size:
            current = f"{current}\n\n{paragraph}"
        else:
            chunks.append(current)
            current = paragraph
    if current:
        chunks.append(current)
    return chunks


def _paragraphs(text: str) -> list[str]:
    return [part.strip() for part in _PARAGRAPH_BREAK.split(text) if part.strip()]


def _window(text: str, *, size: int, overlap: int) -> list[str]:
    step = size - overlap
    return [text[start : start + size] for start in range(0, len(text) - overlap, step)]
