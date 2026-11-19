import uuid
from typing import Literal

from pydantic import Field

from src.modules.character.schema import CharacterPublic
from src.modules.knowledge.schema import SearchHit
from src.shared.schema import CamelModel


class SessionCreate(CamelModel):
    character_slug: str = Field(min_length=1, max_length=50)


class AdminSessionCreate(CamelModel):
    character_id: uuid.UUID


class SessionCreated(CamelModel):
    session_id: uuid.UUID
    character: CharacterPublic


class MessageCreate(CamelModel):
    # 실제 한도는 설정(CHAT_MESSAGE_MAX_LENGTH)이 정한다. 여기는 요청 크기 상한이다.
    text: str = Field(min_length=1, max_length=2000)


class HistoryMessage(CamelModel):
    role: Literal["user", "assistant"]
    content: str


class UsageRead(CamelModel):
    llm_calls_today: int
    llm_calls_per_day: int


class ReplyContext(CamelModel):
    """관리자 채팅 테스트에서 응답 전에 보여 주는 재료."""

    memories: list[SearchHit]
    system_prompt: str
