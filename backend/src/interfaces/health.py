"""배포 환경의 상태 확인용 endpoint. API 버전과 무관하므로 prefix 밖에 둔다."""

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from src.core.container import AppContainer
from src.infrastructure.database import Database
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["system"])


@router.get("/live")
async def live() -> dict[str, str]:
    """프로세스 생존 여부. 의존성을 확인하지 않는다."""
    return {"status": "ok"}


@router.get("/ready")
@inject
async def ready(
    database: Database = Depends(Provide[AppContainer.infrastructure.database]),
    redis: Redis = Depends(Provide[AppContainer.infrastructure.redis]),
) -> JSONResponse:
    """트래픽을 받을 수 있는지. DB·Redis 중 하나라도 닿지 않으면 503."""
    checks: dict[str, str] = {}
    for name, ping in (("database", database.ping), ("redis", redis.ping)):
        try:
            await ping()
            checks[name] = "ok"
        except Exception as exc:
            logger.warning("readiness 실패", extra={"check": name, "error": type(exc).__name__})
            checks[name] = "fail"

    if "fail" in checks.values():
        return JSONResponse(status_code=503, content={"status": "unavailable", "checks": checks})
    return JSONResponse(content={"status": "ok", "checks": checks})
