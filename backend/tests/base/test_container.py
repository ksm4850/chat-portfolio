"""컨테이너 조립 검증.

wiring 이 누락되면 `Provide` marker 객체가 그대로 주입되고 조용히 실패한다.
새 모듈을 추가하면 이 파일에 provider 한 줄을 더한다.
"""

import uuid

from src.core.config import Settings
from src.core.container import AppContainer
from src.infrastructure.database import Database
from src.infrastructure.embedding import Embedder, OpenAIEmbedder
from src.infrastructure.files import MediaDirectory, TextFileDirectory
from src.infrastructure.llm import ClaudeCliClient, LLMClient, OpenAIChatClient
from src.infrastructure.rate_limit import RedisRateLimiter
from src.infrastructure.security import PasswordHasher, TokenService
from src.infrastructure.speech import SpeechToText
from src.infrastructure.tracing import NoopTracer
from src.modules.auth.repository import RefreshTokenRepository
from src.modules.auth.service import AuthService
from src.modules.character.service import CharacterService
from src.modules.chat.service import ChatService
from src.modules.chat.session_store import InMemorySessionStore, RedisSessionStore
from src.modules.guide.service import GuideLogService, GuideService
from src.modules.knowledge.service import KnowledgeService
from src.modules.portfolio.service import PortfolioService
from src.modules.users.repository import UserRepository
from src.modules.users.service import UserService
from src.modules.visitor.service import VisitorService
from src.modules.voice.service import VoiceService


def _container() -> AppContainer:
    return AppContainer(settings=Settings(jwt_secret_key="test-secret-key"))


def test_infrastructure_providers_resolve() -> None:
    container = _container()

    assert isinstance(container.infrastructure().database(), Database)
    assert isinstance(container.infrastructure().password_hasher(), PasswordHasher)
    assert isinstance(container.infrastructure().token_service(), TokenService)
    assert isinstance(container.infrastructure().rate_limiter(), RedisRateLimiter)
    assert isinstance(container.infrastructure().llm(), LLMClient)
    assert isinstance(container.infrastructure().embedder(), Embedder)
    assert isinstance(container.infrastructure().stt(), SpeechToText)
    assert isinstance(container.infrastructure().tracer(), NoopTracer)


def test_providers_follow_settings() -> None:
    local = _container()
    deployed = AppContainer(
        settings=Settings(
            jwt_secret_key="test-secret-key",
            llm_provider="openai",
            openai_api_key="test-openai-key",
        )
    )

    assert isinstance(local.infrastructure().llm(), ClaudeCliClient)
    assert isinstance(local.infrastructure().embedder(), OpenAIEmbedder)
    assert isinstance(deployed.infrastructure().llm(), OpenAIChatClient)
    assert isinstance(deployed.infrastructure().embedder(), OpenAIEmbedder)
    assert deployed.guide().service()._llm is deployed.infrastructure().llm()
    assert deployed.chat().service()._llm is deployed.infrastructure().llm()
    assert deployed.knowledge().service()._embedder is deployed.infrastructure().embedder()


def test_module_providers_resolve() -> None:
    container = _container()

    assert isinstance(container.users().repository(), UserRepository)
    assert isinstance(container.users().service(), UserService)
    assert isinstance(container.auth().refresh_token_repository(), RefreshTokenRepository)
    assert isinstance(container.auth().service(), AuthService)
    assert isinstance(container.knowledge().service(), KnowledgeService)
    assert isinstance(container.character().service(), CharacterService)
    assert isinstance(container.visitor().service(), VisitorService)
    assert isinstance(container.chat().session_store(), RedisSessionStore)
    assert isinstance(container.chat().service(), ChatService)
    assert isinstance(container.voice().service(), VoiceService)
    assert isinstance(container.guide().log_service(), GuideLogService)
    assert isinstance(container.portfolio().files(), TextFileDirectory)
    assert isinstance(container.portfolio().media(), MediaDirectory)
    assert isinstance(container.portfolio().service(), PortfolioService)
    assert isinstance(container.guide().service(), GuideService)


def test_database_is_shared_singleton() -> None:
    container = _container()

    assert container.infrastructure().database() is container.infrastructure().database()


def test_repository_is_shared_singleton() -> None:
    """repository 는 세션을 인자로 받는 stateless 객체라 하나만 만든다."""
    container = _container()

    assert container.users().repository() is container.users().repository()


def test_service_is_created_per_request() -> None:
    container = _container()

    assert container.users().service() is not container.users().service()


def test_auth_service_shares_user_service_dependencies() -> None:
    """auth 모듈은 users repository 를 직접 쓰지 않고 UserService 를 통한다."""
    container = _container()
    auth_service = container.auth().service()

    assert isinstance(auth_service._user_service, UserService)
    assert auth_service._db is container.infrastructure().database()


async def test_chat_sessions_survive_across_service_instances() -> None:
    """service 는 요청마다 새로 만들지만 세션 저장소는 하나를 공유해야 대화가 이어진다."""
    container = _container()
    container.chat.session_store.override(InMemorySessionStore())
    visitor_id = uuid.uuid4()
    session_id = await container.chat().session_store().create(uuid.uuid4(), visitor_id)

    assert await container.chat().service().get_history(session_id, visitor_id) == []


def test_rate_limiter_is_shared_by_login_visitor_and_chat() -> None:
    """제한 카운터가 한 저장소에 모여야 프로세스·모듈이 같은 숫자를 본다."""
    container = _container()
    limiter = container.infrastructure().rate_limiter()

    assert container.visitor().service()._limiter is limiter
    assert container.chat().usage_guard()._limiter is limiter


def test_guide_shares_chat_usage_guard() -> None:
    """안내와 채팅이 같은 방문자·IP·전체 LLM 카운터를 쓴다."""
    container = _container()

    assert container.guide().service()._guard is container.chat().usage_guard()
