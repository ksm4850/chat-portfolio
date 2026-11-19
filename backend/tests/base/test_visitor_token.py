import uuid

import pytest

from src.infrastructure.rate_limit import InMemoryRateLimiter
from src.infrastructure.security import TokenService
from src.modules.visitor.exceptions import InvalidVisitorTokenError
from src.modules.visitor.service import VisitorService

SECRET = "test-secret-key-that-is-at-least-32-bytes"


def _service(secret: str = SECRET, days: int = 30) -> VisitorService:
    tokens = TokenService(secret, visitor_token_expire_days=days)
    return VisitorService(tokens, InMemoryRateLimiter(), tokens_per_ip_per_hour=10)


async def test_issued_token_resolves_to_same_visitor() -> None:
    service = _service()
    token = (await service.issue("1.2.3.4")).visitor_token

    assert service.resolve(token) == service.resolve(token)
    assert isinstance(service.resolve(token), uuid.UUID)


@pytest.mark.parametrize(
    "token",
    [
        None,
        "",
        "not-a-jwt",
        TokenService(SECRET).create_access_token(str(uuid.uuid4()), version=0),
        TokenService("other-secret-key-that-is-at-least-32b").create_visitor_token("x").token,
        TokenService(SECRET, visitor_token_expire_days=-1).create_visitor_token("x").token,
    ],
    ids=["missing", "empty", "garbage", "access-token", "other-key", "expired"],
)
def test_invalid_tokens_are_rejected(token: str | None) -> None:
    with pytest.raises(InvalidVisitorTokenError):
        _service().resolve(token)
