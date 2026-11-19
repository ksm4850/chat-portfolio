from fastapi.testclient import TestClient
from pydantic import SecretStr


def test_response_has_generated_request_id(client: TestClient) -> None:
    response = client.get("/health/live")

    assert len(response.headers["X-Request-ID"]) == 32


def test_valid_incoming_request_id_is_kept(client: TestClient) -> None:
    response = client.get("/health/live", headers={"X-Request-ID": "trace-abc.123"})

    assert response.headers["X-Request-ID"] == "trace-abc.123"


def test_malformed_incoming_request_id_is_replaced(client: TestClient) -> None:
    """로그 주입을 막기 위해 형식이 맞지 않는 값은 쓰지 않는다."""
    response = client.get("/health/live", headers={"X-Request-ID": "bad id\nINJECT"})

    assert response.headers["X-Request-ID"] != "bad id\nINJECT"
    assert len(response.headers["X-Request-ID"]) == 32


def test_unexpected_error_body_contains_request_id(settings) -> None:
    """local 은 debug 라 traceback 을 그대로 보여 주므로, 운영과 같은 설정으로 확인한다."""
    from src.interfaces.main import create_app

    app = create_app(
        settings.model_copy(update={"environment": "prod", "jwt_secret_key": SecretStr("x" * 32)})
    )

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("boom")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/boom", headers={"X-Request-ID": "req-500"})

    assert response.status_code == 500
    assert response.json()["error"]["requestId"] == "req-500"


def test_cors_is_off_by_default(client: TestClient) -> None:
    response = client.options(
        "/api/v1/users",
        headers={"Origin": "https://app.example.com", "Access-Control-Request-Method": "POST"},
    )

    assert "access-control-allow-origin" not in response.headers


def test_cors_allows_configured_origin(settings) -> None:
    from src.interfaces.main import create_app

    app = create_app(settings.model_copy(update={"cors_origins": ["https://app.example.com"]}))
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/users",
            headers={"Origin": "https://app.example.com", "Access-Control-Request-Method": "POST"},
        )

    assert response.headers["access-control-allow-origin"] == "https://app.example.com"
