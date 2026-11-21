import uuid

from src.modules.guide.service import relevant_hits
from src.modules.knowledge.schema import SearchHit


def _hits(*scores: float) -> list[SearchHit]:
    return [
        SearchHit(document_id=uuid.uuid4(), title="문서", content=str(score), score=score)
        for score in scores
    ]


def test_keeps_hits_close_to_top_and_above_floor() -> None:
    kept = relevant_hits(_hits(0.56, 0.52, 0.47, 0.40), min_score=0.35, max_gap=0.08)

    assert [hit.score for hit in kept] == [0.56, 0.52]


def test_drops_everything_below_floor() -> None:
    assert relevant_hits(_hits(0.34, 0.33), min_score=0.35, max_gap=0.08) == []


def test_floor_applies_even_within_gap() -> None:
    kept = relevant_hits(_hits(0.38, 0.34), min_score=0.35, max_gap=0.08)

    assert [hit.score for hit in kept] == [0.38]
