import uuid
from datetime import datetime

from pydantic import ConfigDict, Field

from src.shared.schema import CamelModel

_SLUG = r"^[a-z0-9][a-z0-9-]{0,49}$"


class ExampleDialogue(CamelModel):
    user: str = Field(min_length=1, max_length=500)
    assistant: str = Field(min_length=1, max_length=500)


class CharacterCreate(CamelModel):
    slug: str = Field(pattern=_SLUG)
    name: str = Field(min_length=1, max_length=50)
    greeting: str = Field(default="", max_length=500)
    # 나는 누구인가. 직업·성격·관심사 같은 요약. 자세한 사실은 기억 문서로 넣는다.
    profile: str = Field(min_length=1, max_length=4000)
    speaking_style: str = Field(default="", max_length=2000)
    example_dialogues: list[ExampleDialogue] = Field(default_factory=list, max_length=20)
    is_public: bool = False


class CharacterUpdate(CamelModel):
    """보낸 필드만 바꾼다."""

    slug: str | None = Field(default=None, pattern=_SLUG)
    name: str | None = Field(default=None, min_length=1, max_length=50)
    greeting: str | None = Field(default=None, max_length=500)
    profile: str | None = Field(default=None, min_length=1, max_length=4000)
    speaking_style: str | None = Field(default=None, max_length=2000)
    example_dialogues: list[ExampleDialogue] | None = Field(default=None, max_length=20)
    is_public: bool | None = None


class CharacterRead(CamelModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    greeting: str
    profile: str
    speaking_style: str
    example_dialogues: list[ExampleDialogue]
    is_public: bool
    created_at: datetime
    updated_at: datetime


class CharacterPublic(CamelModel):
    """방문자에게 보이는 정보. 프롬프트 재료(소개·말투·예시)는 노출하지 않는다."""

    model_config = ConfigDict(from_attributes=True)

    slug: str
    name: str
    greeting: str
