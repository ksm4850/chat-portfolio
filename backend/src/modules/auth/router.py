from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, status

from src.core.container import AppContainer
from src.interfaces.dependencies import LoginForm, limit_login_attempts
from src.modules.auth.schema import RefreshRequest, TokenResponse
from src.modules.auth.service import AuthService

router = APIRouter(tags=["auth"])


@router.post("/login", status_code=status.HTTP_200_OK, dependencies=[Depends(limit_login_attempts)])
@inject
async def login(
    form: LoginForm,
    service: AuthService = Depends(Provide[AppContainer.auth.service]),
) -> TokenResponse:
    """OAuth2 password flow 로그인.

    `username` 필드에 이메일을 넣어 보낸다. OAuth2 규격의 필드 이름이라 바꾸지 않는다.
    """
    return await service.login(email=form.username, password=form.password)


@router.post("/refresh", status_code=status.HTTP_200_OK)
@inject
async def refresh(
    payload: RefreshRequest,
    service: AuthService = Depends(Provide[AppContainer.auth.service]),
) -> TokenResponse:
    """refresh 토큰으로 새 토큰 쌍을 받는다. 사용한 refresh 토큰은 폐기된다."""
    return await service.refresh(payload.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def logout(
    payload: RefreshRequest,
    service: AuthService = Depends(Provide[AppContainer.auth.service]),
) -> None:
    """refresh 토큰이 속한 로그인 세션 전체를 폐기한다."""
    await service.logout(payload.refresh_token)
