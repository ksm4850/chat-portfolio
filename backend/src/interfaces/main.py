from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.core.config import Settings, get_settings
from src.core.container import AppContainer
from src.infrastructure.logging import configure_logging
from src.interfaces.api.v1 import router as v1_router
from src.interfaces.error_handlers import register_exception_handlers
from src.interfaces.health import router as health_router
from src.interfaces.middleware import REQUEST_ID_HEADER, RequestContextMiddleware

PLAYGROUND_DIR = Path(__file__).parent / "playground"
ADMIN_UI_DIR = Path(__file__).parent / "admin_ui"


def create_app(settings: Settings | None = None) -> FastAPI:
    """앱 팩토리. `uvicorn --factory src.interfaces.main:create_app` 으로 띄운다."""
    settings = settings or get_settings()
    configure_logging(settings)

    container = AppContainer(settings=settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        await container.infrastructure().database().dispose()
        await container.infrastructure().redis().aclose()
        container.infrastructure().tracer().shutdown()

    # 운영에서는 API 문서를 끈다. 관리자 API 구조까지 공개되기 때문이다.
    docs = settings.environment == "local"
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
    )
    app.state.container = container

    register_exception_handlers(app)

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=[REQUEST_ID_HEADER],
        )
    # 마지막에 등록한 미들웨어가 가장 바깥에서 돈다. CORS 거부 응답에도 request_id 가 붙는다.
    app.add_middleware(RequestContextMiddleware)

    app.include_router(health_router)
    app.include_router(v1_router, prefix=settings.api_prefix)

    # 정적 화면만 제공한다. 데이터는 superuser 인증이 걸린 /api/v1/admin 으로만 오간다.
    app.mount("/admin", StaticFiles(directory=ADMIN_UI_DIR, html=True), name="admin-ui")

    if settings.environment == "local":
        # 브라우저로 기능을 직접 확인하는 개발용 화면. 예: /playground/stt.html
        app.mount("/playground", StaticFiles(directory=PLAYGROUND_DIR), name="playground")

    return app
