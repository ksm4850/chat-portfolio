from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from src.core.config import get_settings
from src.core.container import AppContainer
from src.infrastructure.logging import configure_logging


@asynccontextmanager
async def app_container() -> AsyncIterator[AppContainer]:
    """CLI 명령이 HTTP 앱과 같은 설정·조립으로 서비스를 쓰게 한다."""
    settings = get_settings()
    configure_logging(settings)
    container = AppContainer(settings=settings)
    try:
        yield container
    finally:
        await container.infrastructure().database().dispose()
        await container.infrastructure().redis().aclose()
        container.infrastructure().tracer().shutdown()
