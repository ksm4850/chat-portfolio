import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database import Base


class GuideLog(Base):
    """안내 run 한 번(질문 하나와 답변). 관리자 확인용이며 방문자에게 돌려주지 않는다."""

    __tablename__ = "guide_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    visitor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    thread_id: Mapped[str | None] = mapped_column(String(100))
    # GA4 client_id(_ga 쿠키의 마지막 두 마디). BigQuery 내보내기의 user_pseudo_id 와 같다.
    ga_client_id: Mapped[str | None] = mapped_column(String(64), index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    scores: Mapped[list[float]] = mapped_column(JSONB, nullable=False)
    anchors: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    first_token_ms: Mapped[float | None] = mapped_column(Float)
    total_ms: Mapped[float] = mapped_column(Float, nullable=False)
    # 방문자가 답변 도중 연결을 끊으면 False. answer 는 그때까지 보낸 부분이다.
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # LLM 공급자가 알려 준 실제 사용량. 폴백이거나 사용량을 받기 전에 끊기면 NULL.
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    reasoning_tokens: Mapped[int | None] = mapped_column(Integer)
    # input_tokens 중 프롬프트 캐시에서 읽은 양.
    cached_tokens: Mapped[int | None] = mapped_column(Integer)
    # Langfuse trace id. 추적이 꺼져 있으면 NULL.
    trace_id: Mapped[str | None] = mapped_column(String(64))
