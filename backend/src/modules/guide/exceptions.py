from src.core.exceptions import AppError


class NoUserMessageError(AppError):
    status_code = 422
    code = "no_user_message"
    message = "user 메시지가 없다."


class UnknownTimezoneError(AppError):
    status_code = 422
    code = "unknown_timezone"
    message = "알 수 없는 시간대다."
