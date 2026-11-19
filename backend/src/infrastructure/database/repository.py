from collections.abc import Sequence
from typing import Any, ClassVar

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnExpressionArgument
from sqlalchemy.sql.base import ExecutableOption

from src.infrastructure.database.exceptions import UniqueViolationError
from src.infrastructure.database.session import Base

_UNIQUE_VIOLATION = "23505"


class BaseRepository[ModelT: Base]:
    """도메인 repository 의 공통 조회·저장 동작.

    상태가 없으므로 컨테이너에서 `Singleton` 으로 조립하고, 세션은 메서드 인자로 받는다.
    `commit()` 과 `rollback()` 은 호출하지 않는다. 트랜잭션 경계는 서비스가 갖는다.

    필터는 문자열 규약을 만들지 않고 SQLAlchemy 표현식을 그대로 받는다.
    예: `await repo.find(session, User.is_active.is_(True), limit=20)`
    """

    model: ClassVar[type[Base]]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, "model"):
            raise TypeError(f"{cls.__name__} 은 model 클래스 변수를 지정해야 한다.")

    async def get(
        self,
        session: AsyncSession,
        *primary_key: Any,
        options: Sequence[ExecutableOption] = (),
    ) -> ModelT | None:
        """기본키로 한 건 조회한다."""
        return await session.get(self.model, primary_key, options=list(options) or None)

    async def find_one(
        self,
        session: AsyncSession,
        *where: ColumnExpressionArgument[bool],
        options: Sequence[ExecutableOption] = (),
    ) -> ModelT | None:
        statement = select(self.model).where(*where).limit(1)
        if options:
            statement = statement.options(*options)
        return (await session.execute(statement)).scalars().first()

    async def find(
        self,
        session: AsyncSession,
        *where: ColumnExpressionArgument[bool],
        order_by: Sequence[Any] = (),
        offset: int = 0,
        limit: int = 100,
        options: Sequence[ExecutableOption] = (),
    ) -> Sequence[ModelT]:
        statement = select(self.model).where(*where).offset(offset).limit(limit)
        if order_by:
            statement = statement.order_by(*order_by)
        if options:
            statement = statement.options(*options)
        return (await session.execute(statement)).scalars().all()

    async def count(
        self,
        session: AsyncSession,
        *where: ColumnExpressionArgument[bool],
    ) -> int:
        statement = select(func.count()).select_from(self.model).where(*where)
        return (await session.execute(statement)).scalar_one()

    async def exists(
        self,
        session: AsyncSession,
        *where: ColumnExpressionArgument[bool],
    ) -> bool:
        statement = select(select(self.model).where(*where).exists())
        return bool((await session.execute(statement)).scalar())

    async def add(self, session: AsyncSession, obj: ModelT) -> ModelT:
        """새 행을 추가하고 자동 생성값까지 확보한다.

        `flush()` 만 호출한다. 커밋은 서비스의 트랜잭션 블록이 담당한다.
        """
        session.add(obj)
        await _flush(session)
        return obj

    async def persist(self, session: AsyncSession, obj: ModelT) -> ModelT:
        """수정한 객체를 DB에 반영하고 서버가 계산한 값까지 다시 읽어온다.

        `onupdate=func.now()` 같은 서버 계산 컬럼은 UPDATE 뒤에 만료 상태가 된다.
        async 에서는 만료된 속성을 읽는 순간 `MissingGreenlet` 이 나므로
        여기서 명시적으로 `refresh()` 한다.
        """
        await _flush(session)
        await session.refresh(obj)
        return obj

    async def add_all(self, session: AsyncSession, objs: Sequence[ModelT]) -> Sequence[ModelT]:
        session.add_all(list(objs))
        await _flush(session)
        return objs

    async def remove(self, session: AsyncSession, obj: ModelT) -> None:
        await session.delete(obj)
        await session.flush()

    async def remove_where(
        self,
        session: AsyncSession,
        *where: ColumnExpressionArgument[bool],
    ) -> int:
        """조건에 맞는 행을 지우고 삭제된 행 수를 돌려준다."""
        result = await session.execute(delete(self.model).where(*where))
        return result.rowcount or 0


async def _flush(session: AsyncSession) -> None:
    """flush 중 unique 위반을 SQLAlchemy 와 무관한 `UniqueViolationError` 로 바꿔 올린다."""
    try:
        await session.flush()
    except IntegrityError as exc:
        if getattr(exc.orig, "sqlstate", None) != _UNIQUE_VIOLATION:
            raise
        constraint = getattr(exc.orig.__cause__, "constraint_name", None)
        raise UniqueViolationError(constraint) from exc
