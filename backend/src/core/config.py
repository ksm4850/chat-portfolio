import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_JWT_SECRET = "change-me-in-env"


class Settings(BaseSettings):
    """환경변수와 env 파일에서 읽는 실행 설정.

    클래스는 env 파일을 읽지 않는다. 앱·CLI·마이그레이션은 `get_settings()` 가 고른 파일을 읽고,
    테스트에서 직접 만드는 `Settings(...)` 는 로컬 파일 값에 영향받지 않는다.
    비밀값은 `SecretStr` 로 선언해 로그와 오류 메시지에 원문이 찍히지 않게 한다.
    """

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
        # 검증 오류 메시지에 비밀값 원문이 찍히지 않게 한다.
        hide_input_in_errors=True,
    )

    app_name: str = "voice-clone-chat"
    environment: Literal["local", "dev", "prod"] = "local"
    log_level: str = "INFO"
    # auto = local 이면 text, 그 밖에는 json
    log_format: Literal["auto", "text", "json"] = "auto"
    api_prefix: str = "/api"

    database_url: str = "postgresql+asyncpg://app:changeme@localhost:5433/app"
    database_echo: bool = False
    database_pool_size: int = 5
    database_max_overflow: int = 10
    # 장시간 유휴 후 끊긴 커넥션을 재사용하지 않도록 주기적으로 폐기한다.
    database_pool_recycle: int = 1800
    database_pool_pre_ping: bool = True
    # 느린 쿼리·락 대기가 커넥션을 오래 붙잡아 풀이 고갈되지 않게 서버 쪽에서 끊는다.
    database_statement_timeout_ms: int = 30_000
    database_connect_timeout: float = 5.0

    jwt_secret_key: SecretStr = SecretStr(_DEFAULT_JWT_SECRET)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14

    # 비어 있으면 CORS 를 켜지 않는다. 예: CORS_ORIGINS=["https://app.example.com"]
    cors_origins: list[str] = []

    # 로그인 시도 제한. IP+이메일 조합은 한 계정 대입을, IP 전체는 여러 계정 대입을 막는다.
    login_rate_limit_per_account: int = 5
    login_rate_limit_per_ip: int = 30
    login_rate_limit_window_seconds: int = 60

    redis_url: str = "redis://localhost:6380/0"

    # claude_cli 는 개인 구독을 쓰므로 local 에서만 허용한다.
    llm_provider: Literal["claude_cli", "openai"] = "claude_cli"
    llm_cli_path: str = "claude"
    llm_model: str = "haiku"
    llm_timeout_seconds: float = 120.0
    # 한 번 응답의 최대 토큰. 비용 상한이기도 하다.
    llm_max_output_tokens: int = 1000

    openai_api_key: SecretStr = SecretStr("")
    openai_chat_model: str = "gpt-6.1-terra"
    openai_embedding_model: str = "text-embedding-3-small"

    embedding_timeout_seconds: float = 30.0
    knowledge_chunk_size: int = 500
    knowledge_chunk_overlap: int = 100
    rag_top_k: int = 4

    # LLM 추적(Langfuse). 키가 비어 있으면 아무것도 보내지 않는다. 호스트는 리전별 주소.
    langfuse_public_key: str = ""
    langfuse_secret_key: SecretStr = SecretStr("")
    langfuse_base_url: str = Field(
        default="", validation_alias=AliasChoices("LANGFUSE_BASE_URL", "LANGFUSE_HOST")
    )

    # 비어 있으면 STT 요청이 speech_not_configured 로 실패한다.
    deepgram_api_key: SecretStr = SecretStr("")
    stt_model: str = "nova-3"
    stt_language: str = "ko"

    # 한 턴 = 사용자 발화 + 응답. 이보다 오래된 대화는 프롬프트에 넣지도, 보관하지도 않는다.
    chat_history_turns: int = 10
    # 마지막 대화 뒤 이 시간이 지나면 세션(최근 대화)이 Redis 에서 사라진다.
    chat_session_ttl_seconds: int = 86_400

    # 익명 방문자 토큰. 시크릿 창으로 새로 받는 우회는 IP 당 발급 수로 막는다.
    visitor_token_expire_days: int = 30
    visitor_tokens_per_ip_per_hour: int = 10

    # 사용량 제한. 테스트하며 조정한다.
    chat_message_max_length: int = 500
    chat_min_interval_seconds: int = 2
    chat_messages_per_session: int = 20
    chat_messages_per_visitor_per_day: int = 50
    chat_messages_per_ip_per_hour: int = 60
    # 전체 방문자 합계. 비용 상한이다.
    chat_llm_calls_per_day: int = 500

    # 포트폴리오 원본(projects.json + md). 관리자 화면에서 md 를 고치면 이 디렉터리에 쓴다.
    portfolio_content_dir: Path = Path("../content/portfolio")

    # 포트폴리오 안내(AG-UI). 수집한 포트폴리오 문서를 이 캐릭터의 기억으로 넣고,
    # 안내도 이 캐릭터로 답한다.
    guide_character_slug: str = "me"
    # False 면 LLM 없이 검색 결과로만 답한다(폴백).
    guide_llm_enabled: bool = True
    guide_search_limit: int = 6
    # 코사인 유사도 기준(OpenAI 임베딩). sources 에 넣는 최소 점수 < 폴백이 화면을 여는 최소 점수.
    # 정답 섹션 0.38~0.67, 범위 밖 질문 0.18~0.39 로 측정했다(tests/eval/cases.yaml).
    guide_source_min_score: float = 0.30
    guide_action_min_score: float = 0.45
    # 대화 맥락. 최근 history_max_turns 턴을 보관하고, 그중 최근 history_turns 턴은 질문·답변으로,
    # 나머지는 질문만 넣는다. 답변은 history_answer_max_chars 에서 자른다.
    # 보관 기간은 CHAT_SESSION_TTL_SECONDS 를 따른다.
    guide_history_turns: int = 3
    guide_history_max_turns: int = 8
    guide_history_answer_max_chars: int = 400

    @model_validator(mode="after")
    def _reject_unsafe_production_values(self) -> Settings:
        if self.environment == "local":
            return self

        problems = []
        secret = self.jwt_secret_key.get_secret_value()
        if secret == _DEFAULT_JWT_SECRET or len(secret.encode()) < 32:
            problems.append("JWT_SECRET_KEY 는 기본값이 아닌 32바이트 이상이어야 한다")
        if ":changeme@" in self.database_url:
            problems.append("DATABASE_URL 에 기본 비밀번호가 들어 있다")
        if self.database_echo:
            problems.append("DATABASE_ECHO 는 local 에서만 켤 수 있다")
        if self.llm_provider == "claude_cli":
            problems.append("LLM_PROVIDER=claude_cli 는 개인 구독이라 local 에서만 쓸 수 있다")
        if not self.openai_api_key.get_secret_value():
            problems.append("OPENAI_API_KEY 가 필요하다(임베딩은 항상 OpenAI)")

        if problems:
            raise ValueError(f"{self.environment} 환경 설정 오류: " + "; ".join(problems))
        return self

    @property
    def debug(self) -> bool:
        return self.environment == "local"


def env_file() -> str | None:
    """`ENV_FILE` 로 지정하거나, 로컬 `.env.local` 이 있으면 그것만, 없으면 `.env.prod` 만 읽는다.

    두 파일을 겹쳐 읽지 않는다. 로컬 파일에 빠진 값을 운영 값(DB 주소 등)으로 채우지 않기 위해서다.
    """
    if (chosen := os.environ.get("ENV_FILE")) is not None:
        return chosen or None
    return ".env.local" if Path(".env.local").exists() else ".env.prod"


@lru_cache
def get_settings() -> Settings:
    return Settings(_env_file=env_file())
