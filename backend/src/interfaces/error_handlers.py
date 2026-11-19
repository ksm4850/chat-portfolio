"""예외 → HTTP 응답 변환.

도메인 예외는 모듈 `exceptions.py` 의 `AppError` 하위 클래스가 상태 코드와 code 를 갖고,
여기서는 `AppErrorMapper` 하나로 일괄 변환한다.
프레임워크·공통 예외는 `ErrorMapper` 를 상속한 클래스를 만들어 `MAPPERS` 에 더한다.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.core.exceptions import AppError
from src.infrastructure.logging import get_logger, request_id_var

logger = get_logger(__name__)


@dataclass(frozen=True)
class ErrorResponse:
    status_code: int
    code: str
    message: str
    details: list[dict[str, Any]] | None = None
    headers: dict[str, str] | None = None
    # 서버 오류 문의 시 로그를 찾을 수 있도록 본문에 담는다.
    request_id: str | None = None

    def to_json_response(self) -> JSONResponse:
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details is not None:
            error["details"] = self.details
        if self.request_id is not None:
            error["requestId"] = self.request_id
        return JSONResponse(
            status_code=self.status_code, content={"error": error}, headers=self.headers
        )


class ErrorMapper[E: Exception](ABC):
    """한 종류의 예외를 `ErrorResponse` 로 바꾸는 규칙."""

    exception_type: ClassVar[type[Exception]]

    @abstractmethod
    def map(self, request: Request, exc: E) -> ErrorResponse: ...


class AppErrorMapper(ErrorMapper[AppError]):
    exception_type = AppError

    def map(self, request: Request, exc: AppError) -> ErrorResponse:
        if exc.status_code >= 500:
            logger.exception("도메인 오류", exc_info=exc)
            return ErrorResponse(
                exc.status_code, exc.code, exc.message, request_id=request_id_var.get()
            )
        return ErrorResponse(exc.status_code, exc.code, exc.message, headers=exc.headers)


class RequestValidationErrorMapper(ErrorMapper[RequestValidationError]):
    """요청 검증 실패. 비밀번호 같은 입력 원문이 되돌아가지 않도록 `input`·`ctx` 는 뺀다."""

    exception_type = RequestValidationError

    def map(self, request: Request, exc: RequestValidationError) -> ErrorResponse:
        details = [
            {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        return ErrorResponse(422, "validation_error", "요청 값이 올바르지 않다.", details)


class HTTPExceptionMapper(ErrorMapper[StarletteHTTPException]):
    """라우팅 단계의 404·405 등 프레임워크가 직접 올리는 HTTP 오류."""

    exception_type = StarletteHTTPException

    _CODES: ClassVar[dict[int, str]] = {
        404: "not_found",
        405: "method_not_allowed",
    }

    def map(self, request: Request, exc: StarletteHTTPException) -> ErrorResponse:
        return ErrorResponse(
            exc.status_code,
            self._CODES.get(exc.status_code, "http_error"),
            str(exc.detail),
            headers=exc.headers,
        )


class UnexpectedErrorMapper(ErrorMapper[Exception]):
    exception_type = Exception

    def map(self, request: Request, exc: Exception) -> ErrorResponse:
        logger.exception("처리하지 못한 오류", exc_info=exc)
        return ErrorResponse(
            500, "internal_error", "서버 내부 오류가 발생했다.", request_id=request_id_var.get()
        )


MAPPERS: tuple[ErrorMapper[Any], ...] = (
    AppErrorMapper(),
    RequestValidationErrorMapper(),
    HTTPExceptionMapper(),
    UnexpectedErrorMapper(),
)


def register_exception_handlers(app: FastAPI) -> None:
    for mapper in MAPPERS:
        app.add_exception_handler(mapper.exception_type, _handler(mapper))


def _handler(mapper: ErrorMapper[Any]):
    async def handle(request: Request, exc: Exception) -> JSONResponse:
        return mapper.map(request, exc).to_json_response()

    return handle
