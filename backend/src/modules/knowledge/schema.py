import uuid
from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field

from src.shared.schema import CamelModel


class DocumentCreate(CamelModel):
    title: str = Field(min_length=1, max_length=200)
    # 출처 구분용. 예: profile(자기소개 Q&A), kakao, note
    source: str = Field(min_length=1, max_length=50)
    content: str = Field(min_length=1)


class DocumentUpdate(CamelModel):
    """보낸 필드만 바꾼다. 본문을 바꾸면 청크를 다시 만든다."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    source: str | None = Field(default=None, min_length=1, max_length=50)
    content: str | None = Field(default=None, min_length=1)


class DocumentRead(CamelModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    source: str
    chunk_count: int
    created_at: datetime
    updated_at: datetime


class ChunkRead(CamelModel):
    model_config = ConfigDict(from_attributes=True)

    position: int
    content: str
    meta: dict[str, Any] | None = None


class DocumentDetail(DocumentRead):
    content: str
    chunks: list[ChunkRead]


class SearchRequest(CamelModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=4, ge=1, le=20)


class SearchHit(CamelModel):
    document_id: uuid.UUID
    title: str
    content: str
    # 코사인 유사도. 1 에 가까울수록 질의와 비슷하다.
    score: float
    meta: dict[str, Any] | None = None


class ChunkDraft(CamelModel):
    """다른 모듈이 미리 나눈 청크. `meta.path` 가 있으면 임베딩할 때 앞에 문맥으로 붙인다."""

    content: str
    meta: dict[str, Any] | None = None


class DocumentDraft(CamelModel):
    title: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=50)
    content: str
    chunks: list[ChunkDraft]
