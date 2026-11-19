from src.core.exceptions import AppError


class UserNotFoundError(AppError):
    status_code = 404
    code = "user_not_found"
    message = "사용자를 찾을 수 없다."


class EmailAlreadyExistsError(AppError):
    status_code = 409
    code = "email_already_exists"
    message = "이미 사용 중인 이메일이다."


class InvalidCurrentPasswordError(AppError):
    status_code = 400
    code = "invalid_current_password"
    message = "현재 비밀번호가 일치하지 않는다."
