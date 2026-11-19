from dependency_injector import containers, providers

from src.infrastructure.database import Database
from src.infrastructure.security import TokenService
from src.modules.auth.repository import RefreshTokenRepository
from src.modules.auth.service import AuthService
from src.modules.users.service import UserService


class AuthContainer(containers.DeclarativeContainer):
    """인증 모듈 조립. 사용자 조회는 `UserService` 를 통한다."""

    database = providers.Dependency(instance_of=Database)
    token_service = providers.Dependency(instance_of=TokenService)
    user_service = providers.Dependency(instance_of=UserService)

    refresh_token_repository = providers.Singleton(RefreshTokenRepository)

    service = providers.Factory(
        AuthService,
        db=database,
        user_service=user_service,
        refresh_token_repository=refresh_token_repository,
        token_service=token_service,
    )
