from src.core.exceptions import AppError


class InvalidVisitorTokenError(AppError):
    status_code = 401
    code = "invalid_visitor_token"
    message = "방문자 토큰이 없거나 유효하지 않다. POST /visitors 로 새로 받는다."
