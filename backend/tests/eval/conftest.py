"""안내 답변 eval 공용 준비. 실제 DB·검색·LLM 으로 답을 만들고 DeepEval 로 채점한다.

방문자 사용량 제한과 일일 LLM 한도는 거치지 않는다. 실행 방법은 `make eval`.
"""

import asyncio
import os
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Literal

import pytest
import yaml
from deepeval.test_case import LLMTestCase, ToolCall
from dependency_injector import providers
from pydantic import BaseModel, Field

from src.core.config import get_settings
from src.core.container import AppContainer
from src.infrastructure.tracing import NoopTracer
from src.modules.chat.limits import ChatUsageGuard
from src.modules.guide.schema import GuideLogCreate, ModeChanged, TextDelta, ToolCalled
from src.modules.guide.service import GuideLogService, relevant_hits
from tests.eval.judge import JudgeModel, judge_client

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "1")

CASES_FILE = Path(__file__).with_name("cases.yaml")


class Expect(BaseModel):
    action: Literal["required", "optional", "forbidden"] = "optional"
    anchors_any: list[str] = Field(default_factory=list)
    include_any: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)
    allow_fallback: bool = False


class Case(BaseModel):
    id: str
    question: str
    tags: list[str] = Field(default_factory=list)
    expect: Expect = Field(default_factory=Expect)


def load_cases() -> list[Case]:
    data = yaml.safe_load(CASES_FILE.read_text(encoding="utf-8"))
    return [Case.model_validate(case) for case in data["cases"]]


class _UnlimitedGuard(ChatUsageGuard):
    def __init__(self) -> None:
        pass

    async def check_visitor(self, visitor_id: uuid.UUID, client_ip: str) -> None:
        return None

    async def try_llm_call(self) -> bool:
        return True


class _NoLogs(GuideLogService):
    """eval run 이 관리자 대화 기록에 섞이지 않게 한다."""

    def __init__(self) -> None:
        pass

    async def record(self, entry: GuideLogCreate) -> None:
        return None


class GuideRunner:
    """앱과 같은 조립으로 안내 run 을 돌려 DeepEval 테스트 케이스로 바꾼다.

    DB 커넥션 풀이 한 이벤트 루프에 묶이므로 모든 비동기 호출을 같은 루프에서 돌린다.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self._loop = asyncio.Runner()
        self._container = AppContainer(settings=self.settings)
        self._container.chat.usage_guard.override(providers.Object(_UnlimitedGuard()))
        self._container.guide.log_service.override(providers.Object(_NoLogs()))
        self._container.infrastructure.tracer.override(providers.Object(NoopTracer()))
        self._character = self._loop.run(
            self._container.character.service().get_by_slug(self.settings.guide_character_slug)
        )

    def close(self) -> None:
        self._loop.run(self._container.infrastructure().database().dispose())
        self._loop.run(self._container.infrastructure().redis().aclose())
        self._loop.close()

    def test_case(self, case: Case) -> LLMTestCase:
        return self._loop.run(self._test_case(case))

    async def _test_case(self, case: Case) -> LLMTestCase:
        context = await self._retrieval_context(case.question)
        mode, text, tools = None, "", []
        started = time.perf_counter()
        first_token_ms = None
        events = await self._container.guide.service().start(
            uuid.uuid4(), "127.0.0.1", case.question, None
        )
        async for event in events:
            if isinstance(event, ModeChanged):
                mode = event.mode
            elif isinstance(event, TextDelta):
                first_token_ms = first_token_ms or round((time.perf_counter() - started) * 1000)
                text += event.text
            elif isinstance(event, ToolCalled):
                tools.append(ToolCall(name=event.name, input_parameters=event.args))
        return LLMTestCase(
            input=case.question,
            actual_output=text,
            retrieval_context=context,
            tools_called=tools,
            completion_time=time.perf_counter() - started,
            metadata={"caseId": case.id, "mode": mode, "firstTokenMs": first_token_ms},
        )

    async def _retrieval_context(self, question: str) -> list[str]:
        """LLM 이 받은 근거와 같게 만든다: 캐릭터 프로필 + 기준 점수 이상 검색 결과."""
        hits = await self._container.knowledge.service().search(
            self._character.id, question, limit=self.settings.guide_search_limit
        )
        relevant = relevant_hits(
            hits,
            min_score=self.settings.guide_source_min_score,
            max_gap=self.settings.guide_source_max_gap,
        )
        materials = [f"[{hit.title}] {hit.content}" for hit in relevant]
        return [f"[프로필] {self._character.profile}", *materials]


@pytest.fixture(scope="session")
def guide() -> Iterator[GuideRunner]:
    runner = GuideRunner()
    yield runner
    runner.close()


@pytest.fixture(scope="session")
def judge(guide: GuideRunner) -> JudgeModel:
    client, name = judge_client(guide.settings)
    return JudgeModel(client, name)
