import os
import stat
from pathlib import Path

import pytest

from src.infrastructure.llm import ChatMessage, ClaudeCliClient, LLMError, TokenUsage
from src.infrastructure.llm.claude_cli import fill_usage, render_transcript, text_delta


def test_text_delta_picks_only_text_deltas() -> None:
    text = {
        "type": "stream_event",
        "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "안녕"}},
    }
    thinking = {
        "type": "stream_event",
        "event": {"type": "content_block_delta", "delta": {"type": "thinking_delta"}},
    }

    assert text_delta(text) == "안녕"
    assert text_delta(thinking) is None
    assert text_delta({"type": "assistant", "message": {}}) is None


def test_usage_counts_cached_input() -> None:
    usage = TokenUsage()

    fill_usage(
        usage,
        {
            "input_tokens": 10,
            "cache_creation_input_tokens": 300,
            "cache_read_input_tokens": 2000,
            "output_tokens": 90,
        },
    )

    assert (usage.input_tokens, usage.output_tokens, usage.reasoning_tokens) == (2310, 90, None)
    assert usage.cached_tokens == 2000


def test_single_message_is_sent_as_is() -> None:
    assert render_transcript([ChatMessage("user", "안녕")]) == "안녕"


def test_history_is_rendered_with_speakers() -> None:
    prompt = render_transcript(
        [
            ChatMessage("user", "뭐 해?"),
            ChatMessage("assistant", "코딩 중"),
            ChatMessage("user", "무슨 코딩?"),
        ]
    )

    assert "상대: 뭐 해?\n나: 코딩 중" in prompt
    assert "상대의 새 말: 무슨 코딩?" in prompt


def _fake_cli(tmp_path: Path, body: str) -> str:
    script = tmp_path / "fake-claude"
    script.write_text(f"#!/bin/sh\ncat > /dev/null\n{body}\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script)


async def test_stream_yields_deltas_from_cli_output(tmp_path: Path) -> None:
    delta = (
        '{"type":"stream_event","event":{"type":"content_block_delta",'
        '"delta":{"type":"text_delta","text":"%s"}}}'
    )
    cli = _fake_cli(tmp_path, f"echo '{delta % '안녕'}'\necho '{delta % '하세요'}'")
    client = ClaudeCliClient(cli, model="haiku", timeout_seconds=5)

    parts = [part async for part in client.stream("system", [ChatMessage("user", "hi")])]

    assert parts == ["안녕", "하세요"]


async def test_nonzero_exit_raises_llm_error(tmp_path: Path) -> None:
    cli = _fake_cli(tmp_path, "echo 'boom' >&2\nexit 3")
    client = ClaudeCliClient(cli, model="haiku", timeout_seconds=5)

    with pytest.raises(LLMError, match="boom"):
        [part async for part in client.stream("system", [ChatMessage("user", "hi")])]


async def test_missing_cli_raises_llm_error() -> None:
    client = ClaudeCliClient(os.devnull + "-missing", model="haiku", timeout_seconds=5)

    with pytest.raises(LLMError):
        [part async for part in client.stream("system", [ChatMessage("user", "hi")])]
