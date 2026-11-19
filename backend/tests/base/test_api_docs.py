from fastapi.testclient import TestClient

from src.core.config import Settings
from src.interfaces.main import create_app

PROD = Settings(
    environment="prod",
    jwt_secret_key="test-secret-key-that-is-at-least-32-bytes",
    database_url="postgresql+asyncpg://test:test@localhost:5432/test",
    llm_provider="openai",
    openai_api_key="test-openai-key",
)


def test_docs_are_hidden_outside_local() -> None:
    client = TestClient(create_app(PROD))

    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404, path


def test_docs_are_served_locally(client) -> None:
    assert client.get("/openapi.json").status_code == 200
