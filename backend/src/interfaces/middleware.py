import re
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.infrastructure.logging import get_logger, request_id_var

logger = get_logger("app.access")

REQUEST_ID_HEADER = "X-Request-ID"
# 로그 주입을 막기 위해 받은 값은 형식이 맞을 때만 그대로 쓴다.
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_SKIP_ACCESS_LOG_PREFIX = "/health"


class RequestContextMiddleware:
    """요청마다 request_id 를 정하고 응답 헤더와 접근 로그에 남긴다.

    `BaseHTTPMiddleware` 는 별도 task 에서 돌아 contextvar 가 어긋날 수 있어 순수 ASGI 로 둔다.
    contextvar 는 되돌리지 않는다. 처리하지 못한 오류의 응답은 이 미들웨어 바깥에서 만들어지는데,
    그 오류 로그와 응답에도 같은 request_id 가 남아야 한다. 요청마다 task 가 달라 새지 않는다.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _request_id_from(scope)
        request_id_var.set(request_id)
        started = time.perf_counter()
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                MutableHeaders(scope=message)[REQUEST_ID_HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            if not scope["path"].startswith(_SKIP_ACCESS_LOG_PREFIX):
                logger.info(
                    "요청 처리",
                    extra={
                        "method": scope["method"],
                        "path": scope["path"],
                        "status": status_code,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                    },
                )


def _request_id_from(scope: Scope) -> str:
    for name, value in scope["headers"]:
        if name == b"x-request-id":
            candidate = value.decode("latin-1")
            if _VALID_REQUEST_ID.match(candidate):
                return candidate
            break
    return uuid.uuid4().hex
