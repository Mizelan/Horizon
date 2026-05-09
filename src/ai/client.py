"""AI client abstraction supporting multiple providers."""

import asyncio
import json
import os
import sys
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI, AsyncAzureOpenAI
from google import genai
from google.genai import types

from ..models import AIConfig, AIProvider
from .tokens import record_usage


def _required_api_key(config: AIConfig, provider_name: str) -> str:
    if not config.api_key_env:
        raise ValueError(f"api_key_env is required for {provider_name} provider")
    api_key = os.getenv(config.api_key_env)
    if not api_key:
        raise ValueError(f"Missing API key: {config.api_key_env}")
    return api_key


class AIClient(ABC):
    """Abstract base class for AI clients."""

    @abstractmethod
    async def complete(
        self,
        system: str,
        user: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate completion from AI model.

        Args:
            system: System prompt
            user: User prompt
            temperature: Optional sampling temperature override
            max_tokens: Optional maximum tokens override

        Returns:
            str: Generated completion text
        """
        pass

    async def preflight(self) -> Optional[str]:
        """Check if the AI client is ready before running the pipeline.

        Returns:
            None if ready, or an error message string explaining what's wrong.
        """
        return None  # Most providers rely on env-var validation at first call


class AnthropicClient(AIClient):
    """Client for Anthropic Claude models."""

    def __init__(self, config: AIConfig):
        """Initialize Anthropic client.

        Args:
            config: AI configuration
        """
        self.config = config

        api_key = _required_api_key(config, "anthropic")

        kwargs = {"api_key": api_key}
        if config.base_url:
            kwargs["base_url"] = config.base_url

        self.client = AsyncAnthropic(**kwargs)
        self.model = config.model
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens

    async def complete(
        self,
        system: str,
        user: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate completion using Claude.

        Args:
            system: System prompt
            user: User prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            str: Generated text
        """
        temperature = self.temperature if temperature is None else temperature
        max_tokens = self.max_tokens if max_tokens is None else max_tokens

        message = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}]
        )
        usage = getattr(message, "usage", None)
        if usage is not None:
            record_usage(
                "anthropic",
                input_tokens=getattr(usage, "input_tokens", 0),
                output_tokens=getattr(usage, "output_tokens", 0),
            )
        return message.content[0].text


