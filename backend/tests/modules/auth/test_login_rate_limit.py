"""로그인 시도 제한. 서비스를 대체해 DB 없이 검증한다."""

from dependency_injector import providers
from fastapi.testclient import TestClient

from src.modules.auth.exceptions import InvalidCredentialsError


class _RejectingAuthService:
    async def login(self, email: str, password: str):
        raise InvalidCredentialsError()


def _login(client: TestClient, email: str):
    return client.post("/api/v1/auth/login", data={"username": email, "password": "wrong-password"})


def _client(app, container, settings, **limits) -> TestClient:
    container.settings.override(providers.Object(settings.model_copy(update=limits)))
    container.auth.service.override(providers.Object(_RejectingAuthService()))
    return TestClient(app)


def test_account_is_limited_with_retry_after(app, container, settings) -> None:
    with _client(app, container, settings, login_rate_limit_per_account=3) as client:
        statuses = [_login(client, "a@example.com").status_code for _ in range(4)]
        blocked = _login(client, "a@example.com")

    assert statuses == [401, 401, 401, 429]
    assert blocked.json()["error"]["code"] == "too_many_requests"
    assert int(blocked.headers["Retry-After"]) > 0


def test_email_case_does_not_bypass_account_limit(app, container, settings) -> None:
    with _client(app, container, settings, login_rate_limit_per_account=1) as client:
        _login(client, "a@example.com")
        response = _login(client, "A@Example.com")

    assert response.status_code == 429


def test_ip_limit_applies_across_accounts(app, container, settings) -> None:
    with _client(
        app, container, settings, login_rate_limit_per_account=10, login_rate_limit_per_ip=3
    ) as client:
        statuses = [_login(client, f"user{i}@example.com").status_code for i in range(4)]

    assert statuses == [401, 401, 401, 429]
