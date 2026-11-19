import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.core.config import Settings
from src.infrastructure.rate_limit import InMemoryRateLimiter
from src.interfaces.main import create_app
from src.modules.chat.session_store import InMemorySessionStore
from src.modules.guide.history import InMemoryGuideHistory

TEST_SECRET = "test-secret-key"

EVAL_DIR = Path(__file__).with_name("eval")


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool | None:
    # eval 은 실제 LLM·채점 호출로 요금이 나간다.
    # make eval(RUN_EVAL=1 + deepeval 플러그인)에서만 모으고, IDE 등에서 플러그인이 켜져도
    # RUN_EVAL 이 없으면 모으지 않는다.
    if collection_path == EVAL_DIR:
        requested = os.environ.get("RUN_EVAL") == "1"
        return not (requested and config.pluginmanager.hasplugin("deepeval"))
    return None


@pytest.fixture(autouse=True)
def _no_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    """`.env` 에 Langfuse 키가 있어도 테스트는 추적을 보내지 않는다.

    환경변수가 .env 보다 우선한다.
    """
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "")


class FakeRedis:
    """Redis 를 쓰는 provider 는 메모리 구현으로 바꾸므로 헬스체크·종료 처리만 흉내 낸다."""

    def __init__(self, healthy: bool = True) -> None:
        self.healthy = healthy

    async def ping(self) -> bool:
        if not self.healthy:
            raise ConnectionError("redis down")
        return True

    async def aclose(self) -> None:
        pass


def use_in_memory_stores(app: FastAPI) -> FastAPI:
    """Redis 없이 돌도록 Redis 기반 provider 를 메모리 구현으로 바꾼다.

    실행 사이에 카운터가 남지 않아 로그인·대화 제한 테스트가 서로 영향을 주지 않는다.
    """
    container = app.state.container
    container.infrastructure.redis.override(FakeRedis())
    container.infrastructure.rate_limiter.override(InMemoryRateLimiter())
    container.chat.session_store.override(InMemorySessionStore())
    container.guide.history.override(InMemoryGuideHistory())
    return app


@pytest.fixture
def settings() -> Settings:
    return Settings(
        environment="local",
        jwt_secret_key=TEST_SECRET,
        database_url="postgresql+asyncpg://test:test@localhost:5432/test",
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    """DB·Redis 없이 라우터·컨테이너 조립만 확인하는 앱."""
    return use_in_memory_stores(create_app(settings))


@pytest.fixture
def container(app: FastAPI):
    return app.state.container


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
