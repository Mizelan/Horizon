# LLM Runner Provider Implementation Plan

> Historical note: this root-level plan is non-authoritative for runner config
> field names. The approved sprint artifact in
> `docs/plans/2026-05-08-llm-runner-provider/2026-05-08-llm-runner-provider.md`
> and the implementation schema use `llm_runner_command` and
> `llm_runner_provider`; older `runner_*` field names below are preserved only
> as planning history and must not be used for implementation or verification.

> **For Codex:** REQUIRED SUB-SKILL: Use `$executing-plans` to implement this plan task-by-task.

**Goal:** Add an `llm_runner` AI provider to Horizon so LLM analysis can run through the local `llm-runner` CLI instead of Horizon-owned API key SDK calls.

**Architecture:** Keep existing SDK providers unchanged and add a separate `LLMRunnerClient` implementing `AIClient.complete()`. The new client invokes `llm-runner run --json` through `asyncio.create_subprocess_exec`, sends the combined system/user prompt through stdin, parses the final normalized result JSON, and returns `result["text"]`. Horizon config must not accept API keys, auth tokens, provider secrets, or generic child-process env passthrough for this provider.

**Tech Stack:** Python 3.11+, Pydantic v2, asyncio subprocesses, pytest, existing Horizon `AIClient` abstraction, external `llm-runner` executable.

---

## Mission Frame

- **Mission:** Install and verify a Horizon integration path where LLM calls can use `llm-runner` as a subprocess-only provider.
- **Evidence of Success:** Focused pytest coverage passes for model parsing, factory selection, subprocess success/failure handling, setup wizard behavior, MCP env validation, and analyzer JSON parsing through `LLMRunnerClient`.
- **Boundaries:** Do not change existing provider behavior except where optional `api_key_env` requires safe guards. Do not import Go packages from `llm-runner`. Do not add API key/auth token/provider secret fields for `llm_runner`. Do not claim live provider compatibility unless a real opt-in `llm-runner run` smoke succeeds.

## Design Step

### Depth

Depth: deep

Reason: This changes the config model, AI client factory, setup wizard, MCP validation, documentation, and tests. It also relaxes the existing `AIConfig.api_key_env` required-field assumption.

### Gate

Gate: triggered

Condition check:
- 2+ layers/files changed? yes
- DB/API/infrastructure hard-to-rollback decision? no
- Existing assumption changed? yes, `api_key_env` is no longer universal for every AI provider

### Design Overview

Add `AIProvider.LLM_RUNNER = "llm_runner"` and make `AIConfig.api_key_env` optional. Add runner-specific fields to `AIConfig`: `runner_provider`, `runner_bin`, `runner_effort`, `runner_timeout`, `runner_hang_window`, `runner_heartbeat_interval`, and `runner_raw_event_dir`. `LLMRunnerClient` should construct argv directly, never through a shell string, and should only pass supported `llm-runner` protocol fields as CLI flags.

The setup wizard must not ask for an API key environment variable for `llm_runner`, and it must not check for key presence before source recommendations. For this provider, the wizard should treat AI recommendations as available without running a preflight; `src/setup/ai_recommend.py` already catches `create_ai_client()` and `client.complete()` failures and returns an empty recommendation list. The MCP config validator should not report `missing_env` for `ai.api_key_env` when the selected provider is `llm_runner`.

## 설계자 예측

1. Setup wizard key checks will be a real integration risk because the current code assumes every provider has `api_key_env`. The plan includes explicit wizard and MCP tasks to remove that assumption for `llm_runner`.
2. The runner text may not be valid Horizon analysis JSON even when the subprocess succeeds. The plan verifies this through TDD at the `ContentAnalyzer` level and preserves the existing fallback behavior for unparseable analysis output.
3. Live provider smoke can fail because provider CLI account state belongs outside Horizon. The plan separates contract tests from optional live smoke and allows `llm-runner` repo repair only when Horizon TDD exposes a runner protocol defect.

Previous related experience:
- `llm-runner` consumers must parse the final normalized result object rather than expecting direct stdout text.
- The accepted runner boundary is CLI-only, subprocess-only, and no direct API/SDK/HTTP client inside the runner path.

## Non-Goals

- Do not remove OpenAI, Anthropic, Azure, Gemini, MiniMax, Ali, or Doubao clients.
- Do not make `llm-runner` the default provider in `data/config.example.json`.
- Do not add Horizon-managed secret injection for provider subprocesses.
- Do not introduce a generic env passthrough field.
- Do not block merge on live Codex app account availability.

