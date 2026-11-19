from dependency_injector import containers, providers

from src.infrastructure.database import Database
from src.modules.character.repository import CharacterRepository
from src.modules.character.service import CharacterService


class CharacterContainer(containers.DeclarativeContainer):
    database = providers.Dependency(instance_of=Database)

    repository = providers.Singleton(CharacterRepository)

    service = providers.Factory(CharacterService, db=database, repository=repository)
