from dependency_injector import providers
from fastapi.testclient import TestClient

from tests.conftest import FakeRedis


class _Database:
    def __init__(self, healthy: bool) -> None:
        self._healthy = healthy

    async def ping(self, timeout: float = 2.0) -> None:
        if not self._healthy:
            raise ConnectionError("db down")

    async def dispose(self) -> None:
        pass


def test_live_does_not_check_dependencies(client: TestClient) -> None:
    assert client.get("/health/live").json() == {"status": "ok"}


def test_ready_is_ok_when_database_responds(app, container) -> None:
    database = providers.Object(_Database(healthy=True))
    with container.infrastructure.database.override(database), TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json()["checks"]["database"] == "ok"


def test_ready_is_unavailable_when_database_fails(app, container) -> None:
    database = providers.Object(_Database(healthy=False))
    with container.infrastructure.database.override(database), TestClient(app) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["checks"]["database"] == "fail"


def test_ready_is_unavailable_when_redis_fails(app, container) -> None:
    database = providers.Object(_Database(healthy=True))
    with (
        container.infrastructure.database.override(database),
        container.infrastructure.redis.override(providers.Object(FakeRedis(healthy=False))),
        TestClient(app) as client,
    ):
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["checks"] == {"database": "ok", "redis": "fail"}
