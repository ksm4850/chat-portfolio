from dependency_injector import containers, providers

from src.infrastructure.database import Database
from src.infrastructure.llm import LLMClient
from src.infrastructure.tracing import Tracer
from src.modules.character.service import CharacterService
from src.modules.chat.limits import ChatLimits, ChatUsageGuard
from src.modules.guide.history import RedisGuideHistory
from src.modules.guide.repository import GuideLogRepository
from src.modules.guide.schema import GuideOptions
from src.modules.guide.service import GuideLogService, GuideService
from src.modules.knowledge.service import KnowledgeService
from src.modules.portfolio.service import PortfolioService


class GuideContainer(containers.DeclarativeContainer):
    database = providers.Dependency(instance_of=Database)
    redis = providers.Dependency()
    llm = providers.Dependency(instance_of=LLMClient)
    tracer = providers.Dependency(instance_of=Tracer)
    knowledge_service = providers.Dependency(instance_of=KnowledgeService)
    portfolio_service = providers.Dependency(instance_of=PortfolioService)
    character_service = providers.Dependency(instance_of=CharacterService)
    usage_guard = providers.Dependency(instance_of=ChatUsageGuard)
    limits = providers.Dependency(instance_of=ChatLimits)
    options = providers.Dependency(instance_of=GuideOptions)

    log_repository = providers.Singleton(GuideLogRepository)
    log_service = providers.Factory(GuideLogService, db=database, repository=log_repository)

    history = providers.Singleton(
        RedisGuideHistory,
        redis=redis,
        ttl_seconds=limits.provided.session_ttl_seconds,
        max_turns=options.provided.history_max_turns,
    )

    service = providers.Factory(
        GuideService,
        llm=llm,
        knowledge_service=knowledge_service,
        portfolio_service=portfolio_service,
        character_service=character_service,
        usage_guard=usage_guard,
        limits=limits,
        options=options,
        log_service=log_service,
        history=history,
        tracer=tracer,
    )
