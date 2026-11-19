"""추적 어댑터. Langfuse 클라이언트를 가짜로 바꿔 네트워크 없이 기록 내용과 오류 격리만 본다."""

from src.infrastructure.llm import TokenUsage
from src.infrastructure.tracing import LangfuseTracer, NoopTracer, create_tracer


class FakeObservation:
    def __init__(self, name: str, fail: bool = False, **fields) -> None:
        self.name = name
        self.fail = fail
        self.fields = fields
        self.updates: dict = {}
        self.ended = False
        self.children: list[FakeObservation] = []
        self.trace_id = "trace-1"

    def start_observation(self, *, name: str, **fields) -> FakeObservation:
        child = FakeObservation(name, self.fail, **fields)
        self.children.append(child)
        return child

    def update(self, **fields) -> None:
        if self.fail:
            raise RuntimeError("sdk down")
        self.updates.update(fields)

    def end(self) -> None:
        self.ended = True


class FakeClient:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.roots: list[FakeObservation] = []

    def start_observation(self, *, name: str, **fields) -> FakeObservation:
        if self.fail:
            raise RuntimeError("sdk down")
        root = FakeObservation(name, **fields)
        self.roots.append(root)
        return root

    def shutdown(self) -> None:
        raise RuntimeError("sdk down")


def _tracer(client: FakeClient) -> LangfuseTracer:
    tracer = object.__new__(LangfuseTracer)
    tracer._client = client
    return tracer


def _start(tracer):
    return tracer.start("guide", user_id="v1", session_id="t1", input="질문", metadata={})


def test_without_keys_nothing_is_sent() -> None:
    tracer = create_tracer("", "", "", "local")

    trace = _start(tracer)

    assert isinstance(tracer, NoopTracer)
    assert trace.trace_id is None
    trace.step("llm", kind="generation", input=[]).end(output="x")
    trace.end(output="x")


def test_generation_records_model_usage_and_error() -> None:
    client = FakeClient()
    trace = _start(_tracer(client))

    generation = trace.step("llm", kind="generation", input=["p"], model="gpt-x")
    generation.first_token()
    generation.end(
        output="답[[show:a-b-1]]",
        usage=TokenUsage(
            input_tokens=900, output_tokens=60, reasoning_tokens=20, cached_tokens=768
        ),
        error="down",
    )
    trace.end(output="답", metadata={"mode": "fallback"})

    [root] = client.roots
    [child] = root.children
    assert trace.trace_id == "trace-1"
    assert root.fields["input"] == "질문"
    assert (child.name, child.fields["as_type"], child.fields["model"]) == (
        "llm",
        "generation",
        "gpt-x",
    )
    assert "completion_start_time" in child.updates
    assert child.updates["usage_details"] == {
        "input": 132,
        "input_cached_tokens": 768,
        "output": 40,
        "output_reasoning": 20,
    }
    assert child.updates["level"] == "ERROR"
    assert child.updates["status_message"] == "down"
    assert child.ended and root.ended
    assert root.updates["output"] == "답"
    assert "level" not in root.updates


def test_sdk_errors_do_not_escape() -> None:
    assert _start(_tracer(FakeClient(fail=True))).trace_id is None

    client = FakeClient()
    trace = _start(_tracer(client))
    client.roots[0].fail = True
    trace.step("retrieval", kind="retriever", input="q").end(output=[])
    trace.end(output="x")
    _tracer(client).shutdown()
