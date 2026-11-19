"""포트폴리오 안내 답변 eval. 문항은 cases.yaml, 실행은 `make eval`."""

import os

import pytest
from deepeval import assert_test, log_hyperparameters
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric

from src.core.config import get_settings
from tests.eval.conftest import Case, GuideRunner, load_cases
from tests.eval.judge import JudgeModel, judge_model_name
from tests.eval.metrics import LLMModeMetric, PhraseMetric, ScreenActionMetric

pytestmark = pytest.mark.eval

CASES = load_cases()
# LLM 채점은 문항당 judge 호출이 여러 번이라 느리다. 규칙 지표만 빠르게 볼 때 끈다.
USE_JUDGE = os.getenv("EVAL_JUDGE", "1") != "0"


@log_hyperparameters
def hyperparameters() -> dict:
    """실행 조건을 결과 JSON 에 남긴다. 기준선과 비교할 때 무엇이 달랐는지 본다."""
    settings = get_settings()
    openai = settings.llm_provider == "openai"
    return {
        "llm": settings.openai_chat_model if openai else f"claude_cli:{settings.llm_model}",
        "embedding": settings.openai_embedding_model,
        "judge": judge_model_name(settings) if USE_JUDGE else "off",
        "searchLimit": settings.guide_search_limit,
        "sourceMinScore": settings.guide_source_min_score,
        "actionMinScore": settings.guide_action_min_score,
    }


def _metrics(case: Case, judge: JudgeModel) -> list:
    expect = case.expect
    metrics = [
        ScreenActionMetric(expect.action, expect.anchors_any),
        PhraseMetric(expect.include_any, expect.exclude),
    ]
    if not expect.allow_fallback:
        metrics.append(LLMModeMetric())
    if USE_JUDGE:
        metrics += [
            AnswerRelevancyMetric(threshold=0.7, model=judge),
            FaithfulnessMetric(threshold=0.7, model=judge),
        ]
    return metrics


@pytest.mark.parametrize("case", CASES, ids=[case.id for case in CASES])
def test_guide_answer(case: Case, guide: GuideRunner, judge: JudgeModel) -> None:
    assert_test(guide.test_case(case), _metrics(case, judge))
