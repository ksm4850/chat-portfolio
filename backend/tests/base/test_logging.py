import json
import logging

import pytest

from src.core.config import Settings
from src.infrastructure.logging import configure_logging, get_logger, request_id_var


@pytest.fixture(autouse=True)
def restore_logging():
    yield
    logging.getLogger().handlers.clear()


# 운영 환경 검증을 통과하는 테스트용 값. 실제 비밀값이 아니다.
_SAFE = {
    "jwt_secret_key": "test-secret-key-that-is-at-least-32-bytes",
    "database_url": "postgresql+asyncpg://test:test@localhost:5432/test",
    "llm_provider": "openai",
    "openai_api_key": "test-openai-key",
}


def _configure(capsys, **overrides) -> logging.Logger:
    settings = Settings(_env_file=None, **{**_SAFE, **overrides})
    configure_logging(settings)
    capsys.readouterr()
    return get_logger("test.logger")


def test_local_uses_text_format(capsys) -> None:
    logger = _configure(capsys, environment="local")
    logger.info("사람이 읽는 줄")

    out = capsys.readouterr().out
    assert "[test.logger]" in out
    assert "사람이 읽는 줄" in out


def test_non_local_uses_json_format(capsys) -> None:
    logger = _configure(capsys, environment="prod")
    logger.info("저장 완료 count=%d", 3)

    record = json.loads(capsys.readouterr().out.strip())
    assert record["level"] == "INFO"
    assert record["logger"] == "test.logger"
    assert record["message"] == "저장 완료 count=3"
    assert "timestamp" in record


def test_text_format_keeps_extra_fields(capsys) -> None:
    logger = _configure(capsys, environment="local")
    logger.info("이벤트 저장", extra={"stored_count": 2, "user_id": "abc"})

    out = capsys.readouterr().out
    assert "이벤트 저장 stored_count=2 user_id=abc" in out


def test_json_format_keeps_extra_fields(capsys) -> None:
    logger = _configure(capsys, environment="prod")
    logger.info("이벤트 저장", extra={"stored_count": 2, "user_id": "abc"})

    record = json.loads(capsys.readouterr().out.strip())
    assert record["extra"] == {"stored_count": 2, "user_id": "abc"}


def test_json_format_records_exception(capsys) -> None:
    logger = _configure(capsys, environment="prod")
    try:
        raise ValueError("실패")
    except ValueError:
        logger.exception("처리 실패")

    record = json.loads(capsys.readouterr().out.strip())
    assert "ValueError: 실패" in record["exception"]


def test_log_format_override_beats_environment(capsys) -> None:
    logger = _configure(capsys, environment="local", log_format="json")
    logger.info("강제 json")

    assert json.loads(capsys.readouterr().out.strip())["message"] == "강제 json"


def test_uvicorn_logger_uses_root_handler(capsys) -> None:
    _configure(capsys, environment="prod")
    logging.getLogger("uvicorn.error").warning("서버 경고")

    record = json.loads(capsys.readouterr().out.strip())
    assert record["logger"] == "uvicorn.error"
    assert record["message"] == "서버 경고"


def test_sql_logger_is_quiet_unless_echo_enabled(capsys) -> None:
    _configure(capsys, environment="prod", database_echo=False)
    logging.getLogger("sqlalchemy.engine").info("SELECT 1")

    assert capsys.readouterr().out == ""


def test_request_id_is_attached_to_logs(capsys) -> None:
    logger = _configure(capsys, environment="prod")
    token = request_id_var.set("req-123")
    try:
        logger.info("요청 중 로그")
    finally:
        request_id_var.reset(token)

    record = json.loads(capsys.readouterr().out.strip())
    assert record["extra"]["request_id"] == "req-123"
