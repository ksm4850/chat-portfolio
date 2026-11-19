import time

import pytest

from src.infrastructure.security import InvalidTokenError, PasswordHasher, TokenService


@pytest.fixture
def hasher() -> PasswordHasher:
    return PasswordHasher()


@pytest.fixture
def tokens() -> TokenService:
    return TokenService("test-secret-key", access_token_expire_minutes=30)


def test_password_hash_is_not_reversible(hasher: PasswordHasher) -> None:
    hashed = hasher.hash("correct-horse")

    assert "correct-horse" not in hashed
    assert hashed.startswith("$argon2")


def test_password_verify(hasher: PasswordHasher) -> None:
    hashed = hasher.hash("correct-horse")

    assert hasher.verify("correct-horse", hashed) is True
    assert hasher.verify("wrong-password", hashed) is False


def test_same_password_gets_different_hash(hasher: PasswordHasher) -> None:
    """salt 가 달라 같은 비밀번호도 해시가 다르다."""
    assert hasher.hash("same-password") != hasher.hash("same-password")


def test_verify_dummy_always_fails(hasher: PasswordHasher) -> None:
    """사용자가 없을 때 쓰는 더미 검증은 어떤 입력에도 통과하지 않는다."""
    assert hasher.verify_dummy("any-password") is False


def test_verify_survives_broken_hash(hasher: PasswordHasher) -> None:
    """저장된 해시가 깨져 있어도 예외 대신 False 를 돌려준다."""
    assert hasher.verify("any", "not-a-hash") is False


def test_access_token_roundtrip(tokens: TokenService) -> None:
    token = tokens.create_access_token("user-1", version=0)
    claims = tokens.decode(token, expected_type="access")

    assert claims.subject == "user-1"
    assert claims.token_type == "access"


def test_refresh_token_is_not_accepted_as_access(tokens: TokenService) -> None:
    """종류가 다른 토큰은 거부한다."""
    refresh = tokens.create_refresh_token("user-1", version=0).token

    with pytest.raises(InvalidTokenError):
        tokens.decode(refresh, expected_type="access")


def test_token_signed_with_other_secret_is_rejected(tokens: TokenService) -> None:
    other = TokenService("another-secret-key")
    token = other.create_access_token("user-1", version=0)

    with pytest.raises(InvalidTokenError):
        tokens.decode(token, expected_type="access")


def test_expired_token_is_rejected() -> None:
    expired = TokenService("test-secret-key", access_token_expire_minutes=0)
    token = expired.create_access_token("user-1", version=0)
    time.sleep(1)

    with pytest.raises(InvalidTokenError):
        expired.decode(token, expected_type="access")


def test_malformed_token_is_rejected(tokens: TokenService) -> None:
    with pytest.raises(InvalidTokenError):
        tokens.decode("not.a.jwt", expected_type="access")


def test_tokens_are_unique_per_issue(tokens: TokenService) -> None:
    """jti 가 달라 같은 사용자라도 토큰이 겹치지 않는다."""
    first = tokens.decode(tokens.create_access_token("user-1", version=0), expected_type="access")
    second = tokens.decode(tokens.create_access_token("user-1", version=0), expected_type="access")

    assert first.jti != second.jti


def test_access_token_expires_in_is_seconds() -> None:
    assert TokenService("k", access_token_expire_minutes=30).access_token_expires_in == 1800


def test_refresh_token_exposes_jti_and_expiry(tokens: TokenService) -> None:
    """RTR 저장에 쓰는 jti·만료 시각이 토큰 claim 과 일치한다."""
    issued = tokens.create_refresh_token("user-1", version=0)
    claims = tokens.decode(issued.token, expected_type="refresh")

    assert claims.jti == issued.jti
    assert claims.expires_at == issued.expires_at.replace(microsecond=0)


def test_token_carries_version(tokens: TokenService) -> None:
    token = tokens.create_access_token("user-1", version=3)

    assert tokens.decode(token, expected_type="access").version == 3
