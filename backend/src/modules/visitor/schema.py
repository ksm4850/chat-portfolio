from datetime import datetime

from src.shared.schema import CamelModel


class VisitorToken(CamelModel):
    """브라우저 localStorage 에 두고 요청마다 `X-Visitor-Token` 헤더로 보낸다."""

    visitor_token: str
    expires_at: datetime
