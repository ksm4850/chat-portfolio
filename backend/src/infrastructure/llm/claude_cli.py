"""`claude -p` 를 subprocess 로 호출하는 LLM 어댑터.

로컬 개발·테스트용이다. 구독 인증을 그대로 쓰므로 API 키가 없어도 되지만,
호출마다 프로세스를 새로 띄워 API 직접 호출보다 느리다.
배포는 `LLM_PROVIDER=openai` 로 `OpenAIChatClient` 를 쓴다.
"""

import asyncio
import json
import tempfile
from collections.abc import AsyncIterator, Sequence

from src.infrastructure.llm.base import ChatMessage, LLMClient, LLMError, TokenUsage
from src.infrastructure.logging import get_logger

logger = get_logger(__name__)

# init 이벤트처럼 한 줄이 기본 한도(64KB)를 넘는 경우가 있다.
_STREAM_LIMIT = 16 * 1024 * 1024
_SPEAKER = {"user": "상대", "assistant": "나"}


class ClaudeCliClient(LLMClient):
    def __init__(self, cli_path: str, model: str, timeout_seconds: float) -> None:
        self._cli_path = cli_path
        self._model = model
        self.model = f"claude_cli:{model}"
        self._timeout_seconds = timeout_seconds
        # 실행 위치의 CLAUDE.md 가 프롬프트에 섞이지 않도록 빈 디렉터리에서 실행한다.
        self._workdir = tempfile.mkdtemp(prefix="claude-cli-")

    async def stream(
        self,
        system: str,
        messages: Sequence[ChatMessage],
        usage: TokenUsage | None = None,
        *,
        cache_key: str | None = None,
    ) -> AsyncIterator[str]:
        try:
            process = await asyncio.create_subprocess_exec(
                *self._command(system),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self._workdir,
                limit=_STREAM_LIMIT,
            )
        except FileNotFoundError as exc:
            raise LLMError(f"claude CLI 를 찾을 수 없다: {self._cli_path}") from exc

        assert process.stdin and process.stdout and process.stderr
        try:
            async with asyncio.timeout(self._timeout_seconds):
                process.stdin.write(render_transcript(messages).encode())
                await process.stdin.drain()
                process.stdin.close()

                async for raw in process.stdout:
                    event = _parse(raw)
                    if event is None:
                        continue
                    if event.get("type") == "result" and event.get("is_error"):
                        raise LLMError(f"claude CLI 오류: {event.get('result')}")
                    if event.get("type") == "result" and usage is not None:
                        fill_usage(usage, event.get("usage") or {})
                    delta = text_delta(event)
                    if delta:
                        yield delta

                returncode = await process.wait()
                if returncode != 0:
                    stderr = (await process.stderr.read()).decode(errors="replace").strip()
                    raise LLMError(f"claude CLI 종료 코드 {returncode}: {stderr[:500]}")
        except TimeoutError as exc:
            raise LLMError(f"claude CLI 응답이 {self._timeout_seconds}초를 넘었다") from exc
        finally:
            # 클라이언트가 연결을 끊어 스트림이 중간에 닫혀도 프로세스를 남기지 않는다.
            if process.returncode is None:
                process.kill()
                await process.wait()

    def _command(self, system: str) -> list[str]:
        return [
            self._cli_path,
            "-p",
            "--model",
            self._model,
            "--system-prompt",
            system,
            "--output-format",
            "stream-json",
            "--verbose",
            "--include-partial-messages",
            "--tools",
            "",
            "--setting-sources",
            "",
            "--strict-mcp-config",
            "--no-session-persistence",
        ]


def render_transcript(messages: Sequence[ChatMessage]) -> str:
    """`claude -p` 는 단일 프롬프트만 받으므로 대화 기록을 한 덩어리 텍스트로 만든다."""
    *history, last = messages
    if not history:
        return last.content
    lines = [f"{_SPEAKER[message.role]}: {message.content}" for message in history]
    return (
        "<conversation>\n"
        + "\n".join(lines)
        + "\n</conversation>\n\n"
        + f"상대의 새 말: {last.content}\n"
        + "위 대화에 이어서 '나'로서 답한다. 화자 표시 없이 답변 내용만 쓴다."
    )


def fill_usage(usage: TokenUsage, reported: dict) -> None:
    """캐시에서 읽거나 캐시에 쓴 입력도 입력 토큰에 더한다."""
    usage.input_tokens = (
        reported.get("input_tokens", 0)
        + reported.get("cache_creation_input_tokens", 0)
        + reported.get("cache_read_input_tokens", 0)
    )
    usage.output_tokens = reported.get("output_tokens")
    usage.cached_tokens = reported.get("cache_read_input_tokens")


def text_delta(event: dict) -> str | None:
    if event.get("type") != "stream_event":
        return None
    inner = event.get("event", {})
    if inner.get("type") != "content_block_delta":
        return None
    delta = inner.get("delta", {})
    if delta.get("type") != "text_delta":
        return None
    return delta.get("text")


def _parse(raw: bytes) -> dict | None:
    line = raw.strip()
    if not line:
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        logger.warning("claude CLI 출력 파싱 실패", extra={"line": line[:200]})
        return None
