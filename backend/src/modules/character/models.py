import uuid

from sqlalchemy import Boolean, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database import Base, TimestampMixin


class Character(Base, TimestampMixin):
    __tablename__ = "characters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # 방문자용 URL 에 쓰는 이름. 예: /characters/sangmyeong
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    greeting: Mapped[str] = mapped_column(Text, nullable=False, default="")
    profile: Mapped[str] = mapped_column(Text, nullable=False)
    speaking_style: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # [{"user": "...", "assistant": "..."}]
    example_dialogues: Mapped[list[dict[str, str]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    is_public: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
