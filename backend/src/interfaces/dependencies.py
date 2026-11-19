"""요청 스코프 의존성.

앱 수명 객체는 DI 컨테이너가 조립하고, 요청마다 달라지는 값(토큰, 현재 사용자)은
여기에서 FastAPI `Depends` 로 받는다.
"""

import uuid
from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, Request
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer, OAuth2PasswordRequestForm

from src.core.config import Settings, get_settings
from src.core.container import AppContainer
from src.core.exceptions import TooManyRequestsError
from src.infrastructure.rate_limit import RateLimiter
from src.modules.auth.exceptions import InvalidAuthTokenError, NotEnoughPermissionError
from src.modules.auth.service import AuthService
from src.modules.users.schema import UserRead, normalize_email
from src.modules.users.service import UserService
from src.modules.visitor.service import VisitorService

# tokenUrl 은 Swagger UI 의 Authorize 흐름이 사용한다. 로그인 경로와 반드시 일치해야 한다.
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{get_settings().api_prefix.lstrip('/')}/v1/auth/login",
    auto_error=False,
)


@inject
async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    auth_service: AuthService = Depends(Provide[AppContainer.auth.service]),
) -> UserRead:
    """Authorization 헤더의 access 토큰으로 현재 사용자를 확인한다."""
    if not token:
        raise InvalidAuthTokenError("인증 토큰이 없다.")
    return await auth_service.resolve_user(token)


CurrentUser = Annotated[UserRead, Depends(get_current_user)]


async def get_current_superuser(current_user: CurrentUser) -> UserRead:
    if not current_user.is_superuser:
        raise NotEnoughPermissionError()
    return current_user


CurrentSuperUser = Annotated[UserRead, Depends(get_current_superuser)]


def get_client_ip(request: Request) -> str:
    """프록시 뒤에서는 uvicorn `--proxy-headers --forwarded-allow-ips` 를 켜야 실제 IP 가 된다.

    X-Forwarded-For 를 여기서 직접 읽지 않는다. 신뢰할 프록시를 거치지 않으면 누구나 위조할 수 있다.
    """
    return request.client.host if request.client else "unknown"


ClientIP = Annotated[str, Depends(get_client_ip)]

# Swagger 의 Authorize 에서 방문자 토큰도 넣어 볼 수 있게 보안 스킴으로 선언한다.
visitor_token_header = APIKeyHeader(name="X-Visitor-Token", auto_error=False)


@inject
async def get_current_visitor(
    token: Annotated[str | None, Depends(visitor_token_header)],
    visitor_service: VisitorService = Depends(Provide[AppContainer.visitor.service]),
) -> uuid.UUID:
    return visitor_service.resolve(token)


CurrentVisitor = Annotated[uuid.UUID, Depends(get_current_visitor)]

LoginForm = Annotated[OAuth2PasswordRequestForm, Depends()]


@inject
async def limit_login_attempts(
    request: Request,
    form: LoginForm,
    limiter: RateLimiter = Depends(Provide[AppContainer.infrastructure.rate_limiter]),
    settings: Settings = Depends(Provide[AppContainer.settings]),
) -> None:
    """로그인 시도 횟수를 IP+이메일, IP 단위로 제한한다.

    프록시 뒤에서는 uvicorn `--proxy-headers --forwarded-allow-ips` 를 켜야 실제 IP 로 센다.
    """
    client_ip = get_client_ip(request)
    window = settings.login_rate_limit_window_seconds
    checks = (
        (
            f"login:account:{client_ip}:{normalize_email(form.username)}",
            settings.login_rate_limit_per_account,
        ),
        (f"login:ip:{client_ip}", settings.login_rate_limit_per_ip),
    )
    for key, limit in checks:
        retry_after = await limiter.hit(key, limit=limit, window_seconds=window)
        if retry_after is not None:
            raise TooManyRequestsError(retry_after)


AuthServiceDep = Annotated[AuthService, Depends(Provide[AppContainer.auth.service])]
UserServiceDep = Annotated[UserService, Depends(Provide[AppContainer.users.service])]
