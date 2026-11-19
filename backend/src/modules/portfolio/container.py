from pathlib import Path

from dependency_injector import containers, providers

from src.infrastructure.database import Database
from src.infrastructure.files import MediaDirectory, TextFileDirectory
from src.modules.character.service import CharacterService
from src.modules.knowledge.service import KnowledgeService
from src.modules.portfolio.repository import CatalogRepository, SectionRepository
from src.modules.portfolio.service import MEDIA_DIR, MEDIA_EXTENSIONS, PortfolioService


class PortfolioContainer(containers.DeclarativeContainer):
    database = providers.Dependency(instance_of=Database)
    knowledge_service = providers.Dependency(instance_of=KnowledgeService)
    character_service = providers.Dependency(instance_of=CharacterService)
    content_dir = providers.Dependency(instance_of=Path)
    character_slug = providers.Dependency(instance_of=str)
    chunk_size = providers.Dependency(instance_of=int)
    chunk_overlap = providers.Dependency(instance_of=int)

    catalog_repository = providers.Singleton(CatalogRepository)
    section_repository = providers.Singleton(SectionRepository)
    files = providers.Singleton(TextFileDirectory, root=content_dir)
    media = providers.Singleton(
        MediaDirectory,
        root=content_dir.provided.joinpath.call(MEDIA_DIR),
        extensions=MEDIA_EXTENSIONS,
    )

    service = providers.Factory(
        PortfolioService,
        db=database,
        catalog_repository=catalog_repository,
        section_repository=section_repository,
        knowledge_service=knowledge_service,
        character_service=character_service,
        files=files,
        media=media,
        character_slug=character_slug,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
