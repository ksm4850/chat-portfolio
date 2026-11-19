import json
import uuid

from src.modules.guide.history import GuideTurn, RedisGuideHistory


class FakeRedis:
    def __init__(self, raw: list[str]) -> None:
        self.raw = raw

    async def lrange(self, key, start, end):
        return self.raw


async def test_recent_skips_broken_items_and_ignores_unknown_keys() -> None:
    raw = [
        "{not json",
        json.dumps(["list"]),
        json.dumps({"answer": "질문이 없다"}),
        json.dumps({"question": "q", "answer": "a", "anchors": ["x", 1], "mode": "new"}),
        json.dumps({"question": "q2", "answer": "a2"}),
    ]

    turns = await RedisGuideHistory(FakeRedis(raw), 60, 8).recent(uuid.uuid4(), "t")

    assert turns == [GuideTurn("q", "a", ["x"]), GuideTurn("q2", "a2", [])]
