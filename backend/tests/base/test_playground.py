from fastapi.testclient import TestClient

from src.core.config import Settings
from src.interfaces.main import create_app
from tests.conftest import use_in_memory_stores


def test_playground_is_served_in_local(client: TestClient) -> None:
    response = client.get("/playground/stt.html")

    assert response.status_code == 200
    assert "/api/v1/voice/stt" in response.text
    assert client.get("/playground/pcm-worklet.js").status_code == 200


def test_playground_is_hidden_outside_local() -> None:
    settings = Settings(
        _env_file=None,
        environment="dev",
        llm_provider="openai",
        openai_api_key="test-openai-key",
        jwt_secret_key="test-secret-key-that-is-at-least-32-bytes",
        database_url="postgresql+asyncpg://test:test@localhost:5432/test",
    )

    with TestClient(use_in_memory_stores(create_app(settings))) as client:
        assert client.get("/playground/stt.html").status_code == 404
