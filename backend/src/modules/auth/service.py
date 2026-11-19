import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database import Database
from src.infrastructure.logging import get_logger
from src.infrastructure.security import (
    InvalidTokenError,
    TokenClaims,
    TokenService,
    TokenType,
)
from src.modules.auth.exceptions import (
    InactiveUserError,
    InvalidAuthTokenError,
    InvalidCredentialsError,
)
from src.modules.auth.models import RefreshToken
from src.modules.auth.repository import RefreshTokenRepository
from src.modules.auth.schema import TokenResponse
from src.modules.users.exceptions import UserNotFoundError
from src.modules.users.schema import UserAuthState, UserRead
from src.modules.users.service import UserService

logger = get_logger(__name__)


class AuthService:
    """로그인, 토큰 재발급(RTR), 로그아웃, 토큰으로 사용자 확인.

    refresh 토큰은 한 번 쓰면 폐기하고 같은 family 로 새 토큰을 발급한다.
    이미 폐기된 토큰이 다시 오면 탈취로 보고 family 전체를 폐기한다.
    사용자 `token_version` 이 바뀌면(비밀번호 변경 등) 이전 토큰은 모두 거부한다.
    비밀번호 검증과 사용자 조회는 `UserService` 가 맡는다.
    """

    def __init__(
        self,
        db: Database,
        user_service: UserService,
        refresh_token_repository: RefreshTokenRepository,
        token_service: TokenService,
    ) -> None:
        self._db = db
        self._user_service = user_service
        self._refresh_tokens = refresh_token_repository
        self._token_service = token_service

    async def login(self, email: str, password: str) -> TokenResponse:
        # 없는 이메일과 틀린 비밀번호를 응답으로 구분하지 않는다.
        state = await self._user_service.authenticate(email, password)
        if state is None:
            logger.info("로그인 실패", extra={"email_domain": _email_domain(email)})
            raise InvalidCredentialsError()
        if not state.user.is_active:
            raise InactiveUserError()

        async with self._db.transaction() as session:
            tokens = await self._issue_tokens(session, state, family_id=uuid.uuid4())

        logger.info("로그인 성공", extra={"user_id": str(state.user.id)})
        return tokens

    async def refresh(self, refresh_token: str) -> TokenResponse:
        claims = self._decode(refresh_token, expected_type="refresh")
        state = await self._load_active_user(claims)
        user = state.user
        jti = _parse_uuid(claims.jti)

        reused = False
        async with self._db.transaction() as session:
            stored = await self._refresh_tokens.get_for_update(session, jti)
            if stored is None or stored.user_id != user.id:
                raise InvalidAuthTokenError()

            now = datetime.now(UTC)
            if stored.revoked_at is not None:
                # 예외를 블록 안에서 올리면 family 폐기까지 롤백되므로 커밋 후에 올린다.
                await self._refresh_tokens.revoke_family(session, stored.family_id, now)
                reused = True
            else:
                stored.revoked_at = now
                tokens = await self._issue_tokens(session, state, family_id=stored.family_id)

        if reused:
            logger.warning("폐기된 refresh 토큰 재사용", extra={"user_id": str(user.id)})
            raise InvalidAuthTokenError()

        logger.info("토큰 재발급", extra={"user_id": str(user.id)})
        return tokens

    async def logout(self, refresh_token: str) -> None:
        """refresh 토큰이 속한 family 를 폐기한다. 이미 폐기된 토큰이어도 성공으로 본다."""
        claims = self._decode(refresh_token, expected_type="refresh")
        jti = _parse_uuid(claims.jti)

        async with self._db.transaction() as session:
            stored = await self._refresh_tokens.get_for_update(session, jti)
            if stored is None:
                return
            await self._refresh_tokens.revoke_family(session, stored.family_id, datetime.now(UTC))

        logger.info("로그아웃", extra={"user_id": str(stored.user_id)})

    async def purge_expired_tokens(self) -> int:
        """만료된 refresh 토큰을 지운다. 만료 전 폐기 토큰은 재사용 감지에 필요해 남긴다."""
        async with self._db.transaction() as session:
            deleted = await self._refresh_tokens.remove_where(
                session, RefreshToken.expires_at < datetime.now(UTC)
            )

        logger.info("만료 refresh 토큰 정리", extra={"deleted": deleted})
        return deleted

    async def resolve_user(self, access_token: str) -> UserRead:
        """access 토큰으로 현재 사용자를 확인한다. 인증 의존성이 사용한다."""
        claims = self._decode(access_token, expected_type="access")
        return (await self._load_active_user(claims)).user

    async def _issue_tokens(
        self, session: AsyncSession, state: UserAuthState, *, family_id: uuid.UUID
    ) -> TokenResponse:
        user_id = state.user.id
        subject = str(user_id)
        version = state.token_version
        refresh = self._token_service.create_refresh_token(subject, version=version)
        await self._refresh_tokens.add(
            session,
            RefreshToken(
                jti=uuid.UUID(refresh.jti),
                user_id=user_id,
                family_id=family_id,
                expires_at=refresh.expires_at,
            ),
        )
        return TokenResponse(
            access_token=self._token_service.create_access_token(subject, version=version),
            refresh_token=refresh.token,
            expires_in=self._token_service.access_token_expires_in,
        )

    def _decode(self, token: str, *, expected_type: TokenType) -> TokenClaims:
        try:
            return self._token_service.decode(token, expected_type=expected_type)
        except InvalidTokenError as exc:
            raise InvalidAuthTokenError() from exc

    async def _load_active_user(self, claims: TokenClaims) -> UserAuthState:
        try:
            state = await self._user_service.get_auth_state(_parse_uuid(claims.subject))
        except UserNotFoundError as exc:
            # 삭제된 사용자의 토큰은 유효하지 않은 토큰으로 취급한다.
            raise InvalidAuthTokenError() from exc

        if state.token_version != claims.version:
            raise InvalidAuthTokenError()
        if not state.user.is_active:
            raise InactiveUserError()
        return state


def _parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise InvalidAuthTokenError() from exc


def _email_domain(email: str) -> str:
    """로그에는 이메일 원문을 남기지 않고 도메인만 남긴다."""
    _, _, domain = email.partition("@")
    return domain or "unknown"
