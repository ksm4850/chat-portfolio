"""안내 기록 캐시 토큰

Revision ID: b7c41e9d2a50
Revises: 078d61499a2f
Create Date: 2026-11-18 18:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7c41e9d2a50"
down_revision: str | None = "078d61499a2f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("guide_logs", sa.Column("cached_tokens", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("guide_logs", "cached_tokens")
