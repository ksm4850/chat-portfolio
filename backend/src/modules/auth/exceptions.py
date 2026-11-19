from src.core.exceptions import AppError


class InvalidCredentialsError(AppError):
    status_code = 401
    code = "invalid_credentials"
    message = "이메일 또는 비밀번호가 올바르지 않다."


class InvalidAuthTokenError(AppError):
    status_code = 401
    code = "invalid_token"
    message = "토큰이 유효하지 않다."


class InactiveUserError(AppError):
    status_code = 403
    code = "inactive_user"
    message = "비활성화된 계정이다."


class NotEnoughPermissionError(AppError):
    status_code = 403
    code = "not_enough_permission"
    message = "권한이 부족하다."
