import uuid

from src.core.exceptions import TooManyRequestsError
from src.infrastructure.logging import get_logger
from src.infrastructure.rate_limit import RateLimiter
from src.infrastructure.security import InvalidTokenError, TokenService
from src.modules.visitor.exceptions import InvalidVisitorTokenError
from src.modules.visitor.schema import VisitorToken

logger = get_logger(__name__)

_HOUR = 3600


class VisitorService:
    """로그인하지 않은 방문자를 서명된 토큰으로 구분한다.

    토큰 자체가 신원이라 방문자 정보는 따로 저장하지 않는다.
    서명이 있어 임의의 ID 를 지어낼 수 없고, 시크릿 창 등으로 새 토큰을 계속 받는 우회는
    IP 당 발급 수로 막는다.
    """

    def __init__(
        self, token_service: TokenService, rate_limiter: RateLimiter, tokens_per_ip_per_hour: int
    ) -> None:
        self._tokens = token_service
        self._limiter = rate_limiter
        self._tokens_per_ip_per_hour = tokens_per_ip_per_hour

    async def issue(self, client_ip: str) -> VisitorToken:
        retry_after = await self._limiter.hit(
            f"visitor:issue:ip:{client_ip}",
            limit=self._tokens_per_ip_per_hour,
            window_seconds=_HOUR,
        )
        if retry_after is not None:
            raise TooManyRequestsError(retry_after)

        visitor_id = uuid.uuid4()
        issued = self._tokens.create_visitor_token(str(visitor_id))
        logger.info("방문자 토큰 발급", extra={"visitor_id": str(visitor_id)})
        return VisitorToken(visitor_token=issued.token, expires_at=issued.expires_at)

    def resolve(self, token: str | None) -> uuid.UUID:
        if not token:
            raise InvalidVisitorTokenError()
        try:
            claims = self._tokens.decode(token, expected_type="visitor")
            return uuid.UUID(claims.subject)
        except (InvalidTokenError, ValueError) as exc:
            raise InvalidVisitorTokenError() from exc