## Tasks

### Task 1: Add failing model and factory tests

**Files:**
- Create: `tests/test_llm_runner_client.py`
- Modify later: `src/models.py`
- Modify later: `src/ai/client.py`

**Step 1: Write the failing tests**

Create `tests/test_llm_runner_client.py`:

```python
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

import src.ai.client as client_module
from src.ai.client import LLMRunnerClient, create_ai_client
from src.models import AIConfig, AIProvider


def _make_config(**overrides) -> AIConfig:
    defaults = {
        "provider": AIProvider.LLM_RUNNER,
        "model": "gpt-5.5",
        "runner_provider": "codex",
        "runner_bin": "llm-runner",
        "runner_timeout": "2m",
        "runner_hang_window": "30s",
        "temperature": 0.3,
        "max_tokens": 4096,
    }
    defaults.update(overrides)
    return AIConfig(**defaults)


def test_llm_runner_config_does_not_require_api_key_env():
    config = _make_config()
    assert config.api_key_env is None
    assert config.provider == AIProvider.LLM_RUNNER


def test_factory_creates_llm_runner_client():
    client = create_ai_client(_make_config())
    assert isinstance(client, LLMRunnerClient)
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_llm_runner_client.py -q
```

Expected: FAIL because `AIProvider.LLM_RUNNER` and `LLMRunnerClient` do not exist yet.

**Step 3: Implement the minimal model/factory surface**

Modify `src/models.py`:

```python
class AIProvider(str, Enum):
    """Supported AI providers."""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    AZURE = "azure"
    ALI = "ali"
    GEMINI = "gemini"
    DOUBAO = "doubao"
    MINIMAX = "minimax"
    LLM_RUNNER = "llm_runner"


class AIConfig(BaseModel):
    """AI client configuration."""

    provider: AIProvider
    model: str
    base_url: Optional[str] = None
    api_key_env: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 4096
    throttle_sec: float = 0.0
    languages: List[str] = Field(default_factory=lambda: ["en"])
    azure_endpoint_env: Optional[str] = None
    api_version: Optional[str] = None
    runner_provider: Optional[str] = None
    runner_bin: str = "llm-runner"
    runner_effort: Optional[str] = None
    runner_timeout: str = "10m"
    runner_hang_window: Optional[str] = None
    runner_heartbeat_interval: Optional[str] = None
    runner_raw_event_dir: Optional[str] = None
```

Modify `src/ai/client.py` with a temporary class shell:

```python
class LLMRunnerClient(AIClient):
    """Client for local llm-runner subprocess execution."""

    def __init__(self, config: AIConfig):
        self.config = config
        self.model = config.model
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens
        self.runner_provider = config.runner_provider
        self.runner_bin = config.runner_bin
```

Add factory branch:

```python
elif config.provider == AIProvider.LLM_RUNNER:
    return LLMRunnerClient(config)
```

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/test_llm_runner_client.py::test_llm_runner_config_does_not_require_api_key_env tests/test_llm_runner_client.py::test_factory_creates_llm_runner_client -q
```

Expected: `2 passed`.

### Task 1.5: Preserve existing SDK provider API-key error contract

**Files:**
- Modify: `tests/test_llm_runner_client.py`
- Modify: `src/ai/client.py`

**Step 1: Add failing regression tests**

Append to `tests/test_llm_runner_client.py`:

```python
def test_openai_provider_without_api_key_env_raises_value_error():
    config = AIConfig(provider=AIProvider.OPENAI, model="gpt-4")

    with pytest.raises(ValueError, match="api_key_env is required for provider openai"):
        create_ai_client(config)


def test_anthropic_provider_without_api_key_env_raises_value_error():
    config = AIConfig(provider=AIProvider.ANTHROPIC, model="claude-sonnet-4.5-20250929")

    with pytest.raises(ValueError, match="api_key_env is required for provider anthropic"):
        create_ai_client(config)
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_llm_runner_client.py::test_openai_provider_without_api_key_env_raises_value_error tests/test_llm_runner_client.py::test_anthropic_provider_without_api_key_env_raises_value_error -q
```

Expected: FAIL until SDK client initialization explicitly handles `api_key_env=None`.

**Step 3: Add a shared API-key guard for SDK providers**

Modify `src/ai/client.py` near the top-level helpers:

```python
def _get_required_api_key(config: AIConfig) -> str:
    if not config.api_key_env:
        raise ValueError(f"api_key_env is required for provider {config.provider.value}")
    api_key = os.getenv(config.api_key_env)
    if not api_key:
        raise ValueError(f"Missing API key: {config.api_key_env}")
    return api_key
