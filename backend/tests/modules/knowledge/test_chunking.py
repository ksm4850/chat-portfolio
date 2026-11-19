import pytest

from src.modules.knowledge.chunking import split_text


def test_short_paragraphs_are_merged_up_to_size() -> None:
    text = "Q: 고향은?\nA: 부산\n\nQ: 직업은?\nA: 개발자\n\n\nQ: 취미는?\nA: 등산"

    chunks = split_text(text, size=30, overlap=5)

    assert chunks == ["Q: 고향은?\nA: 부산\n\nQ: 직업은?\nA: 개발자", "Q: 취미는?\nA: 등산"]


def test_long_paragraph_is_split_with_overlap() -> None:
    text = "가" * 10 + "나" * 10

    chunks = split_text(text, size=12, overlap=4)

    assert chunks == ["가" * 10 + "나" * 2, "가" * 2 + "나" * 10]
    assert all(len(chunk) <= 12 for chunk in chunks)


def test_long_paragraph_flushes_pending_chunk_first() -> None:
    chunks = split_text("짧은 문단\n\n" + "가" * 20, size=10, overlap=2)

    assert chunks[0] == "짧은 문단"
    assert "".join(chunks[1:]).startswith("가" * 10)


def test_blank_text_has_no_chunks() -> None:
    assert split_text(" \n\n \n", size=10, overlap=2) == []


def test_overlap_must_be_smaller_than_size() -> None:
    with pytest.raises(ValueError):
        split_text("내용", size=10, overlap=10)