class OpenAIClient(AIClient):
    """Client for OpenAI models."""

    def __init__(self, config: AIConfig):
        """Initialize OpenAI client.

        Args:
            config: AI configuration
        """
        self.config = config

        api_key = _required_api_key(config, "openai")

        kwargs = {"api_key": api_key}
        if config.base_url:
            kwargs["base_url"] = config.base_url

        self.client = AsyncOpenAI(**kwargs)
        self.model = config.model
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens

    async def complete(
        self,
        system: str,
        user: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate completion using OpenAI.

        Args:
            system: System prompt
            user: User prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            str: Generated text
        """
        temperature = self.temperature if temperature is None else temperature
        max_tokens = self.max_tokens if max_tokens is None else max_tokens

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        usage = getattr(response, "usage", None)
        if usage is not None:
            record_usage(
                "openai",
                input_tokens=getattr(usage, "prompt_tokens", 0),
                output_tokens=getattr(usage, "completion_tokens", 0),
            )
        return response.choices[0].message.content


class AzureOpenAIClient(AIClient):
    """Client for Azure OpenAI deployments.

    Uses the native AsyncAzureOpenAI client, which requires the deployment
    name (passed as `model`), azure_endpoint (resource base URL), and
    api_version. The deployment path is assembled internally by the SDK.
    """

    # Newer reasoning-series models reject legacy `max_tokens` and require
    # `max_completion_tokens` instead. Azure uses deployment names as `model`,
    # so a best-effort guess can be wrong for custom deployment aliases.
    _MODELS_REQUIRING_MAX_COMPLETION_TOKENS = ("o1", "o3", "o4", "gpt-5")

    def __init__(self, config: AIConfig):
        """Initialize Azure OpenAI client.

        Args:
            config: AI configuration
        """
        self.config = config

        api_key = _required_api_key(config, "azure")
        if not config.azure_endpoint_env:
            raise ValueError("azure_endpoint_env is required for azure provider")
        azure_endpoint = os.getenv(config.azure_endpoint_env)
        if not azure_endpoint:
            raise ValueError(f"Missing Azure endpoint: {config.azure_endpoint_env}")
        if not config.api_version:
            raise ValueError("api_version is required for azure provider")

        self.client = AsyncAzureOpenAI(
            api_key=api_key,
            azure_endpoint=azure_endpoint,
            api_version=config.api_version,
        )
        self.model = config.model
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens
        self._use_max_completion_tokens = any(
            config.model.startswith(prefix)
            for prefix in self._MODELS_REQUIRING_MAX_COMPLETION_TOKENS
        )

    async def complete(
        self,
        system: str,
        user: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate completion using Azure OpenAI.

        Args:
            system: System prompt
            user: User prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            str: Generated text
        """
        temperature = self.temperature if temperature is None else temperature
        max_tokens = self.max_tokens if max_tokens is None else max_tokens

        try:
            response = await self._create_completion(
                system=system,
                user=user,
                temperature=temperature,
                max_tokens=max_tokens,
                use_max_completion_tokens=self._use_max_completion_tokens,
            )
        except Exception as exc:
            fallback = self._token_fallback_mode(str(exc))
            if fallback is None:
                raise

            self._use_max_completion_tokens = fallback
            response = await self._create_completion(
                system=system,
                user=user,
                temperature=temperature,
                max_tokens=max_tokens,
                use_max_completion_tokens=fallback,
            )

        usage = getattr(response, "usage", None)
        if usage is not None:
            record_usage(
                "openai",
                input_tokens=getattr(usage, "prompt_tokens", 0),
                output_tokens=getattr(usage, "completion_tokens", 0),
            )
        return response.choices[0].message.content

    async def _create_completion(
        self,
        *,
        system: str,
        user: str,
        temperature: float,
        max_tokens: int,
        use_max_completion_tokens: bool,
    ):
        tokens_kwarg = (
            {"max_completion_tokens": max_tokens}
            if use_max_completion_tokens
            else {"max_tokens": max_tokens}
        )
        return await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            response_format={"type": "json_object"},
            **tokens_kwarg,
        )

    @staticmethod
    def _token_fallback_mode(message: str) -> Optional[bool]:
        lowered = message.lower()
        if "max_completion_tokens" in lowered and "max_tokens" in lowered:
            return True
        if "max_tokens" in lowered and "max_completion_tokens" not in lowered:
            return False
        return None


