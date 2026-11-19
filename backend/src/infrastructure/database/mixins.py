from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """생성·수정 시각 컬럼.

    값은 DB의 `now()` 가 계산한다. 그래서 UPDATE 뒤에 `updated_at` 을 읽으려면
    `session.refresh()` 로 다시 읽어야 한다 (`BaseRepository.persist` 참고).
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
