from dependency_injector import containers, providers

from src.core.config import Settings
from src.infrastructure.database import Database
from src.infrastructure.embedding import EMBEDDING_DIMENSIONS, OpenAIEmbedder
from src.infrastructure.llm import ClaudeCliClient, OpenAIChatClient
from src.infrastructure.rate_limit import RedisRateLimiter
from src.infrastructure.redis import create_redis
from src.infrastructure.security import PasswordHasher, TokenService
from src.infrastructure.speech import DeepgramSpeechToText
from src.infrastructure.tracing import create_tracer


class InfrastructureContainer(containers.DeclarativeContainer):
    """기술 어댑터 조립. 도메인 지식은 넣지 않는다."""

    settings = providers.Dependency(instance_of=Settings)

    database = providers.Singleton(
        Database,
        url=settings.provided.database_url,
        echo=settings.provided.database_echo,
        pool_size=settings.provided.database_pool_size,
        max_overflow=settings.provided.database_max_overflow,
        pool_recycle=settings.provided.database_pool_recycle,
        pool_pre_ping=settings.provided.database_pool_pre_ping,
        statement_timeout_ms=settings.provided.database_statement_timeout_ms,
        connect_timeout=settings.provided.database_connect_timeout,
    )

    password_hasher = providers.Singleton(PasswordHasher)

    redis = providers.Singleton(create_redis, url=settings.provided.redis_url)

    rate_limiter = providers.Singleton(RedisRateLimiter, redis=redis)

    token_service = providers.Singleton(
        TokenService,
        secret_key=settings.provided.jwt_secret_key.get_secret_value.call(),
        algorithm=settings.provided.jwt_algorithm,
        access_token_expire_minutes=settings.provided.access_token_expire_minutes,
        refresh_token_expire_days=settings.provided.refresh_token_expire_days,
        visitor_token_expire_days=settings.provided.visitor_token_expire_days,
    )

    llm = providers.Selector(
        settings.provided.llm_provider,
        claude_cli=providers.Singleton(
            ClaudeCliClient,
            cli_path=settings.provided.llm_cli_path,
            model=settings.provided.llm_model,
            timeout_seconds=settings.provided.llm_timeout_seconds,
        ),
        openai=providers.Singleton(
            OpenAIChatClient,
            api_key=settings.provided.openai_api_key.get_secret_value.call(),
            model=settings.provided.openai_chat_model,
            max_output_tokens=settings.provided.llm_max_output_tokens,
            timeout_seconds=settings.provided.llm_timeout_seconds,
        ),
    )

    embedder = providers.Singleton(
        OpenAIEmbedder,
        api_key=settings.provided.openai_api_key.get_secret_value.call(),
        model=settings.provided.openai_embedding_model,
        dimensions=EMBEDDING_DIMENSIONS,
        timeout_seconds=settings.provided.embedding_timeout_seconds,
    )

    stt = providers.Singleton(
        DeepgramSpeechToText,
        api_key=settings.provided.deepgram_api_key.get_secret_value.call(),
        model=settings.provided.stt_model,
        language=settings.provided.stt_language,
    )

    tracer = providers.Singleton(
        create_tracer,
        public_key=settings.provided.langfuse_public_key,
        secret_key=settings.provided.langfuse_secret_key.get_secret_value.call(),
        base_url=settings.provided.langfuse_base_url,
        environment=settings.provided.environment,
    )
