from src.modules.guide.markers import (
    MAX_MARKER_LENGTH,
    MarkerParser,
    ShowPiece,
    TextPiece,
    ViewPiece,
)


def _run(deltas: list[str]) -> tuple[list, MarkerParser]:
    parser = MarkerParser()
    pieces = [piece for delta in deltas for piece in parser.feed(delta)]
    return pieces + parser.flush(), parser


def _merge(pieces: list) -> list:
    """연속한 텍스트 조각을 합쳐 비교하기 쉽게 만든다."""
    merged: list = []
    for piece in pieces:
        if isinstance(piece, TextPiece) and merged and isinstance(merged[-1], TextPiece):
            merged[-1] = TextPiece(merged[-1].text + piece.text)
        else:
            merged.append(piece)
    return merged


def test_marker_between_text_becomes_show_piece() -> None:
    pieces, _ = _run(["앞 문장입니다.[[show:cq-decisions-2|방향을 뒤집어]] 뒤 문장입니다."])

    assert _merge(pieces) == [
        TextPiece("앞 문장입니다."),
        ShowPiece("cq-decisions-2", "방향을 뒤집어"),
        TextPiece(" 뒤 문장입니다."),
    ]


def test_marker_split_across_every_delta_boundary() -> None:
    answer = "가[[show:ecs-overview-2|서버마다 각자]]나[[show:cq-overview-1]]다"
    expected = [
        TextPiece("가"),
        ShowPiece("ecs-overview-2", "서버마다 각자"),
        TextPiece("나"),
        ShowPiece("cq-overview-1", None),
        TextPiece("다"),
    ]

    for size in range(1, 6):
        deltas = [answer[i : i + size] for i in range(0, len(answer), size)]
        pieces, _ = _run(deltas)
        assert _merge(pieces) == expected, size


def test_text_before_marker_is_released_immediately() -> None:
    parser = MarkerParser()

    assert parser.feed("설명입니다.[[sh") == [TextPiece("설명입니다.")]
    assert parser.feed("ow:a-b-1]]") == [ShowPiece("a-b-1", None)]


def test_single_trailing_bracket_waits_for_next_delta() -> None:
    parser = MarkerParser()

    assert parser.feed("배열 a[") == [TextPiece("배열 a")]
    assert parser.feed("0] 입니다") == [TextPiece("[0] 입니다")]


def test_invalid_marker_is_dropped_from_text() -> None:
    pieces, parser = _run(["앞[[open:cq]]뒤"])

    assert _merge(pieces) == [TextPiece("앞뒤")]
    assert parser.dropped == 1


def test_unclosed_marker_longer_than_limit_is_plain_text() -> None:
    long = "[[" + "가" * MAX_MARKER_LENGTH + " 끝"

    pieces, _ = _run([long])

    assert "".join(p.text for p in pieces if isinstance(p, TextPiece)) == long


def test_unclosed_marker_at_end_is_flushed_as_text() -> None:
    pieces, _ = _run(["끝[[show:a-b"])

    assert _merge(pieces) == [TextPiece("끝[[show:a-b")]


def test_view_marker_becomes_view_piece() -> None:
    pieces, parser = _run(["경력입니다.[[vi", "ew:career]] 끝[[view:]]"])

    assert _merge(pieces) == [TextPiece("경력입니다."), ViewPiece("career"), TextPiece(" 끝")]
    assert parser.dropped == 1
