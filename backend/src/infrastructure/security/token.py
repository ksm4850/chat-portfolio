"""JWT 발급·검증 어댑터."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import uuid4

import jwt

TokenType = Literal["access", "refresh", "visitor"]


class InvalidTokenError(Exception):
    """서명·만료·형식이 잘못된 토큰."""


@dataclass(frozen=True)
class TokenClaims:
    """검증을 통과한 토큰에서 읽은 값."""

    subject: str
    token_type: TokenType
    expires_at: datetime
    jti: str
    version: int


@dataclass(frozen=True)
class IssuedToken:
    """발급한 토큰과 저장·추적에 필요한 값."""

    token: str
    jti: str
    expires_at: datetime


class TokenService:
    """access/refresh 토큰을 만들고 검증한다.

    비밀키는 이 객체 안에만 두고 밖으로 반환하지 않는다.
    """

    def __init__(
        self,
        secret_key: str,
        *,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 30,
        refresh_token_expire_days: int = 14,
        visitor_token_expire_days: int = 30,
    ) -> None:
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._access_expire = timedelta(minutes=access_token_expire_minutes)
        self._refresh_expire = timedelta(days=refresh_token_expire_days)
        self._visitor_expire = timedelta(days=visitor_token_expire_days)

    @property
    def access_token_expires_in(self) -> int:
        """access 토큰 유효시간(초). 로그인 응답의 `expiresIn` 에 사용한다."""
        return int(self._access_expire.total_seconds())

    def create_access_token(self, subject: str, *, version: int) -> str:
        return self._encode(subject, "access", self._access_expire, version).token

    def create_refresh_token(self, subject: str, *, version: int) -> IssuedToken:
        """refresh 토큰은 회전·폐기를 위해 jti 와 만료 시각을 함께 돌려준다."""
        return self._encode(subject, "refresh", self._refresh_expire, version)

    def create_visitor_token(self, visitor_id: str) -> IssuedToken:
        """로그인하지 않은 방문자를 구분하는 토큰. 사용자 계정과 무관해 version 은 0 이다."""
        return self._encode(visitor_id, "visitor", self._visitor_expire, 0)

    def decode(self, token: str, *, expected_type: TokenType) -> TokenClaims:
        """토큰을 검증하고 claim 을 돌려준다.

        서명·만료가 잘못되었거나 종류가 다르면 `InvalidTokenError` 를 올린다.
        """
        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                self._secret_key,
                algorithms=[self._algorithm],
                options={"require": ["sub", "exp", "type", "jti", "ver"]},
            )
        except jwt.PyJWTError as exc:
            raise InvalidTokenError(str(exc)) from exc

        if payload.get("type") != expected_type:
            raise InvalidTokenError("토큰 종류가 다르다.")

        return TokenClaims(
            subject=str(payload["sub"]),
            token_type=expected_type,
            expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
            jti=str(payload["jti"]),
            version=int(payload["ver"]),
        )

    def _encode(
        self, subject: str, token_type: TokenType, expires_in: timedelta, version: int
    ) -> IssuedToken:
        issued_at = datetime.now(UTC)
        expires_at = issued_at + expires_in
        jti = str(uuid4())
        payload = {
            "sub": subject,
            "type": token_type,
            "iat": issued_at,
            "exp": expires_at,
            "jti": jti,
            "ver": version,
        }
        token = jwt.encode(payload, self._secret_key, algorithm=self._algorithm)
        return IssuedToken(token=token, jti=jti, expires_at=expires_at)
