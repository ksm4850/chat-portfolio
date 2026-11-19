from dependency_injector import containers, providers

from src.infrastructure.llm import LLMClient
from src.infrastructure.rate_limit import RateLimiter
from src.modules.character.service import CharacterService
from src.modules.chat.limits import ChatLimits, ChatUsageGuard
from src.modules.chat.service import ChatService
from src.modules.chat.session_store import RedisSessionStore
from src.modules.knowledge.service import KnowledgeService


class ChatContainer(containers.DeclarativeContainer):
    llm = providers.Dependency(instance_of=LLMClient)
    redis = providers.Dependency()
    rate_limiter = providers.Dependency(instance_of=RateLimiter)
    knowledge_service = providers.Dependency(instance_of=KnowledgeService)
    character_service = providers.Dependency(instance_of=CharacterService)
    limits = providers.Dependency(instance_of=ChatLimits)
    rag_top_k = providers.Dependency(instance_of=int)
    history_turns = providers.Dependency(instance_of=int)

    session_store = providers.Singleton(
        RedisSessionStore,
        redis=redis,
        ttl_seconds=limits.provided.session_ttl_seconds,
        max_turns=history_turns,
    )

    usage_guard = providers.Singleton(ChatUsageGuard, rate_limiter=rate_limiter, limits=limits)

    service = providers.Factory(
        ChatService,
        llm=llm,
        knowledge_service=knowledge_service,
        character_service=character_service,
        session_store=session_store,
        usage_guard=usage_guard,
        limits=limits,
        rag_top_k=rag_top_k,
        history_turns=history_turns,
    )
