import uuid
from typing import Any

from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database import Base, TimestampMixin


class PortfolioCatalog(Base, TimestampMixin):
    """projects.json 원본(프로필·경력·프로젝트·기술). 수집할 때마다 한 행을 통째로 바꾼다."""

    __tablename__ = "portfolio_catalogs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class PortfolioSection(Base):
    __tablename__ = "portfolio_sections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    tab: Mapped[str] = mapped_column(String(100), nullable=False)
    # 화면 DOM(data-anchor)·청크 meta·LLM 위치 표시가 같은 값을 쓴다. 예: cq-decisions-2
    anchor: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