```

Replace every SDK provider constructor pattern like:

```python
api_key = os.getenv(config.api_key_env)
if not api_key:
    raise ValueError(f"Missing API key: {config.api_key_env}")
```

with:

```python
api_key = _get_required_api_key(config)
```

Apply this replacement only to `AnthropicClient`, `OpenAIClient`, `AzureOpenAIClient`, `MiniMaxClient`, `AliClient`, and `GeminiClient`. Do not call this helper from `LLMRunnerClient`.

**Step 4: Run regression tests**

Run:

```bash
uv run pytest tests/test_llm_runner_client.py tests/test_minimax_client.py tests/test_azure_client.py -q
```

Expected: all selected tests pass, including existing `Missing API key` tests for configured SDK providers.

### Task 2: Implement subprocess success path with TDD

**Files:**
- Modify: `tests/test_llm_runner_client.py`
- Modify: `src/ai/client.py`

**Step 1: Add failing subprocess success test**

Append to `tests/test_llm_runner_client.py`:

```python
class _FakeProcess:
    def __init__(self, stdout: bytes, stderr: bytes = b"", returncode: int = 0):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode
        self.stdin_payload = None

    async def communicate(self, input=None):
        self.stdin_payload = input
        return self._stdout, self._stderr


def test_complete_invokes_llm_runner_and_returns_text(monkeypatch):
    payload = {
        "status": "succeeded",
        "provider": "codex",
        "model": "gpt-5.5",
        "text": "{\"score\": 8, \"reason\": \"useful\", \"summary\": \"ok\", \"tags\": [\"ai\"]}",
        "usage": {"input_tokens": 11, "output_tokens": 7},
        "diagnostics": {"exit_code": 0},
    }
    process = _FakeProcess(json.dumps(payload).encode())
    calls = []

    async def fake_create_subprocess_exec(*args, **kwargs):
        calls.append((args, kwargs))
        return process

    monkeypatch.setattr(client_module.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    client = LLMRunnerClient(_make_config(runner_raw_event_dir="/tmp/horizon-runner-events"))
    result = asyncio.run(client.complete(system="system prompt", user="user prompt"))

    assert json.loads(result)["score"] == 8
    args, kwargs = calls[0]
    assert args[:4] == ("llm-runner", "run", "--provider", "codex")
    assert "--json" in args
    assert "--model" in args
    assert "--timeout" in args
    assert "--raw-event-dir" in args
    assert kwargs["stdin"] == client_module.asyncio.subprocess.PIPE
    assert b"system prompt" in process.stdin_payload
    assert b"user prompt" in process.stdin_payload
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_llm_runner_client.py::test_complete_invokes_llm_runner_and_returns_text -q
```

Expected: FAIL because `complete()` is not implemented.

**Step 3: Implement subprocess success path**

Modify imports in `src/ai/client.py`:

```python
import asyncio
import json
```

Implement `LLMRunnerClient.complete()`:

```python
class LLMRunnerClient(AIClient):
    """Client for local llm-runner subprocess execution."""

    def __init__(self, config: AIConfig):
        self.config = config
        self.model = config.model
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens
        self.runner_provider = config.runner_provider or "codex"
        self.runner_bin = config.runner_bin

    async def complete(
        self,
        system: str,
        user: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        prompt = self._build_prompt(system, user)
        args = self._build_args()
        process = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate(prompt.encode("utf-8"))
        result = self._parse_result(stdout=stdout, stderr=stderr, returncode=process.returncode)
        usage = result.get("usage") or {}
        record_usage(
            "llm_runner",
            input_tokens=int(usage.get("input_tokens") or 0),
            output_tokens=int(usage.get("output_tokens") or 0),
        )
        return str(result.get("text") or "")

    def _build_prompt(self, system: str, user: str) -> str:
        return f"System:\n{system}\n\nUser:\n{user}\n"

    def _build_args(self) -> list[str]:
        args = [
            self.runner_bin,
            "run",
            "--provider",
            self.runner_provider,
            "--model",
            self.model,
            "--json",
            "--timeout",
            self.config.runner_timeout,
        ]
        if self.config.runner_effort:
            args.extend(["--effort", self.config.runner_effort])
        if self.config.runner_hang_window:
            args.extend(["--hang-window", self.config.runner_hang_window])
        if self.config.runner_heartbeat_interval:
            args.extend(["--heartbeat-interval", self.config.runner_heartbeat_interval])
        if self.config.runner_raw_event_dir:
            args.extend(["--raw-event-dir", self.config.runner_raw_event_dir])
        return args

    def _parse_result(self, *, stdout: bytes, stderr: bytes, returncode: int) -> dict:
        try:
            result = json.loads(stdout.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError("llm-runner returned invalid JSON") from exc

        status = result.get("status")
        if returncode != 0 or status != "succeeded":
            reason = ((result.get("diagnostics") or {}).get("reason") or "").strip()
            stderr_text = stderr.decode("utf-8", errors="replace").strip()
            detail = reason or stderr_text or f"status={status} exit={returncode}"
            raise RuntimeError(f"llm-runner failed: {detail}")
        return result
```

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/test_llm_runner_client.py::test_complete_invokes_llm_runner_and_returns_text -q
```

Expected: `1 passed`.

### Task 3: Add failure-path TDD coverage

**Files:**
- Modify: `tests/test_llm_runner_client.py`
- Modify: `src/ai/client.py`

**Step 1: Add failing tests for invalid JSON and failure status**

Append:

```python
def test_complete_raises_on_runner_failure(monkeypatch):
    payload = {
        "status": "auth_required",
        "text": "",
        "diagnostics": {"exit_code": 14, "reason": "provider login required"},
    }
    process = _FakeProcess(json.dumps(payload).encode(), stderr=b"login required", returncode=14)

    async def fake_create_subprocess_exec(*args, **kwargs):
        return process

    monkeypatch.setattr(client_module.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    client = LLMRunnerClient(_make_config())
    with pytest.raises(RuntimeError, match="provider login required"):
        asyncio.run(client.complete(system="system", user="user"))


def test_complete_raises_on_invalid_runner_json(monkeypatch):
    process = _FakeProcess(b"not-json", stderr=b"bad output", returncode=0)

    async def fake_create_subprocess_exec(*args, **kwargs):
        return process

    monkeypatch.setattr(client_module.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    client = LLMRunnerClient(_make_config())
    with pytest.raises(RuntimeError, match="invalid JSON"):
        asyncio.run(client.complete(system="system", user="user"))
```

**Step 2: Run tests**

Run:

```bash
uv run pytest tests/test_llm_runner_client.py -q
```

Expected: all `test_llm_runner_client.py` tests pass.

**Step 3: Repair on malformed-result failure**

If failure details show raw stderr or malformed result handling is wrong, update only `LLMRunnerClient._parse_result()` and rerun the same command.

### Task 4: Remove setup wizard key-presence checks for llm_runner

**Files:**
- Modify: `tests/test_setup_wizard.py` or create it if absent
- Modify: `src/setup/wizard.py`

**Step 1: Write failing wizard tests**

If `tests/test_setup_wizard.py` does not exist, create it:

```python
from __future__ import annotations

from src.models import AIProvider
from src.setup import wizard


def test_configure_ai_llm_runner_does_not_prompt_for_api_key(monkeypatch):
    answers = iter(["llm_runner", "gpt-5.5", "", "codex", "zh,en"])
    prompts = []

    def fake_prompt(label, **kwargs):
        prompts.append(label)
        return next(answers)

    monkeypatch.setattr(wizard.Prompt, "ask", fake_prompt)
    monkeypatch.delenv("API_KEY", raising=False)

    config = wizard.configure_ai()

    assert config.provider == AIProvider.LLM_RUNNER
    assert config.api_key_env is None
    assert config.runner_provider == "codex"
    assert "API key environment variable name" not in prompts


def test_ai_recommendations_available_for_llm_runner_without_api_key():
    config = wizard.AIConfig(
        provider=AIProvider.LLM_RUNNER,
        model="gpt-5.5",
        runner_provider="codex",
    )

    assert wizard._ai_recommendations_available(config) is True


def test_ai_recommendations_require_existing_key_for_sdk_provider(monkeypatch):
    config = wizard.AIConfig(
        provider=AIProvider.OPENAI,
        model="gpt-4",
        api_key_env="OPENAI_API_KEY",
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert wizard._ai_recommendations_available(config) is False
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_setup_wizard.py::test_configure_ai_llm_runner_does_not_prompt_for_api_key -q
```

Expected: FAIL because the wizard still prompts for `api_key_env`.

**Step 3: Update wizard provider branch**

Modify `src/setup/wizard.py` inside `configure_ai()`:

```python
    model = Prompt.ask("Model name", default="deepseek-chat" if provider == "openai" else "")

    base_url = Prompt.ask("Base URL (leave empty for default)", default="")

    runner_provider = None
    api_key_env = None
    if provider == AIProvider.LLM_RUNNER.value:
        runner_provider = Prompt.ask(
            "llm-runner provider",
            choices=["codex", "claude", "ollama"],
            default="codex",
        )
    else:
        default_env = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "gemini": "GOOGLE_API_KEY",
            "ali": "DASHSCOPE_API_KEY",
            "doubao": "DOUBAO_API_KEY",
            "minimax": "MINIMAX_API_KEY",
        }
        api_key_env = Prompt.ask(
            "API key environment variable name",
            default=default_env.get(provider, "API_KEY"),
        )
```

Remove the immediate key existence warning block from `configure_ai()`. Then return:

```python
    return AIConfig(
        provider=AIProvider(provider),
        model=model,
        base_url=base_url or None,
        api_key_env=api_key_env,
        runner_provider=runner_provider,
        temperature=0.3,
        max_tokens=8192,
        languages=lang_list,
    )
```

**Step 4: Update recommendation availability logic**

Add this helper near `configure_ai()` in `src/setup/wizard.py`:

```python
def _ai_recommendations_available(ai_config: AIConfig) -> bool:
    if ai_config.provider == AIProvider.LLM_RUNNER:
        return True
    return bool(ai_config.api_key_env and os.getenv(ai_config.api_key_env))
```

Modify `main()`:

```python
    ai_available = _ai_recommendations_available(ai_config)
```

Modify skip message:

```python
        if ai_config.api_key_env:
            console.print(
                f"\n[dim]Skipping AI recommendations ({ai_config.api_key_env} not set)[/dim]"
            )
        else:
            console.print("\n[dim]Skipping AI recommendations[/dim]")
```

**Step 5: Run wizard test**

Run:

```bash
uv run pytest tests/test_setup_wizard.py -q
```

Expected: all setup wizard tests pass.

### Task 5: Update MCP environment validation

**Files:**
- Modify: `tests/test_mcp_service_smoke.py`
- Modify: `src/mcp/service.py`

**Step 1: Add failing MCP validation test**

Append to `tests/test_mcp_service_smoke.py` or add near existing `validate_config` tests:

```python
def test_validate_config_does_not_require_api_key_for_llm_runner(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        """
{
  "version": "1.0",
  "ai": {
    "provider": "llm_runner",
    "model": "gpt-5.5",
    "runner_provider": "codex"
  },
  "sources": {"rss": []},
  "filtering": {"ai_score_threshold": 6.0, "time_window_hours": 24}
}
""".strip(),
        encoding="utf-8",
    )

    from src.mcp.service import HorizonMCPService

    service = HorizonMCPService()
    result = asyncio.run(service.validate_config(config_path=str(config_path), check_env=True))

    assert result["missing_env"] == []
    assert result["ai"]["provider"] == "llm_runner"
    assert result["ai"]["api_key_env"] is None
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_mcp_service_smoke.py::test_validate_config_does_not_require_api_key_for_llm_runner -q
```

Expected: FAIL because `validate_config()` assumes `ctx.config.ai.api_key_env` exists and is required.

**Step 3: Implement MCP guard**

Modify `src/mcp/service.py`:

```python
        if check_env:
            required = []
            if ctx.config.ai.api_key_env:
                required.append(ctx.config.ai.api_key_env)
            for key in required:
                if not os.getenv(key):
                    missing_env.append(key)
```

And in returned `ai` object keep:

```python
                "api_key_env": ctx.config.ai.api_key_env,
```

**Step 4: Run test**

Run:

```bash
uv run pytest tests/test_mcp_service_smoke.py::test_validate_config_does_not_require_api_key_for_llm_runner -q
```

Expected: `1 passed`.

### Task 6: Verify analyzer behavior through runner text

**Files:**
- Modify: `tests/test_analyzer.py`
- No production changes expected unless the test exposes a regression

**Step 1: Add analyzer TDD tests**

Append to `tests/test_analyzer.py`:

```python
def test_analyze_item_accepts_json_text_from_llm_runner_client():
    item = _make_item("rss:test:runner-json")

    class FakeRunnerClient:
        config = SimpleNamespace(throttle_sec=0)

        async def complete(self, system, user):
            return '{"score": 9, "reason": "important", "summary": "runner ok", "tags": ["llm"]}'

    analyzer = ContentAnalyzer(FakeRunnerClient())
    asyncio.run(analyzer._analyze_item(item))

    assert item.ai_score == 9.0
    assert item.ai_reason == "important"
    assert item.ai_summary == "runner ok"
    assert item.ai_tags == ["llm"]


def test_analyze_item_falls_back_when_llm_runner_text_is_not_json():
    item = _make_item("rss:test:runner-text")

    class FakeRunnerClient:
        config = SimpleNamespace(throttle_sec=0)

        async def complete(self, system, user):
            return "plain text response"

    analyzer = ContentAnalyzer(FakeRunnerClient())
    asyncio.run(analyzer._analyze_item(item))

    assert item.ai_score == 0.0
    assert item.ai_reason == "Analysis response parse failed"
    assert item.ai_summary == item.title
    assert item.ai_tags == []
```

**Step 2: Run tests**

Run:

```bash
uv run pytest tests/test_analyzer.py -q
```

Expected: all analyzer tests pass.

**Step 3: Repair on analyzer fallback failure**

If fallback behavior is broken, repair only `src/ai/analyzer.py` parsing/fallback logic and rerun the same command.

### Task 7: Update docs and example config

**Files:**
- Modify: `docs/configuration.md`
- Modify: `README.md`
- Modify: `README_zh.md`
- Modify: `data/config.example.json` only if adding a commented example is not required. JSON cannot contain comments, so prefer docs over changing the default config.

**Step 1: Add configuration docs**

Add to `docs/configuration.md` under AI Providers:

```markdown
**llm-runner**:

```json
{
  "ai": {
    "provider": "llm_runner",
    "model": "gpt-5.5",
    "runner_provider": "codex",
    "runner_timeout": "10m",
    "runner_hang_window": "2m",
    "throttle_sec": 0
  }
}
```

Horizon invokes the local `llm-runner` executable and sends prompts through subprocess stdin. This provider does not use `api_key_env` in Horizon config. Provider credentials, if any, remain owned by the provider CLI environment outside Horizon.
```

**Step 2: Add README note**

In `README.md` manual configuration section, add one short paragraph after the OpenAI example:

```markdown
For subprocess-only execution through a local provider CLI, use `provider: "llm_runner"` with `model: "gpt-5.5"` and `runner_provider`/`llm_runner_provider` set to `codex` for the Codex app path. This mode does not use `api_key_env` in Horizon config; the provider CLI owns its own login or environment.
```

Mirror the same meaning in `README_zh.md`.

**Step 3: Run docs checks**

Run:

```bash
git diff --check -- docs/configuration.md README.md README_zh.md
```

Expected: no output and exit code 0.

### Task 8: Optional llm-runner repository repair lane

**Files:**
- Horizon files only unless a focused Horizon TDD failure proves a runner protocol defect.
- Modify `/Users/mizelan/Documents/GitHub/llm-runner` only when a focused Horizon TDD failure or `llm-runner probe` result proves a runner protocol defect.

**Step 1: Confirm whether runner repair is necessary**

Run after Horizon unit tests pass:

```bash
command -v llm-runner
llm-runner probe --help
```

Expected:
- If `llm-runner` is installed and local preflight succeeds, proceed to optional smoke.
- If the binary is missing, install it with the exact command below, then rerun `command -v llm-runner` and `llm-runner probe --help`:

```bash
(cd /Users/mizelan/Documents/GitHub/llm-runner && make install)
export PATH="$PATH:$HOME/.local/bin"
```

- If probe exposes a local wrapper bug, switch to the `llm-runner` repo and fix that bug with its own TDD before returning to Horizon.

**Step 2: Optional smoke**

Only run when local provider credentials/CLI state are available:

```bash
printf 'Return exactly this JSON object and nothing else: {"score":8,"reason":"ok","summary":"ok","tags":["smoke"]}\n' \
  | llm-runner run --provider codex --model gpt-5.5 --json --timeout 2m
```

Expected:
- Success path: final JSON has `"status":"succeeded"` and `text` contains parseable JSON for Horizon.
- Auth/quota path: final JSON or exit class reports `auth_required`, `quota_exhausted`, `config_error`, or another non-success status. Treat this as live-provider environment evidence, not a Horizon integration failure.

### Task 9: Final verification

**Files:**
- All touched files

**Step 1: Focused tests**

Run:

```bash
uv run pytest tests/test_llm_runner_client.py tests/test_setup_wizard.py tests/test_mcp_service_smoke.py tests/test_analyzer.py -q
```

Expected: all selected tests pass.

**Step 2: Full tests**

Run:

```bash
uv run pytest -q
```

Expected: full test suite passes.

**Step 3: Boundary scan**

Run:

```bash
rg -n "api_key|auth_token|provider_secret|Authorization|generic env|env passthrough" src/ai src/models.py src/setup/wizard.py src/mcp/service.py docs/configuration.md README.md README_zh.md
```

Expected:
- Existing SDK provider API key references remain.
- `llm_runner` docs/code must not introduce API key/auth token/provider secret request fields or generic env passthrough.

**Step 3.5: Placeholder scan**

Run:

```bash
terms=("T""BD" "TO""DO" "may""be" "like""ly" "if need""ed" "optional mod""ify" "적절""히" "유사""하게")
pattern="$(IFS='|'; echo "${terms[*]}")"
! rg -n "$pattern" docs/plans/2026-05-08-llm-runner-provider.md
```

Expected: no output and exit code 0.

**Step 4: Diff hygiene**

Run:

```bash
git diff --check
```

Expected: no output and exit code 0.

## Critical Plan Feedback

- [P1] Finding: The original design only mentioned `src/ai/client.py`, but setup wizard and MCP validation also hard-code `api_key_env`.
  Impact: Horizon would appear to support `llm_runner` but setup/validation would still report missing API keys.
  Plan update: Added Task 4 and Task 5 with explicit tests and implementation guards.

- [P1] Finding: Making `AIConfig.api_key_env` optional without an SDK guard would let existing SDK providers call `os.getenv(None)` and raise a `TypeError` instead of Horizon's current `ValueError` contract.
  Impact: A future agent could pass `llm_runner` tests while regressing OpenAI/Anthropic/Azure/MiniMax/Ali/Gemini initialization failures.
  Plan update: Added Task 1.5 with regression tests and a shared `_get_required_api_key()` helper that must not be used by `LLMRunnerClient`.

- [P2] Finding: A successful runner subprocess does not guarantee Horizon analysis JSON.
  Impact: Production analysis could silently degrade or fail if provider text is not JSON.
  Plan update: Added Task 6 to verify both parseable runner text and fallback behavior.

- [P2] Finding: Live `llm-runner` smoke can fail for provider-owned auth/account reasons.
  Impact: A correct Horizon integration could be misclassified as broken.
  Plan update: Added Task 8 and Task 9 to separate contract tests, local probe, optional live smoke, and environment failure classes.

- [P2] Finding: The setup wizard recommendation path could still hide an `api_key_env` assumption inside `main()` even after `configure_ai()` stops prompting for a key.
  Impact: A future implementation could pass the configure-only test but still crash or skip incorrectly when the full wizard reaches AI recommendations.
  Plan update: Task 4 now introduces `_ai_recommendations_available()` and tests both `llm_runner` and SDK provider branches.

- [P2] Finding: The runner install fallback originally pointed to the sibling repo documentation instead of an exact command.
  Impact: A future implementation agent could stop at a missing `llm-runner` binary instead of installing and probing it.
  Plan update: Task 8 now gives the exact `(cd /Users/mizelan/Documents/GitHub/llm-runner && make install)` command and the required probe rerun.

## Self-Review

- Design coverage: covered config model, client implementation, setup wizard, MCP validation, analyzer behavior, docs, optional runner repair, and final verification.
- Placeholder scan: no unresolved placeholder markers or unspecified file paths remain.
- Consistency: provider name is consistently `llm_runner`; runner-specific fields use `runner_*`; usage accounting provider label is `llm_runner`.
- Handoff readiness: each task has exact files, test commands, expected outcomes, and repair boundaries.

## Execution Routing

Plan is ready at `docs/plans/2026-05-08-llm-runner-provider.md`.

Use `$executing-plans docs/plans/2026-05-08-llm-runner-provider.md` to implement it task-by-task.
