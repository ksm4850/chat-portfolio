from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    """OAuth2 표준 토큰 응답.

    이 모델만 camelCase 로 바꾸지 않는다. `access_token`, `token_type` 은 OAuth2 규격이며
    Swagger UI 의 Authorize 흐름과 표준 클라이언트가 이 이름을 기대한다.
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="access_token 유효시간(초)")


class RefreshRequest(BaseModel):
    refresh_token: str
