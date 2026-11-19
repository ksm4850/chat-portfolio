"""사용자·인증 API 통합 검증. 실제 DB가 필요하다.

`docker compose up -d` + `uv run alembic upgrade head` 가 되어 있지 않으면 건너뛴다.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from src.core.config import Settings, get_settings
from src.interfaces.main import create_app
from tests.conftest import use_in_memory_stores

pytestmark = pytest.mark.integration

EMAIL = "api-test@example.com"
OTHER_EMAIL = "api-test-other@example.com"
ADMIN_EMAIL = "api-test-admin@example.com"
PASSWORD = "test-password-1234"
TEST_EMAILS = (EMAIL, OTHER_EMAIL, ADMIN_EMAIL)


def _sync_url(url: str) -> str:
    return url.replace("+asyncpg", "+psycopg2").replace("postgresql+psycopg2", "postgresql")


@pytest.fixture
def api_settings() -> Settings:
    get_settings.cache_clear()
    return Settings(environment="local", jwt_secret_key="integration-test-secret")


@pytest.fixture
def db_cleanup(api_settings: Settings) -> Iterator[None]:
    engine = create_engine(_sync_url(api_settings.database_url))
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM users LIMIT 1"))
    except Exception as exc:
        engine.dispose()
        pytest.skip(f"실제 DB를 쓸 수 없다: {type(exc).__name__}")

    def purge() -> None:
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM users WHERE email = ANY(:emails)"),
                {"emails": list(TEST_EMAILS)},
            )

    purge()
    yield
    purge()
    engine.dispose()


@pytest.fixture
def client(api_settings: Settings, db_cleanup: None) -> Iterator[TestClient]:
    with TestClient(use_in_memory_stores(create_app(api_settings))) as test_client:
        yield test_client


def _signup(client: TestClient, email: str = EMAIL) -> dict:
    response = client.post(
        "/api/v1/users",
        json={"email": email, "password": PASSWORD, "fullName": "테스트"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _login(client: TestClient, email: str = EMAIL, password: str = PASSWORD):
    return client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_signup_returns_camel_case_without_password(client: TestClient) -> None:
    body = _signup(client)

    assert body["email"] == EMAIL
    assert body["fullName"] == "테스트"
    assert body["isActive"] is True
    assert body["isSuperuser"] is False
    assert "hashedPassword" not in body
    assert "password" not in body


def test_duplicate_email_is_rejected(client: TestClient) -> None:
    _signup(client)

    response = client.post("/api/v1/users", json={"email": EMAIL, "password": PASSWORD})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_already_exists"


def test_short_password_is_rejected(client: TestClient) -> None:
    response = client.post("/api/v1/users", json={"email": EMAIL, "password": "short"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_login_returns_oauth2_snake_case_token(client: TestClient) -> None:
    _signup(client)

    body = _login(client).json()

    # OAuth2 규격 필드명. camelCase 로 바뀌면 Swagger Authorize 와 표준 클라이언트가 깨진다.
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 1800
    assert body["access_token"]
    assert body["refresh_token"]


def test_login_with_wrong_password_is_rejected(client: TestClient) -> None:
    _signup(client)

    response = _login(client, password="wrong-password-1234")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_login_with_unknown_email_gives_same_error(client: TestClient) -> None:
    """사용자 유무가 응답으로 드러나지 않는다."""
    response = _login(client, email="nobody@example.com")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_me_requires_token(client: TestClient) -> None:
    response = client.get("/api/v1/users/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


def test_me_returns_current_user(client: TestClient) -> None:
    _signup(client)
    token = _login(client).json()["access_token"]

    body = client.get("/api/v1/users/me", headers=_auth(token)).json()

    assert body["email"] == EMAIL


def test_refresh_issues_new_access_token(client: TestClient) -> None:
    _signup(client)
    refresh_token = _login(client).json()["refresh_token"]

    response = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})

    assert response.status_code == 200
    new_access = response.json()["access_token"]
    assert client.get("/api/v1/users/me", headers=_auth(new_access)).status_code == 200


def _refresh(client: TestClient, refresh_token: str):
    return client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})


def test_refresh_rotates_refresh_token(client: TestClient) -> None:
    _signup(client)
    first = _login(client).json()["refresh_token"]

    second = _refresh(client, first).json()["refresh_token"]

    assert second != first
    assert _refresh(client, second).status_code == 200


def test_reused_refresh_token_revokes_whole_family(client: TestClient) -> None:
    """이미 쓴 refresh 토큰이 다시 오면 탈취로 보고, 회전된 최신 토큰까지 폐기한다."""
    _signup(client)
    first = _login(client).json()["refresh_token"]
    second = _refresh(client, first).json()["refresh_token"]

    reused = _refresh(client, first)

    assert reused.status_code == 401
    assert reused.json()["error"]["code"] == "invalid_token"
    assert _refresh(client, second).status_code == 401


def test_reuse_does_not_affect_other_login_sessions(client: TestClient) -> None:
    _signup(client)
    victim = _login(client).json()["refresh_token"]
    other_device = _login(client).json()["refresh_token"]
    _refresh(client, victim)

    _refresh(client, victim)

    assert _refresh(client, other_device).status_code == 200


def test_logout_revokes_refresh_token(client: TestClient) -> None:
    _signup(client)
    first = _login(client).json()["refresh_token"]
    second = _refresh(client, first).json()["refresh_token"]

    response = client.post("/api/v1/auth/logout", json={"refresh_token": second})

    assert response.status_code == 204
    assert _refresh(client, second).status_code == 401


def test_access_token_cannot_be_used_to_refresh(client: TestClient) -> None:
    _signup(client)
    access_token = _login(client).json()["access_token"]

    response = client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


def test_refresh_token_cannot_be_used_as_access_token(client: TestClient) -> None:
    _signup(client)
    refresh_token = _login(client).json()["refresh_token"]

    response = client.get("/api/v1/users/me", headers=_auth(refresh_token))

    assert response.status_code == 401


def test_password_change_invalidates_old_password(client: TestClient) -> None:
    _signup(client)
    token = _login(client).json()["access_token"]

    response = client.post(
        "/api/v1/users/me/password",
        json={"currentPassword": PASSWORD, "newPassword": "new-password-5678"},
        headers=_auth(token),
    )

    assert response.status_code == 204
    assert _login(client, password=PASSWORD).status_code == 401
    assert _login(client, password="new-password-5678").status_code == 200


def test_password_change_revokes_existing_tokens(client: TestClient) -> None:
    """비밀번호를 바꾸면 이전에 발급한 access·refresh 토큰을 모두 거부한다."""
    _signup(client)
    tokens = _login(client).json()

    client.post(
        "/api/v1/users/me/password",
        json={"currentPassword": PASSWORD, "newPassword": "new-password-5678"},
        headers=_auth(tokens["access_token"]),
    )

    assert client.get("/api/v1/users/me", headers=_auth(tokens["access_token"])).status_code == 401
    assert _refresh(client, tokens["refresh_token"]).status_code == 401


def test_password_change_requires_correct_current_password(client: TestClient) -> None:
    _signup(client)
    token = _login(client).json()["access_token"]

    response = client.post(
        "/api/v1/users/me/password",
        json={"currentPassword": "wrong-password-1234", "newPassword": "new-password-5678"},
        headers=_auth(token),
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_current_password"


def test_update_me(client: TestClient) -> None:
    _signup(client)
    token = _login(client).json()["access_token"]

    body = client.patch(
        "/api/v1/users/me", json={"fullName": "바뀐 이름"}, headers=_auth(token)
    ).json()

    assert body["fullName"] == "바뀐 이름"


def test_list_users_requires_superuser(client: TestClient) -> None:
    _signup(client)
    token = _login(client).json()["access_token"]

    response = client.get("/api/v1/users", headers=_auth(token))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_enough_permission"


def test_invalid_token_is_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/users/me", headers=_auth("not.a.jwt"))

    assert response.status_code == 401


def test_email_is_normalized_on_signup_and_login(client: TestClient) -> None:
    body = _signup(client, email=EMAIL.upper())

    assert body["email"] == EMAIL
    assert _login(client, email=EMAIL.title()).status_code == 200


def test_email_differing_only_in_case_is_duplicate(client: TestClient) -> None:
    _signup(client)

    response = client.post("/api/v1/users", json={"email": EMAIL.upper(), "password": PASSWORD})

    assert response.status_code == 409


def test_user_cannot_deactivate_self(client: TestClient) -> None:
    """isActive 는 관리자 전용 항목이라 /me 수정에서 무시된다."""
    _signup(client)
    token = _login(client).json()["access_token"]

    body = client.patch("/api/v1/users/me", json={"isActive": False}, headers=_auth(token)).json()

    assert body["isActive"] is True


async def test_create_superuser_command(api_settings: Settings, db_cleanup: None) -> None:
    from src.interfaces.cli.create_superuser import create_superuser

    user = await create_superuser(ADMIN_EMAIL.upper(), PASSWORD)

    assert user.is_superuser is True
    assert user.email == ADMIN_EMAIL


async def test_purge_removes_only_expired_tokens(
    client: TestClient, api_settings: Settings, db_cleanup: None
) -> None:
    from src.interfaces.cli.purge_expired_tokens import purge_expired_tokens

    _signup(client)
    _login(client)
    _login(client)
    engine = create_engine(_sync_url(api_settings.database_url))
    count_sql = text(
        "SELECT count(*) FROM refresh_tokens t JOIN users u ON u.id = t.user_id"
        " WHERE u.email = :email"
    )
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE refresh_tokens SET expires_at = now() - interval '1 day'"
                " WHERE jti = (SELECT t.jti FROM refresh_tokens t JOIN users u ON u.id = t.user_id"
                " WHERE u.email = :email LIMIT 1)"
            ),
            {"email": EMAIL},
        )

    await purge_expired_tokens()

    with engine.connect() as conn:
        remaining = conn.execute(count_sql, {"email": EMAIL}).scalar_one()
    engine.dispose()
    assert remaining == 1
