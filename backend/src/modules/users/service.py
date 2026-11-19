import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database import Database, UniqueViolationError
from src.infrastructure.logging import get_logger
from src.infrastructure.security import PasswordHasher
from src.modules.users.exceptions import (
    EmailAlreadyExistsError,
    InvalidCurrentPasswordError,
    UserNotFoundError,
)
from src.modules.users.models import User
from src.modules.users.repository import UserRepository
from src.modules.users.schema import (
    PasswordUpdate,
    UserAuthState,
    UserCreate,
    UserPage,
    UserRead,
    UserUpdate,
    normalize_email,
)

logger = get_logger(__name__)


class UserService:
    """사용자 업무 규칙.

    공개 메서드는 트랜잭션 경계를 직접 열고, `session` 을 인자로 받는 메서드는
    경계를 열지 않는다. 뒤쪽은 다른 서비스가 한 트랜잭션으로 묶어 쓸 수 있다.
    """

    def __init__(
        self,
        db: Database,
        repository: UserRepository,
        password_hasher: PasswordHasher,
    ) -> None:
        self._db = db
        self._repository = repository
        self._password_hasher = password_hasher

    async def create_user(self, payload: UserCreate, *, is_superuser: bool = False) -> UserRead:
        """`is_superuser` 는 관리자 생성 CLI 에서만 켠다. 가입 API 로는 노출하지 않는다."""
        async with self._db.transaction() as session:
            user = await self.register(session, payload, is_superuser=is_superuser)
            result = UserRead.model_validate(user)

        logger.info("사용자 생성", extra={"user_id": str(result.id), "is_superuser": is_superuser})
        return result

    async def register(
        self, session: AsyncSession, payload: UserCreate, *, is_superuser: bool = False
    ) -> User:
        """트랜잭션에 참여하는 생성 동작. 경계를 열지 않는다."""
        if await self._repository.email_exists(session, payload.email):
            raise EmailAlreadyExistsError()

        user = User(
            email=payload.email,
            hashed_password=self._password_hasher.hash(payload.password),
            full_name=payload.full_name,
            is_superuser=is_superuser,
        )
        try:
            return await self._repository.add(session, user)
        except UniqueViolationError as exc:
            # 사전 확인과 insert 사이에 같은 이메일이 먼저 들어온 경우
            raise EmailAlreadyExistsError() from exc

    async def get_user(self, user_id: uuid.UUID) -> UserRead:
        async with self._db.read() as session:
            user = await self._repository.get_by_id(session, user_id)
            if user is None:
                raise UserNotFoundError()
            return UserRead.model_validate(user)

    async def authenticate(self, email: str, password: str) -> UserAuthState | None:
        """이메일·비밀번호가 맞으면 사용자를 돌려준다. 활성 여부는 호출하는 쪽이 판단한다.

        사용자가 없어도 같은 비용으로 해시를 검증해 응답 시간으로 유무가 드러나지 않게 한다.
        """
        async with self._db.read() as session:
            user = await self._repository.get_by_email(session, normalize_email(email))
            if user is None:
                self._password_hasher.verify_dummy(password)
                return None
            if not self._password_hasher.verify(password, user.hashed_password):
                return None
            return _auth_state(user)

    async def get_auth_state(self, user_id: uuid.UUID) -> UserAuthState:
        """토큰 검증에 필요한 사용자 상태. 인증 모듈이 쓴다."""
        async with self._db.read() as session:
            user = await self._repository.get_by_id(session, user_id)
            if user is None:
                raise UserNotFoundError()
            return _auth_state(user)

    async def list_users(self, *, offset: int = 0, limit: int = 50) -> UserPage:
        async with self._db.read() as session:
            users = await self._repository.find(
                session, order_by=[User.created_at.desc()], offset=offset, limit=limit
            )
            total_count = await self._repository.count(session)

        return UserPage(
            items=[UserRead.model_validate(user) for user in users],
            total_count=total_count,
            offset=offset,
            limit=limit,
        )

    async def update_user(self, user_id: uuid.UUID, payload: UserUpdate) -> UserRead:
        """`UserAdminUpdate` 를 받으면 관리자 전용 항목까지 반영한다."""
        async with self._db.transaction() as session:
            user = await self._repository.get_by_id(session, user_id)
            if user is None:
                raise UserNotFoundError()

            changes = payload.model_dump(exclude_unset=True)
            for field, value in changes.items():
                setattr(user, field, value)
            # updated_at 은 DB 가 계산하므로 다시 읽어야 응답에 담을 수 있다.
            await self._repository.persist(session, user)
            result = UserRead.model_validate(user)

        logger.info("사용자 수정", extra={"user_id": str(user_id), "fields": sorted(changes)})
        return result

    async def change_password(self, user_id: uuid.UUID, payload: PasswordUpdate) -> None:
        async with self._db.transaction() as session:
            user = await self._repository.get_by_id(session, user_id)
            if user is None:
                raise UserNotFoundError()

            if not self._password_hasher.verify(payload.current_password, user.hashed_password):
                raise InvalidCurrentPasswordError()

            user.hashed_password = self._password_hasher.hash(payload.new_password)
            user.token_version += 1
            await self._repository.persist(session, user)

        logger.info("비밀번호 변경", extra={"user_id": str(user_id)})

    async def delete_user(self, user_id: uuid.UUID) -> None:
        async with self._db.transaction() as session:
            user = await self._repository.get_by_id(session, user_id)
            if user is None:
                raise UserNotFoundError()
            await self._repository.remove(session, user)

        logger.info("사용자 삭제", extra={"user_id": str(user_id)})


def _auth_state(user: User) -> UserAuthState:
    return UserAuthState(user=UserRead.model_validate(user), token_version=user.token_version)
