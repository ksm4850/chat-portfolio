import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database import BaseRepository
from src.modules.users.models import User


class UserRepository(BaseRepository[User]):
    """`users` 테이블 접근. 공통 CRUD 는 `BaseRepository` 가 제공한다."""

    model = User

    async def get_by_email(self, session: AsyncSession, email: str) -> User | None:
        return await self.find_one(session, User.email == email)

    async def get_by_id(self, session: AsyncSession, user_id: uuid.UUID) -> User | None:
        return await self.get(session, user_id)

    async def email_exists(self, session: AsyncSession, email: str) -> bool:
        return await self.exists(session, User.email == email)
