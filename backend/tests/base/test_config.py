import pytest
from pydantic import ValidationError

from src.core.config import Settings

SAFE_SECRET = "test-secret-key-that-is-at-least-32-bytes"
SAFE_URL = "postgresql+asyncpg://test:test@localhost:5432/test"
SAFE_PROD = {
    "jwt_secret_key": SAFE_SECRET,
    "database_url": SAFE_URL,
    "llm_provider": "openai",
    "openai_api_key": "test-openai-key",
}


def test_local_allows_default_values() -> None:
    assert Settings(_env_file=None, environment="local").environment == "local"


@pytest.mark.parametrize(
    "overrides",
    [
        {"jwt_secret_key": "change-me-in-env"},
        {"jwt_secret_key": "too-short"},
        {"database_url": "postgresql+asyncpg://app:changeme@db:5432/app"},
        {"database_echo": True},
        {"llm_provider": "claude_cli"},
        {"openai_api_key": ""},
    ],
)
def test_non_local_rejects_unsafe_values(overrides: dict) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="prod", **{**SAFE_PROD, **overrides})


def test_validation_error_does_not_leak_secret() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None, environment="prod", jwt_secret_key="leak-me", database_url=SAFE_URL
        )

    assert "leak-me" not in str(exc_info.value)


def test_non_local_accepts_safe_values() -> None:
    settings = Settings(_env_file=None, environment="prod", **SAFE_PROD)

    assert settings.environment == "prod"


def test_local_does_not_require_openai_key() -> None:
    settings = Settings(_env_file=None, environment="local", llm_provider="openai")

    assert settings.openai_api_key.get_secret_value() == ""