class MiniMaxClient(AIClient):
    """Client for MiniMax models via OpenAI-compatible API."""

    def __init__(self, config: AIConfig):
        """Initialize MiniMax client.

        Args:
            config: AI configuration
        """
        self.config = config

        api_key = _required_api_key(config, "minimax")

        kwargs = {
            "api_key": api_key,
            "base_url": config.base_url or "https://api.minimax.io/v1",
        }

        self.client = AsyncOpenAI(**kwargs)
        self.model = config.model
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens

    async def complete(
        self,
        system: str,
        user: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate completion using MiniMax.

        MiniMax requires temperature in (0.0, 1.0] and does not support
        response_format, so we rely on prompt engineering for JSON output.

        Args:
            system: System prompt
            user: User prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            str: Generated text
        """
        temperature = self.temperature if temperature is None else temperature
        max_tokens = self.max_tokens if max_tokens is None else max_tokens

        # MiniMax temperature must be in (0.0, 1.0]; clamp 0 to a small value
        if temperature <= 0:
            temperature = 0.01

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        usage = getattr(response, "usage", None)
        if usage is not None:
            record_usage(
                "minimax",
                input_tokens=getattr(usage, "prompt_tokens", 0),
                output_tokens=getattr(usage, "completion_tokens", 0),
            )
        return response.choices[0].message.content


class AliClient(AIClient):
    """Client for Alibaba DashScope (OpenAI-compatible API)."""

    def __init__(self, config: AIConfig):
        """Initialize DashScope client.

        Args:
            config: AI configuration
        """
        self.config = config

        api_key = _required_api_key(config, "ali")

        kwargs = {
            "api_key": api_key,
            "base_url": config.base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1",
        }
        self.client = AsyncOpenAI(**kwargs)
        self.model = config.model
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens

    async def complete(
        self,
        system: str,
        user: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate completion using DashScope.

        Args:
            system: System prompt
            user: User prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            str: Generated text
        """
        temperature = self.temperature if temperature is None else temperature
        max_tokens = self.max_tokens if max_tokens is None else max_tokens

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content


class GeminiClient(AIClient):
    """Client for Google Gemini models."""

    def __init__(self, config: AIConfig):
        """Initialize Gemini client.

        Args:
            config: AI configuration
        """
        self.config = config

        api_key = _required_api_key(config, "gemini")

        self.client = genai.Client(api_key=api_key)
        self.model = config.model
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens

    async def complete(
        self,
        system: str,
        user: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate completion using Gemini.

        Args:
            system: System prompt
            user: User prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            str: Generated text
        """
        temperature = self.temperature if temperature is None else temperature
        max_tokens = self.max_tokens if max_tokens is None else max_tokens

        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=temperature,
                max_output_tokens=max_tokens,
                response_mime_type="application/json"
            )
        )
        usage = getattr(response, "usage_metadata", None)
        if usage is not None:
            total = getattr(usage, "total_token_count", 0) or 0
            prompt = getattr(usage, "prompt_token_count", 0) or 0
            completion = max(0, total - prompt)
            record_usage("gemini", input_tokens=prompt, output_tokens=completion)
        return response.text


class LLMRunnerClient(AIClient):
    """Client shell for the subprocess-only llm-runner provider."""

    def __init__(self, config: AIConfig):
        self.config = config
        self.command = config.llm_runner_command
        self.provider = config.llm_runner_provider
        self.model = config.model
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens
        self.hang_window = config.llm_runner_hang_window
        self.heartbeat_interval = config.llm_runner_heartbeat_interval
        self.raw_event_dir = config.llm_runner_raw_event_dir
        self.trace_dir = config.llm_runner_trace_dir
        self._last_trace_path: str | None = None

    async def complete(
        self,
        system: str,
        user: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        args = self._build_args()
        prompt_bytes = self._build_prompt(system=system, user=user).encode("utf-8")

        def _run() -> dict[str, Any]:
            import subprocess
            proc = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = proc.communicate(input=prompt_bytes, timeout=self.config.llm_runner_timeout_seconds)
            # Parse stream JSON output (--stream-json produces one JSON event per line)
            terminal_result: dict[str, Any] | None = None
            for raw_line in stdout.decode("utf-8", errors="replace").splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                event_type = event.get("type")
                if event_type in ("run.completed", "run.failed"):
                    terminal_result = event.get("result") or {}
            if terminal_result is None:
                raise RuntimeError("llm-runner stream ended without a terminal event")
            terminal_result["_stdout"] = stdout
            terminal_result["_stderr"] = stderr
            terminal_result["_exit_code"] = proc.returncode
            return terminal_result

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, _run)
        stderr = result.pop("_stderr", b"")
        returncode = result.pop("_exit_code", 0)
        result = self._validate_result(result=result, stderr=stderr, returncode=returncode)
        usage = result.get("usage") or {}
        record_usage(
            "llm_runner",
            input_tokens=int(usage.get("input_tokens") or 0),
            output_tokens=int(usage.get("output_tokens") or 0),
        )
        return str(result.get("text") or "")

    async def preflight(self) -> Optional[str]:
        """Probe llm-runner with an empty prompt — fail-fast on config errors."""
        probe_args = [self.command, "run"]
        if self.provider:
            probe_args.extend(["--provider", self.provider])
        probe_args.extend(["--model", self.model, "--json"])
        process = await asyncio.create_subprocess_exec(
            *probe_args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        assert process.stdin is not None
        process.stdin.close()
        stdout, stderr = await process.communicate()
        try:
            result = json.loads(stdout)
        except json.JSONDecodeError:
            result = {}
        if result.get("status") == "config_error":
            reason = result.get("diagnostics", {}).get("reason", "unknown config error")
            return (f"llm-runner config error ({self.provider}/{self.model}): {reason}\n"
                    f"  Set the required credentials in your llm-runner config file.")
        return None


    def _build_args(self) -> list[str]:
        args = [self.command, "run"]
        if self.provider:
            args.extend(["--provider", self.provider])
        args.extend(["--model", self.model, "--stream-json"])
        if self.hang_window:
            args.extend(["--hang-window", self.hang_window])
        if self.heartbeat_interval:
            args.extend(["--heartbeat-interval", self.heartbeat_interval])
        raw_event_dir = self.raw_event_dir or str(Path(tempfile.gettempdir()) / "horizon-llm-runner-raw")
        args.extend(["--raw-event-dir", raw_event_dir])
        trace_path = self._new_trace_path()
        args.extend(["--trace-jsonl", trace_path])
        return args

    def _new_trace_path(self) -> str:
        trace_dir = Path(self.trace_dir or (Path(tempfile.gettempdir()) / "horizon-llm-runner-trace"))
        trace_dir.mkdir(parents=True, exist_ok=True)
        trace_file = tempfile.NamedTemporaryFile(
            prefix="trace-",
            suffix=".jsonl",
            dir=str(trace_dir),
            delete=True,
        )
        trace_path = trace_file.name
        trace_file.close()
        Path(trace_path).unlink(missing_ok=True)
        self._last_trace_path = trace_path
        return trace_path

    @staticmethod
    def _build_prompt(*, system: str, user: str) -> str:
        return f"System:\n{system}\n\nUser:\n{user}\n"

    async def _read_stream_result(self, stdout: asyncio.StreamReader) -> dict[str, Any]:
        terminal_result: dict[str, Any] | None = None
        async for raw_line in stdout:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"llm-runner returned invalid stream JSON: {line[:200]}") from exc

            event_type = event.get("type")
            if event_type == "diagnostic":
                diagnostics = event.get("diagnostics") or {}
                message = diagnostics.get("last_event") or event.get("message") or "waiting_for_provider"
                elapsed = event.get("elapsed_ms")
                suffix = f" ({elapsed}ms)" if isinstance(elapsed, int) else ""
                print(f"   llm-runner: {message}{suffix}", file=sys.stderr)
            elif event_type in ("run.completed", "run.failed"):
                terminal_result = event.get("result") or {}

        if terminal_result is None:
            raise RuntimeError("llm-runner stream ended without a terminal event")
        return terminal_result

    @staticmethod
    def _parse_result(*, stdout: bytes, stderr: bytes, returncode: int) -> dict[str, Any]:
        try:
            result = json.loads(stdout.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError("llm-runner returned invalid JSON") from exc

        status = result.get("status")
        if returncode != 0 or status != "succeeded":
            diagnostics = result.get("diagnostics") or {}
            reason = str(diagnostics.get("reason") or "").strip()
            stderr_text = stderr.decode("utf-8", errors="replace").strip()
            detail = reason or stderr_text or f"status={status} exit={returncode}"
            raise RuntimeError(f"llm-runner failed: {detail}")

        return result

    @staticmethod
    def _validate_result(*, result: dict[str, Any], stderr: bytes, returncode: int) -> dict[str, Any]:
        status = result.get("status")
        if returncode != 0 or status != "succeeded":
            diagnostics = result.get("diagnostics") or {}
            reason = str(diagnostics.get("reason") or "").strip()
            stderr_text = stderr.decode("utf-8", errors="replace").strip()
            trace_path = str(result.get("trace_event_path") or "").strip()
            raw_path = str(result.get("raw_event_path") or "").strip()
            evidence = " ".join(
                part for part in (f"trace={trace_path}" if trace_path else "", f"raw={raw_path}" if raw_path else "")
                if part
            )
            detail = reason or stderr_text or f"status={status} exit={returncode}"
            if evidence:
                detail = f"{detail} ({evidence})"
            raise RuntimeError(f"llm-runner failed: {detail}")
        return result


def create_ai_client(config: AIConfig) -> AIClient:
    """Factory function to create appropriate AI client.

    Args:
        config: AI configuration

    Returns:
        AIClient: Initialized AI client

    Raises:
        ValueError: If provider is not supported
    """
    if config.provider == AIProvider.ANTHROPIC:
        return AnthropicClient(config)
    elif config.provider == AIProvider.OPENAI:
        return OpenAIClient(config)
    elif config.provider == AIProvider.AZURE:
        return AzureOpenAIClient(config)
    elif config.provider == AIProvider.ALI:
        return AliClient(config)
    elif config.provider == AIProvider.GEMINI:
        return GeminiClient(config)
    elif config.provider == AIProvider.DOUBAO:
        return OpenAIClient(config)
    elif config.provider == AIProvider.MINIMAX:
        return MiniMaxClient(config)
    elif config.provider == AIProvider.LLM_RUNNER:
        return LLMRunnerClient(config)
    else:
        raise ValueError(f"Unsupported AI provider: {config.provider}")
