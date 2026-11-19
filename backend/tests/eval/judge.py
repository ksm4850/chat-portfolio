"""DeepEval 지표가 채점에 쓰는 LLM(judge). 앱의 LLM 어댑터를 그대로 감싼다.

로컬은 claude 구독(`claude -p`), 배포 설정이면 OpenAI 를 쓴다. 모델은 `EVAL_JUDGE_MODEL` 로 바꾼다.
답변 모델보다 한 단계 높은 모델로 채점해야 자기 답을 후하게 보는 편향이 줄어든다.
"""

import asyncio
import json
import os

from deepeval.models import DeepEvalBaseLLM
from pydantic import BaseModel, ValidationError

from src.core.config import Settings
from src.infrastructure.llm import ChatMessage, ClaudeCliClient, LLMClient, OpenAIChatClient

_SYSTEM = "너는 LLM 답변을 채점하는 평가자다. 지시를 따르고, JSON 을 요구하면 JSON 만 출력한다."
_SCHEMA_RULE = "출력은 다음 JSON 스키마를 따르는 JSON 객체 하나다. 코드 블록 없이 쓴다."
_JUDGE_MAX_OUTPUT_TOKENS = 2000


def judge_model_name(settings: Settings) -> str:
    default = "sonnet" if settings.llm_provider == "claude_cli" else settings.openai_chat_model
    return os.getenv("EVAL_JUDGE_MODEL", default)


def judge_client(settings: Settings) -> tuple[LLMClient, str]:
    model = judge_model_name(settings)
    if settings.llm_provider == "claude_cli":
        client = ClaudeCliClient(
            cli_path=settings.llm_cli_path,
            model=model,
            timeout_seconds=settings.llm_timeout_seconds,
        )
        return client, model
    client = OpenAIChatClient(
        api_key=settings.openai_api_key.get_secret_value(),
        model=model,
        max_output_tokens=_JUDGE_MAX_OUTPUT_TOKENS,
        timeout_seconds=settings.llm_timeout_seconds,
    )
    return client, model


class JudgeModel(DeepEvalBaseLLM):
    def __init__(self, client: LLMClient, name: str) -> None:
        self._client = client
        super().__init__(name)

    def load_model(self) -> LLMClient:
        return self._client

    def get_model_name(self) -> str:
        return self.name

    def generate(self, prompt: str, schema: type[BaseModel] | None = None):
        return asyncio.run(self.a_generate(prompt, schema))

    async def a_generate(self, prompt: str, schema: type[BaseModel] | None = None):
        system = _SYSTEM
        if schema is not None:
            shape = json.dumps(schema.model_json_schema(), ensure_ascii=False)
            system += f"\n{_SCHEMA_RULE}\n{shape}"
        parts = [part async for part in self._client.stream(system, [ChatMessage("user", prompt)])]
        text = "".join(parts)
        if schema is None:
            return text
        try:
            return schema.model_validate_json(text[text.find("{") : text.rfind("}") + 1])
        except ValidationError as exc:
            raise ValueError(f"judge 가 스키마에 맞지 않는 JSON 을 냈다: {text[:300]}") from exc
