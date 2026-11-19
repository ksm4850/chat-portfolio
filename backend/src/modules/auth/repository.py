import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database import BaseRepository
from src.modules.auth.models import RefreshToken


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    model = RefreshToken

    async def get_for_update(self, session: AsyncSession, jti: uuid.UUID) -> RefreshToken | None:
        """동시에 같은 토큰으로 재발급을 시도해도 한 요청만 통과하도록 행을 잠근다."""
        statement = select(RefreshToken).where(RefreshToken.jti == jti).with_for_update()
        return (await session.execute(statement)).scalars().first()

    async def revoke_family(
        self, session: AsyncSession, family_id: uuid.UUID, revoked_at: datetime
    ) -> int:
        statement = (
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=revoked_at)
        )
        result = await session.execute(statement)
        return result.rowcount or 0
