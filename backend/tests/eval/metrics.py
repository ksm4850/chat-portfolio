"""안내 화면 규칙을 보는 커스텀 지표. LLM 채점 없이 결정적으로 판정한다(점수 1 또는 0)."""

from fnmatch import fnmatch
from typing import Literal

from deepeval.metrics import BaseMetric
from deepeval.test_case import LLMTestCase

# 방문자는 이미 포트폴리오 화면을 보고 있다. 외부 링크로 내보내지 않는다.
EXTERNAL_LINKS = ("http://", "https://", "github.io")


class _RuleMetric(BaseMetric):
    """`check` 가 실패 사유를 돌려주면 0점, None 이면 1점."""

    name = "Rule"

    def __init__(self) -> None:
        self.threshold = 1.0
        self.async_mode = False
        self.include_reason = True

    def check(self, test_case: LLMTestCase) -> str | None:
        raise NotImplementedError

    def measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        problem = self.check(test_case)
        self.score = 0.0 if problem else 1.0
        self.reason = problem or "통과"
        self.success = self.score >= self.threshold
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args, **kwargs) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return bool(self.success)

    @property
    def __name__(self) -> str:
        return self.name


def highlighted(test_case: LLMTestCase) -> list[str]:
    return [
        (tool.input_parameters or {})["anchor"]
        for tool in test_case.tools_called or []
        if tool.name == "highlight"
    ]


class LLMModeMetric(_RuleMetric):
    """폴백 없이 LLM 이 답했는가. 폴백은 LLM 실패·한도 초과 신호다."""

    name = "LLM Mode"

    def check(self, test_case: LLMTestCase) -> str | None:
        mode = (test_case.metadata or {}).get("mode")
        return None if mode == "llm" else f"mode={mode}"


class ScreenActionMetric(_RuleMetric):
    """화면 액션(navigate/highlight) 유무와, 기대한 섹션(anchor glob)을 강조했는지."""

    name = "Screen Action"

    def __init__(
        self, action: Literal["required", "optional", "forbidden"], anchors_any: list[str]
    ) -> None:
        super().__init__()
        self.action = action
        self.anchors_any = anchors_any

    def check(self, test_case: LLMTestCase) -> str | None:
        acted = bool(test_case.tools_called)
        anchors = highlighted(test_case)
        if self.action == "required" and not acted:
            return "화면 액션이 없다"
        if self.action == "forbidden" and acted:
            return f"액션이 없어야 하는데 강조했다: {anchors}"
        if self.anchors_any and not any(
            fnmatch(anchor, pattern) for anchor in anchors for pattern in self.anchors_any
        ):
            return f"기대 섹션 {self.anchors_any} 를 강조하지 않았다. 강조: {anchors or '없음'}"
        return None


class PhraseMetric(_RuleMetric):
    """답변에 들어가야 할 문구 중 하나가 있는지, 금지 문구(외부 링크 포함)가 없는지."""

    name = "Phrase"

    def __init__(self, include_any: list[str], exclude: list[str]) -> None:
        super().__init__()
        self.include_any = include_any
        self.exclude = [*EXTERNAL_LINKS, *exclude]

    def check(self, test_case: LLMTestCase) -> str | None:
        text = test_case.actual_output or ""
        banned = [word for word in self.exclude if word in text]
        if banned:
            return f"금지 문구: {banned}"
        if self.include_any and not any(word in text for word in self.include_any):
            return f"다음 중 하나가 없다: {self.include_any}"
        return None
