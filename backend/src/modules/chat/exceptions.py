from src.core.exceptions import AppError


class ChatSessionNotFoundError(AppError):
    status_code = 404
    code = "chat_session_not_found"
    message = "대화 세션을 찾을 수 없다. 새 대화를 시작한다."


class ReplyFailedError(AppError):
    status_code = 502
    code = "reply_failed"
    message = "응답을 생성하지 못했다."


class MessageTooLongError(AppError):
    status_code = 422
    code = "message_too_long"

    def __init__(self, max_length: int) -> None:
        super().__init__(f"메시지는 {max_length}자까지 보낼 수 있다.")


class ChatLimitExceededError(AppError):
    """사용량 제한. 위젯이 code 로 안내 문구를 고른다."""

    status_code = 429

    def __init__(self, code: str, message: str, retry_after: int | None) -> None:
        super().__init__(message)
        self.code = code
        if retry_after is not None:
            self.headers = {"Retry-After": str(retry_after)}
