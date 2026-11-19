from dependency_injector import containers, providers

from src.core.config import Settings
from src.infrastructure.container import InfrastructureContainer
from src.modules.auth.container import AuthContainer
from src.modules.character.container import CharacterContainer
from src.modules.chat.container import ChatContainer
from src.modules.chat.limits import ChatLimits
from src.modules.guide.container import GuideContainer
from src.modules.guide.schema import GuideOptions
from src.modules.knowledge.container import KnowledgeContainer
from src.modules.portfolio.container import PortfolioContainer
from src.modules.users.container import UsersContainer
from src.modules.visitor.container import VisitorContainer
from src.modules.voice.container import VoiceContainer


class AppContainer(containers.DeclarativeContainer):
    """모듈 컨테이너를 조립하는 최상위 컨테이너.

    앱 수명 객체(어댑터, service, repository)는 여기서 조립한다.
    요청마다 달라지는 값(토큰, 현재 사용자)은 컨테이너가 아니라 FastAPI `Depends` 로 받는다.
    새 모듈을 추가할 때 `providers.Container` 한 줄을 더한다.
    """

    # 라우터는 각 모듈에, 공통 의존성은 interfaces 에 있으므로 두 패키지를 wiring한다.
    wiring_config = containers.WiringConfiguration(packages=["src.modules", "src.interfaces"])

    settings = providers.Dependency(instance_of=Settings)

    infrastructure = providers.Container(InfrastructureContainer, settings=settings)

    users = providers.Container(
        UsersContainer,
        database=infrastructure.database,
        password_hasher=infrastructure.password_hasher,
    )

    auth = providers.Container(
        AuthContainer,
        database=infrastructure.database,
        token_service=infrastructure.token_service,
        user_service=users.service,
    )

    character = providers.Container(CharacterContainer, database=infrastructure.database)

    knowledge = providers.Container(
        KnowledgeContainer,
        database=infrastructure.database,
        embedder=infrastructure.embedder,
        character_service=character.service,
        chunk_size=settings.provided.knowledge_chunk_size,
        chunk_overlap=settings.provided.knowledge_chunk_overlap,
    )

    visitor = providers.Container(
        VisitorContainer,
        token_service=infrastructure.token_service,
        rate_limiter=infrastructure.rate_limiter,
        tokens_per_ip_per_hour=settings.provided.visitor_tokens_per_ip_per_hour,
    )

    chat_limits = providers.Singleton(
        ChatLimits,
        message_max_length=settings.provided.chat_message_max_length,
        min_interval_seconds=settings.provided.chat_min_interval_seconds,
        messages_per_session=settings.provided.chat_messages_per_session,
        messages_per_visitor_per_day=settings.provided.chat_messages_per_visitor_per_day,
        messages_per_ip_per_hour=settings.provided.chat_messages_per_ip_per_hour,
        llm_calls_per_day=settings.provided.chat_llm_calls_per_day,
        session_ttl_seconds=settings.provided.chat_session_ttl_seconds,
    )

    chat = providers.Container(
        ChatContainer,
        llm=infrastructure.llm,
        redis=infrastructure.redis,
        rate_limiter=infrastructure.rate_limiter,
        knowledge_service=knowledge.service,
        character_service=character.service,
        limits=chat_limits,
        rag_top_k=settings.provided.rag_top_k,
        history_turns=settings.provided.chat_history_turns,
    )

    voice = providers.Container(VoiceContainer, stt=infrastructure.stt)

    portfolio = providers.Container(
        PortfolioContainer,
        database=infrastructure.database,
        knowledge_service=knowledge.service,
        character_service=character.service,
        content_dir=settings.provided.portfolio_content_dir,
        character_slug=settings.provided.guide_character_slug,
        chunk_size=settings.provided.knowledge_chunk_size,
        chunk_overlap=settings.provided.knowledge_chunk_overlap,
    )

    guide_options = providers.Singleton(
        GuideOptions,
        character_slug=settings.provided.guide_character_slug,
        llm_enabled=settings.provided.guide_llm_enabled,
        search_limit=settings.provided.guide_search_limit,
        source_min_score=settings.provided.guide_source_min_score,
        action_min_score=settings.provided.guide_action_min_score,
        history_turns=settings.provided.guide_history_turns,
        history_max_turns=settings.provided.guide_history_max_turns,
        history_answer_max_chars=settings.provided.guide_history_answer_max_chars,
    )

    guide = providers.Container(
        GuideContainer,
        database=infrastructure.database,
        redis=infrastructure.redis,
        llm=infrastructure.llm,
        tracer=infrastructure.tracer,
        knowledge_service=knowledge.service,
        portfolio_service=portfolio.service,
        character_service=character.service,
        usage_guard=chat.usage_guard,
        limits=chat_limits,
        options=guide_options,
    )
