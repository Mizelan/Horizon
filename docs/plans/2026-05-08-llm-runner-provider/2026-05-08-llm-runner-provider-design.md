# LLM Runner Provider Design

## Goal

Add a Horizon AI provider named `llm_runner` that lets Horizon score and summarize news through a local `llm-runner` CLI subprocess. The provider must fit the existing `AIClient.complete()` abstraction while keeping Horizon out of provider credential ownership.

## Architecture

The new provider is a parallel client path, not a replacement for existing SDK providers.

ASCII flow:

Horizon config
  -> AIConfig provider: llm_runner
  -> create_ai_client
  -> LLMRunnerClient
  -> asyncio subprocess argv
  -> llm-runner run --json
  -> normalized result JSON
  -> result text
  -> ContentAnalyzer JSON parser

The boundary is subprocess-only. Horizon builds an argv list directly and writes the combined system and user prompt to stdin. Horizon reads the final normalized JSON object emitted by `llm-runner`, verifies a success status and process exit, records usage when available, and returns only the `text` field to the analyzer.

## Interfaces

`AIProvider` gains one value: `llm_runner`.

`AIConfig` keeps existing SDK provider fields and makes `api_key_env` optional because it is not valid for `llm_runner`. SDK providers still require an API key environment variable at client creation time and should raise a clear `ValueError` when it is omitted or unset.

Runner-specific config lives under the approved `llm_runner_*` fields:

- `llm_runner_command`: string command name used to launch the local runner, defaulting to `"llm-runner"`. `LLMRunnerClient` appends `run`, `--model`, and `--json` when it builds the subprocess argv.
- `llm_runner_provider`: provider selected by the local runner. The canonical Horizon verification path is `codex` with `gpt-5.5`; other provider names are runner-owned choices and are not required by Horizon.

Additional provider knobs, timeout policy, heartbeat handling, and raw event storage remain owned by the local `llm-runner` CLI and its own configuration. Horizon must not define parallel schema fields for those concerns.

The runner provider must not accept Horizon-managed API keys, auth tokens, provider secrets, Authorization headers, or generic child-process environment passthrough.

## Integration Points

`src/ai/client.py` owns the provider factory, SDK API-key guard, and `LLMRunnerClient`.

`src/models.py` owns config validation shape. The design intentionally keeps `api_key_env` optional at the model layer and restores SDK-specific required behavior at the client layer, where provider semantics are known.

`src/setup/wizard.py` must present `llm_runner` as a provider without prompting for an API key environment variable. AI source recommendations can be attempted for `llm_runner` because the local runner owns its own readiness and failures are already handled by the recommendation path.

`src/mcp/service.py` must not report `ai.api_key_env` as a missing environment variable when the selected provider omits it.

`src/ai/analyzer.py` should continue to parse JSON returned from any client. For runner text that is not parseable analysis JSON, existing fallback behavior should remain the user-visible safety net.

## Non-Goals

- Do not remove or rewrite existing OpenAI, Anthropic, Azure, Gemini, MiniMax, Ali, or Doubao clients.
- Do not make `llm_runner` the default in `data/config.example.json`.
- Do not add generic env passthrough, provider secret fields, or Horizon-owned runner credential injection.
- Do not import Go packages or SDK internals from the sibling `llm-runner` repository.
- Do not block Horizon integration completion on live provider account availability.

## Validation Surface

Validation must prove five boundaries:

- Model and factory: `llm_runner` config works without `api_key_env`; SDK providers still fail clearly when `api_key_env` is absent.
- Subprocess protocol: argv construction, stdin prompt delivery, success parsing, usage recording, invalid JSON failure, and non-success status failure.
- Operator surfaces: setup wizard and MCP config validation no longer assume every AI provider has an API key env var.
- Analyzer behavior: runner text that contains Horizon analysis JSON is accepted; non-JSON text falls back without crashing.
- Documentation and boundary scan: docs describe CLI-owned credentials, and no runner path introduces secret-bearing config fields or generic env passthrough.

## Control Plane Assumptions

`wf-state.json` remains the orchestrator-owned control-plane source of truth. The sprint contract describes planned waves and proofs; `.feature-workflow-run.json` will carry generator checkpoints and proof records; `verification.md` will carry evaluator verdicts. Before evaluator dispatch, the orchestrator should confirm completed and remaining waves agree between `wf-state.json` and `.feature-workflow-run.json`. Before final refresh, it should confirm evaluator pass, no remaining waves, and proof tiers are satisfied. Before completion, it should require final refresh pass, sprint status completion, and `verification.md` verdict pass.

## Design Assumptions Affecting Proof

The plan treats a failed live `llm-runner` smoke caused by missing auth, quota, or local provider account state as environment evidence, not a Horizon integration failure. Contract tests and local subprocess parsing are blocking; live provider compatibility is final-refresh evidence only when the local machine can satisfy provider readiness.
