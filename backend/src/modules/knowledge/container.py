from dependency_injector import containers, providers

from src.infrastructure.database import Database
from src.infrastructure.embedding import Embedder
from src.modules.character.service import CharacterService
from src.modules.knowledge.repository import ChunkRepository, DocumentRepository
from src.modules.knowledge.service import KnowledgeService


class KnowledgeContainer(containers.DeclarativeContainer):
    database = providers.Dependency(instance_of=Database)
    embedder = providers.Dependency(instance_of=Embedder)
    character_service = providers.Dependency(instance_of=CharacterService)
    chunk_size = providers.Dependency(instance_of=int)
    chunk_overlap = providers.Dependency(instance_of=int)

    document_repository = providers.Singleton(DocumentRepository)
    chunk_repository = providers.Singleton(ChunkRepository)

    service = providers.Factory(
        KnowledgeService,
        db=database,
        document_repository=document_repository,
        chunk_repository=chunk_repository,
        embedder=embedder,
        character_service=character_service,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
