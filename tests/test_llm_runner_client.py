"""Tests for the llm-runner AI client integration surface."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import pytest

from src.ai.analyzer import ContentAnalyzer
from src.ai import client as client_module
from src.ai.client import AnthropicClient, LLMRunnerClient, OpenAIClient, create_ai_client
from src.ai.tokens import get_usage_snapshot, reset_usage
from src.models import AIConfig, AIProvider, ContentItem, SourceType


class _FakeProcess:
    def __init__(self, stdout: bytes, stderr: bytes = b"", returncode: int = 0):
        self.stdout = _FakeStdout(stdout)
        self.stderr = _FakeStderr(stderr)
        self.returncode = returncode
        self.stdin_payload = None
        self.stdin = _FakeStdin(self)

    async def wait(self):
        return self.returncode


class _FakeStdin:
    def __init__(self, process):
        self._process = process

    def write(self, payload):
        self._process.stdin_payload = payload

    async def drain(self):
        return None

    def close(self):
        return None

    async def wait_closed(self):
        return None


class _FakeStderr:
    def __init__(self, payload: bytes):
        self._payload = payload

    async def read(self):
        return self._payload


class _FakeStdout:
    def __init__(self, payload: bytes):
        self._lines = payload.splitlines(keepends=True)

    def __aiter__(self):
        self._iter = iter(self._lines)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


def _make_config(**overrides):
    values = {
        "provider": AIProvider.LLM_RUNNER,
        "model": "gpt-5.5",
        "llm_runner_provider": "codex",
    }
    values.update(overrides)
    return AIConfig(**values)


def test_llm_runner_config_does_not_require_api_key_env():
    config = AIConfig(
        provider=AIProvider.LLM_RUNNER,
        model="gpt-5.5",
        llm_runner_provider="codex",
        cache_enabled=False,
    )

    assert config.api_key_env is None
    assert config.llm_runner_provider == "codex"


def test_factory_creates_llm_runner_client():
    config = AIConfig(
        provider=AIProvider.LLM_RUNNER,
        model="gpt-5.5",
        llm_runner_provider="codex",
        cache_enabled=False,
    )

    client = create_ai_client(config)

    assert isinstance(client, LLMRunnerClient)


@pytest.mark.parametrize(
    ("provider", "client_cls", "match"),
    [
        (AIProvider.OPENAI, OpenAIClient, "api_key_env is required for openai provider"),
        (AIProvider.ANTHROPIC, AnthropicClient, "api_key_env is required for anthropic provider"),
    ],
)
def test_sdk_providers_require_api_key_env(provider, client_cls, match):
    config = AIConfig(provider=provider, model="test-model")

    with pytest.raises(ValueError, match=match):
        client_cls(config)


def test_complete_invokes_llm_runner_and_returns_text(monkeypatch):
    reset_usage()
    result_payload = {
        "status": "succeeded",
        "provider": "codex",
        "model": "gpt-5.5",
        "text": "{\"score\": 8, \"reason\": \"useful\", \"summary\": \"ok\", \"tags\": [\"ai\"]}",
        "usage": {"input_tokens": 11, "output_tokens": 7},
        "diagnostics": {"exit_code": 0},
    }
    stream = "\n".join([
        json.dumps({"type": "run.started", "provider": "codex", "model": "gpt-5.5"}),
        json.dumps({"type": "run.completed", "provider": "codex", "model": "gpt-5.5", "result": result_payload}),
        "",
    ])
    process = _FakeProcess(stream.encode())
    calls = []

    async def fake_create_subprocess_exec(*args, **kwargs):
        calls.append((args, kwargs))
        return process

    monkeypatch.setattr(client_module.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    client = LLMRunnerClient(_make_config())
    result = asyncio.run(client.complete(system="system prompt", user="user prompt"))

    assert json.loads(result)["score"] == 8
    args, kwargs = calls[0]
    assert args[:6] == (
        "llm-runner",
        "run",
        "--provider",
        "codex",
        "--model",
        "gpt-5.5",
    )
    assert "--stream-json" in args
    assert "--trace-jsonl" in args
    assert "--raw-event-dir" in args
    assert "--hang-window" in args
    assert "--heartbeat-interval" in args
    assert kwargs["stdin"] == client_module.asyncio.subprocess.PIPE
    assert kwargs["stdout"] == client_module.asyncio.subprocess.PIPE
    assert kwargs["stderr"] == client_module.asyncio.subprocess.PIPE
    assert b"system prompt" in process.stdin_payload
    assert b"user prompt" in process.stdin_payload

    usage = get_usage_snapshot().per_provider["llm_runner"]
    assert usage.input_tokens == 11
    assert usage.output_tokens == 7


def test_llm_runner_client_integrates_config_factory_subprocess_and_analyzer(monkeypatch):
    result_payload = {
        "status": "succeeded",
        "provider": "codex",
        "model": "gpt-5.5",
        "text": "{\"score\": 9, \"reason\": \"cross-module\", \"summary\": \"integrated\", \"tags\": [\"runner\"]}",
        "usage": {"input_tokens": 13, "output_tokens": 5},
        "diagnostics": {"exit_code": 0},
    }
    stream = "\n".join([
        json.dumps({"type": "run.started", "provider": "codex", "model": "gpt-5.5"}),
        json.dumps({"type": "run.completed", "provider": "codex", "model": "gpt-5.5", "result": result_payload}),
        "",
    ])
    process = _FakeProcess(stream.encode())
    calls = []

    async def fake_create_subprocess_exec(*args, **kwargs):
        calls.append((args, kwargs))
        return process

    monkeypatch.setattr(client_module.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    config = AIConfig(
        provider=AIProvider.LLM_RUNNER,
        model="gpt-5.5",
        llm_runner_provider="codex",
        cache_enabled=False,
    )
    ai_client = create_ai_client(config)
    item = ContentItem(
        id="rss:test:integration",
        source_type=SourceType.RSS,
        title="Runner integration",
        url="https://example.com/integration",
        published_at=datetime(2026, 5, 8, tzinfo=timezone.utc),
    )

    asyncio.run(ContentAnalyzer(ai_client)._analyze_item(item))

    args, kwargs = calls[0]
    assert isinstance(ai_client, LLMRunnerClient)
    assert args[:6] == (
        "llm-runner",
        "run",
        "--provider",
        "codex",
        "--model",
        "gpt-5.5",
    )
    assert "--stream-json" in args
    assert kwargs["stdin"] == client_module.asyncio.subprocess.PIPE
    assert b"Runner integration" in process.stdin_payload
    assert item.ai_score == 9.0
    assert item.ai_reason == "cross-module"
    assert item.ai_summary == "integrated"
    assert item.ai_tags == ["runner"]


def test_complete_raises_on_runner_failure(monkeypatch):
    result_payload = {
        "status": "auth_required",
        "text": "",
        "diagnostics": {"exit_code": 14, "reason": "provider login required"},
    }
    stream = json.dumps({"type": "run.failed", "result": result_payload}) + "\n"
    process = _FakeProcess(stream.encode(), stderr=b"login required", returncode=14)

    async def fake_create_subprocess_exec(*args, **kwargs):
        return process

    monkeypatch.setattr(client_module.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    client = LLMRunnerClient(_make_config())
    with pytest.raises(RuntimeError, match="provider login required"):
        asyncio.run(client.complete(system="system", user="user"))


def test_complete_raises_on_invalid_runner_stream_json(monkeypatch):
    process = _FakeProcess(b"not-json", stderr=b"bad output", returncode=0)

    async def fake_create_subprocess_exec(*args, **kwargs):
        return process

    monkeypatch.setattr(client_module.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    client = LLMRunnerClient(_make_config())
    with pytest.raises(RuntimeError, match="invalid stream JSON"):
        asyncio.run(client.complete(system="system", user="user"))
