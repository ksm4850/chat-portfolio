import uuid
from datetime import UTC, datetime

from src.modules.character.schema import CharacterRead, ExampleDialogue
from src.modules.character.service import SHORT_REPLY, build_system_prompt

NOW = datetime(2026, 11, 14, tzinfo=UTC)


def _character(**changes) -> CharacterRead:
    values = {
        "id": uuid.uuid4(),
        "slug": "me",
        "name": "상명",
        "greeting": "",
        "profile": "백엔드 개발자다.",
        "speaking_style": "",
        "example_dialogues": [],
        "is_public": True,
        "created_at": NOW,
        "updated_at": NOW,
    }
    return CharacterRead(**{**values, **changes})


def test_prompt_includes_profile_style_examples_and_memories() -> None:
    character = _character(
        speaking_style="존댓말을 쓴다.",
        example_dialogues=[ExampleDialogue(user="뭐 해요?", assistant="코딩해요.")],
    )

    prompt = build_system_prompt(character, ["고향은 부산"])

    assert prompt.startswith("# 나는 상명\n\n백엔드 개발자다.")
    assert "## 말투\n\n존댓말을 쓴다." in prompt
    assert "상대: 뭐 해요?\n나: 코딩해요." in prompt
    assert prompt.rstrip().endswith("고향은 부산")


def test_empty_sections_are_left_out() -> None:
    prompt = build_system_prompt(_character(), [])

    assert "## 말투" not in prompt
    assert "## 예시 대화" not in prompt
    assert "## 기억" not in prompt


def test_reply_rule_is_short_by_default_and_replaceable() -> None:
    assert SHORT_REPLY in build_system_prompt(_character(), [])

    prompt = build_system_prompt(_character(), [], "- 길게 답한다.")

    assert "- 길게 답한다." in prompt
    assert SHORT_REPLY not in prompt
