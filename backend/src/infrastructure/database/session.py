import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

# 제약조건 이름을 고정해야 이후 마이그레이션에서 이름으로 수정·삭제할 수 있다.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """모든 모듈 ORM 모델의 공통 베이스."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Database:
    """비동기 엔진과 세션 팩토리를 감싼 기술 어댑터.

    세션을 만들고 commit/rollback/close 하는 구현은 여기에만 둔다.
    트랜잭션 경계를 어디에 그을지는 이 클래스를 쓰는 서비스가 정한다.
    """

    def __init__(
        self,
        url: str,
        *,
        echo: bool = False,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_recycle: int = 1800,
        pool_pre_ping: bool = True,
        statement_timeout_ms: int = 30_000,
        connect_timeout: float = 5.0,
    ) -> None:
        self._engine = create_async_engine(
            url,
            echo=echo,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_recycle=pool_recycle,
            pool_pre_ping=pool_pre_ping,
            connect_args={
                "timeout": connect_timeout,
                "server_settings": {"statement_timeout": str(statement_timeout_ms)},
            },
        )
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[AsyncSession]:
        """트랜잭션 블록.

        블록을 정상적으로 벗어나면 commit, 예외가 새어 나가면 rollback 한다.
        쓰기가 있는 작업에 사용한다.
        """
        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    @asynccontextmanager
    async def read(self) -> AsyncIterator[AsyncSession]:
        """읽기 전용 블록.

        commit 을 발행하지 않는다. 조회만 하는 작업에 사용한다.
        """
        session = self._session_factory()
        try:
            yield session
        finally:
            await session.close()

    async def ping(self, timeout: float = 2.0) -> None:
        """DB 에 `SELECT 1` 을 보낸다. 응답이 없거나 실패하면 예외를 올린다."""
        async with asyncio.timeout(timeout), self._engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    async def dispose(self) -> None:
        await self._engine.dispose()
