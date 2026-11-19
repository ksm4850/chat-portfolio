"""로깅 어댑터.

앱 코드는 `get_logger(__name__)`만 사용하고, 포맷과 출력 위치는 이 파일이 정한다.
비밀번호, 토큰, 이메일 원문은 로그에 남기지 않는다. 필요하면 user_id 나 이메일 도메인만 남긴다.
"""

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from logging.config import dictConfig
from typing import Any

from src.core.config import Settings

_TEXT_FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"

# 진입점(HTTP 미들웨어 등)이 설정하면 그 흐름의 모든 로그에 request_id 가 붙는다.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# LogRecord 가 기본으로 갖는 속성. 이 밖의 값만 extra 로 취급한다.
_STANDARD_ATTRS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)


def _extras(record: logging.LogRecord) -> dict[str, Any]:
    return {key: value for key, value in record.__dict__.items() if key not in _STANDARD_ATTRS}


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        request_id = request_id_var.get()
        if request_id is not None and not hasattr(record, "request_id"):
            record.request_id = request_id
        return True


class TextFormatter(logging.Formatter):
    """사람이 읽는 포맷. `extra`로 넘긴 값은 `key=value`로 뒤에 붙인다."""

    def __init__(self) -> None:
        super().__init__(_TEXT_FORMAT)

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        extras = _extras(record)
        if extras:
            line += " " + " ".join(f"{key}={value}" for key, value in extras.items())
        return line


class JsonFormatter(logging.Formatter):
    """로그 수집기가 그대로 읽을 수 있는 한 줄 JSON 포맷."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        extras = _extras(record)
        if extras:
            payload["extra"] = extras

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def _resolve_format(settings: Settings) -> str:
    if settings.log_format != "auto":
        return settings.log_format
    return "text" if settings.environment == "local" else "json"


def configure_logging(settings: Settings) -> None:
    """앱 시작 시 한 번 호출한다.

    uvicorn 이 자기 핸들러를 따로 붙이지 않도록 propagate 만 켜서 root 핸들러로 모은다.
    """
    formatter = _resolve_format(settings)
    level = settings.log_level.upper()

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "text": {"()": f"{__name__}.TextFormatter"},
                "json": {"()": f"{__name__}.JsonFormatter"},
            },
            "filters": {"request_id": {"()": f"{__name__}.RequestIdFilter"}},
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "stream": sys.stdout,
                    "formatter": formatter,
                    "filters": ["request_id"],
                }
            },
            "root": {"level": level, "handlers": ["console"]},
            "loggers": {
                # uvicorn 계열은 자기 핸들러를 비우고 root 로 넘긴다.
                "uvicorn": {"handlers": [], "propagate": True, "level": level},
                "uvicorn.error": {"handlers": [], "propagate": True, "level": level},
                # 접근 로그는 RequestContextMiddleware 가 request_id 와 함께 남긴다.
                "uvicorn.access": {"handlers": [], "propagate": False, "level": "WARNING"},
                # SQL 원문은 database_echo 를 켠 경우에만 남긴다.
                "sqlalchemy.engine": {
                    "handlers": [],
                    "propagate": True,
                    "level": "INFO" if settings.database_echo else "WARNING",
                },
            },
        }
    )


def get_logger(name: str | None = None) -> logging.Logger:
    """모듈 로거를 돌려준다. 호출부는 `get_logger(__name__)` 형태로 쓴다."""
    return logging.getLogger(name or "app")
