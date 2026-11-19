class AppError(Exception):
    """모든 도메인 예외의 최상위 타입.

    각 모듈의 `exceptions.py`는 이 클래스를 상속해 자기 도메인 예외를 정의한다.
    HTTP 상태 코드 변환은 `interfaces/error_handlers.py`가 담당한다.
    """

    status_code: int = 500
    code: str = "internal_error"
    message: str = "서버 내부 오류가 발생했다."
    headers: dict[str, str] | None = None

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
        if message:
            self.message = message


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    message = "요청한 자원을 찾을 수 없다."


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"
    message = "요청 값이 올바르지 않다."


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"
    message = "인증에 실패했다."


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    message = "현재 상태와 충돌하는 요청이다."


class TooManyRequestsError(AppError):
    status_code = 429
    code = "too_many_requests"
    message = "요청이 너무 많다. 잠시 후 다시 시도한다."

    def __init__(self, retry_after: int) -> None:
        super().__init__()
        self.headers = {"Retry-After": str(retry_after)}
