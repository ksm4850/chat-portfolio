from dependency_injector import containers, providers

from src.infrastructure.database import Database
from src.infrastructure.security import PasswordHasher
from src.modules.users.repository import UserRepository
from src.modules.users.service import UserService


class UsersContainer(containers.DeclarativeContainer):
    """사용자 모듈 조립.

    repository 는 세션을 메서드 인자로 받는 stateless 객체라 `Singleton` 으로 둔다.
    """

    database = providers.Dependency(instance_of=Database)
    password_hasher = providers.Dependency(instance_of=PasswordHasher)

    repository = providers.Singleton(UserRepository)

    service = providers.Factory(
        UserService,
        db=database,
        repository=repository,
        password_hasher=password_hasher,
    )
