from contextlib import asynccontextmanager

import pytest

from src.infrastructure.database import UniqueViolationError
from src.infrastructure.security import PasswordHasher
from src.modules.users.exceptions import EmailAlreadyExistsError
from src.modules.users.schema import UserCreate
from src.modules.users.service import UserService


class _FakeDatabase:
    @asynccontextmanager
    async def transaction(self):
        yield object()


class _RacingRepository:
    """사전 확인은 통과했지만 insert 시점에 다른 요청이 먼저 가입한 상황."""

    async def email_exists(self, session, email):
        return False

    async def add(self, session, obj):
        raise UniqueViolationError("ix_users_email")


async def test_concurrent_signup_is_reported_as_duplicate_email() -> None:
    service = UserService(_FakeDatabase(), _RacingRepository(), PasswordHasher())

    with pytest.raises(EmailAlreadyExistsError):
        await service.create_user(UserCreate(email="a@example.com", password="password-1234"))
