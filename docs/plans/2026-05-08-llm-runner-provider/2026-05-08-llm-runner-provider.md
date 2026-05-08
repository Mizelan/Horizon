# LLM Runner Provider Sprint Plan

## Sprint Scope

Implement `llm_runner` as a subprocess-only Horizon AI provider. The sprint changes the config model, AI client factory, runner client, setup wizard, MCP validation, analyzer coverage, and user-facing docs. Existing SDK providers must keep their current behavior except for the safer explicit guard when `api_key_env` is missing.

## Feature Checklist

- F-1: Add `llm_runner` config and factory selection. Test steps: focused model and factory tests prove `AIConfig` accepts no API key env for `llm_runner`, and `create_ai_client` returns the runner client. Status: completed. Proof mapping: PR-1, PR-eval-3.
- F-2: Preserve SDK provider API-key error contract. Test steps: OpenAI and Anthropic missing `api_key_env` cases raise provider-specific `ValueError`, while existing Azure and MiniMax tests still pass. Status: completed. Proof mapping: PR-2, PR-eval-2.
- F-3: Implement runner subprocess success and failure behavior. Test steps: mocked subprocess verifies argv, stdin, normalized JSON parsing, usage handling, non-success status, and invalid JSON failure. Status: completed. Proof mapping: PR-3, PR-eval-3.
- F-4: Remove API-key assumption from setup wizard and MCP validation. Test steps: wizard tests cover no key prompt and recommendation availability; MCP smoke covers no missing env for `llm_runner`. Status: completed. Proof mapping: PR-4, PR-eval-3.
- F-5: Verify analyzer compatibility with runner text. Test steps: analyzer accepts parseable runner text and falls back on non-JSON text. Status: completed. Proof mapping: PR-5, PR-eval-3.
- F-6: Document provider boundary and run final proof. Test steps: docs mention subprocess-only CLI-owned credentials, boundary scan finds no runner secret fields, and PR-eval-1 includes an integration-capable Horizon path with only the external subprocess edge mocked. Status: completed. Proof mapping: PR-6, PR-eval-1, PR-eval-5, PR-eval-6.

## Wave 1 - Config Model, Factory, And SDK Guard

files_to_modify:

- src/models.py (add `llm_runner` provider value, make `api_key_env` optional, add explicit runner config fields)
- src/ai/client.py (add SDK API-key guard helper, add runner client shell, add factory branch)
- tests/test_llm_runner_client.py (create focused model, factory, and SDK missing-key regression tests)

files_to_read:

- src/models.py; key-patterns: `AIProvider`, `AIConfig`, Pydantic v2 field defaults, current `api_key_env` required shape
- src/ai/client.py; key-patterns: `AIClient.complete`, provider constructors, repeated SDK `os.getenv(config.api_key_env)` pattern, `create_ai_client`
- tests/test_minimax_client.py; key-patterns: existing missing API key expectations and factory tests
- tests/test_azure_client.py; key-patterns: existing Azure endpoint and key validation expectations

description:

Start with tests that define the provider enum, optional `api_key_env`, factory selection, and SDK provider regression contract. Then add the minimum model and factory surface. SDK providers should use one shared required-key helper so `api_key_env=None` produces a clear provider-specific `ValueError`, not a low-level `TypeError`.

blocking proof:

- PR-1: `uv run pytest tests/test_llm_runner_client.py::test_llm_runner_config_does_not_require_api_key_env tests/test_llm_runner_client.py::test_factory_creates_llm_runner_client -q`
- PR-2: `uv run pytest tests/test_llm_runner_client.py tests/test_minimax_client.py tests/test_azure_client.py -q`

## Wave 2 - Runner Subprocess Protocol

files_to_modify:

- src/ai/client.py (implement `LLMRunnerClient` subprocess execution, argv construction, prompt construction, result parsing, failure handling, usage recording)
- tests/test_llm_runner_client.py (add success, non-success status, and invalid JSON tests)

files_to_read:

- src/ai/client.py; key-patterns: async client pattern, `record_usage`, provider labels, exception style
- tests/test_llm_runner_client.py; key-patterns: helper config fixture from Wave 1, monkeypatch pattern for subprocess
- src/ai/tokens.py; key-patterns: `record_usage` provider label and token count expectations
- docs/plans/2026-05-08-llm-runner-provider.md; key-patterns: normalized result JSON boundary, subprocess-only/no secret boundary, optional live smoke semantics

description:

Implement the actual runner client after the factory surface exists. The client must call `asyncio.create_subprocess_exec` with direct argv, never shell strings. It must send both system and user prompt text through stdin, parse the final runner JSON result, reject invalid JSON and non-success statuses, and return only the normalized `text` value.

blocking proof:

- PR-3: `uv run pytest tests/test_llm_runner_client.py -q`

## Wave 3 - Operator Surfaces And Analyzer Compatibility

files_to_modify:

- src/setup/wizard.py (skip API-key prompt for `llm_runner`, ask runner provider, centralize AI recommendation availability)
- tests/test_setup_wizard.py (create wizard tests if absent)
- src/mcp/service.py (only require configured env vars when present)
- tests/test_mcp_service_smoke.py (add MCP validation case for `llm_runner`)
- tests/test_analyzer.py (add runner text parse and fallback coverage)
- src/ai/analyzer.py (modify only if the new analyzer tests expose a real fallback regression)

files_to_read:

- src/setup/wizard.py; key-patterns: provider list from enum, `Prompt.ask`, immediate missing key warning, `main` AI recommendation branch
- src/mcp/service.py; key-patterns: `validate_config`, `missing_env`, returned `ai` object, email and webhook env validation
- tests/test_mcp_service_smoke.py; key-patterns: tmp config file pattern, `HorizonPipelineService`, async validation smoke
- tests/test_analyzer.py; key-patterns: `_make_item`, `SimpleNamespace` fake clients, `asyncio.run` style
- src/ai/analyzer.py; key-patterns: `ContentAnalyzer._analyze_item`, `parse_json_response`, fallback fields on parse failure

description:

Remove remaining universal `api_key_env` assumptions at Horizon operator surfaces. The setup wizard should configure runner-specific provider selection without warning about a Horizon API key. MCP validation should keep reporting email, webhook, and source env gaps while ignoring absent AI key env for `llm_runner`. Analyzer coverage should prove the runner client's returned text works with existing parsing and fallback behavior.

blocking proof:

- PR-4: `uv run pytest tests/test_setup_wizard.py tests/test_mcp_service_smoke.py::test_validate_config_does_not_require_api_key_for_llm_runner -q`
- PR-5: `uv run pytest tests/test_analyzer.py -q`

## Wave 4 - Docs, Boundary Scan, And Final Refresh

files_to_modify:

- docs/configuration.md (add `llm-runner` provider configuration section and credential ownership note)
- README.md (add short manual configuration note after the OpenAI example)
- README_zh.md (mirror the same meaning in Chinese)

files_to_read:

- docs/configuration.md; key-patterns: AI provider sections, JSON examples, `.env` language
- README.md; key-patterns: manual configuration section and supported provider summary language
- README_zh.md; key-patterns: Chinese manual configuration section and corresponding provider wording
- data/config.example.json; key-patterns: OpenAI remains default; JSON cannot carry comments, so do not change unless generator finds a strict need
- docs/plans/2026-05-08-llm-runner-provider.md; key-patterns: final verification commands, live smoke classification, placeholder scan intent

description:

Document the new provider without changing the default example config. The final pass must verify docs hygiene, focused test coverage, full test coverage, boundary scan, optional local runner probe, and control-plane consistency. Live smoke may be recorded as environment evidence when provider auth or account state is unavailable.

blocking proof:

- PR-6: `git diff --check -- docs/configuration.md README.md README_zh.md`
- PR-eval-5: `git diff --check`

final refresh proof:

- PR-eval-1: `uv run pytest tests/test_llm_runner_client.py::test_llm_runner_client_integrates_config_factory_subprocess_and_analyzer tests/test_setup_wizard.py tests/test_mcp_service_smoke.py::test_validate_config_does_not_require_api_key_for_llm_runner tests/test_analyzer.py -q`
- PR-eval-2: `uv run pytest tests/test_minimax_client.py tests/test_azure_client.py -q`
- PR-eval-3: `uv run pytest -q`
- PR-eval-4: `rg -n "api_key|auth_token|provider_secret|Authorization|generic env|env passthrough" src/ai src/models.py src/setup/wizard.py src/mcp/service.py docs/configuration.md README.md README_zh.md`
- PR-eval-6: `printf '{"score":8,"reason":"codex live ok","summary":"ok","tags":["codex"]}\n' | llm-runner run --provider codex --model gpt-5.5 --json`, proving the Codex app provider path succeeds through `llm-runner` without requiring an Ollama environment. Do not modify the sibling runner repo for this Horizon proof.

## Proof Requirements

- PR-1: Model and factory proof. Tier: blocking_proof. Evidence: focused tests for `llm_runner` config without `api_key_env` and factory creation.
- PR-2: SDK regression proof. Tier: blocking_proof. Evidence: focused runner client tests plus existing MiniMax and Azure tests prove SDK key behavior remains clear.
- PR-3: Runner protocol proof. Tier: blocking_proof. Evidence: mocked subprocess tests cover argv, stdin, success parse, usage, invalid JSON, and non-success failure.
- PR-4: Wizard and MCP proof. Tier: blocking_proof. Evidence: setup wizard and MCP validation tests prove no universal key-env assumption remains.
- PR-5: Analyzer proof. Tier: blocking_proof. Evidence: analyzer tests prove parseable runner text is accepted and non-JSON text falls back.
- PR-6: Documentation proof. Tier: blocking_proof. Evidence: targeted doc diff hygiene passes.
- PR-eval-1: Integration-capable runner proof plus focused operator/analyzer suite. Tier: final_refresh. Evidence: the runner test exercises `AIConfig`, `create_ai_client`, `LLMRunnerClient.complete`, and `ContentAnalyzer` together while mocking only the external subprocess edge; wizard, MCP, and analyzer focused tests pass alongside it.
- PR-eval-2: SDK compatibility refresh. Tier: final_refresh. Evidence: MiniMax and Azure compatibility tests pass after `api_key_env` becomes optional.
- PR-eval-3: Full test suite. Tier: final_refresh. Evidence: `uv run pytest -q` passes.
- PR-eval-4: Secret-boundary scan. Tier: final_refresh. Evidence: scan output contains only existing SDK key handling and no runner secret fields or generic env passthrough.
- PR-eval-5: Diff hygiene. Tier: final_refresh. Evidence: `git diff --check` passes for all changes.
- PR-eval-6: Local runner availability and Codex provider live smoke. Tier: final_refresh. Evidence: `llm-runner run --provider codex --model gpt-5.5 --json` exits 0 with `status: succeeded`; Ollama is not required for this Horizon proof.

## Expensive Gate Policy

expensive_gate_policy: final_refresh_once_per_successful_repair_cycle

Generator waves should run only their blocking proofs. Full tests, boundary scan, and runner probe belong to final refresh after evaluator pass. If final refresh fails, run a focused repair wave using the failing proof as `repair_focus` before rerunning final refresh.

## Control-Plane Consistency

Before evaluator dispatch:

- `.feature-workflow-sprint.json` status is `planned`, `approved` is true, waves and `remaining_waves` are non-empty at planner completion.
- `.feature-workflow-run.json` completed and remaining waves match `wf-state.json` for the stage being dispatched.
- The union of all wave `files_to_modify` equals sprint `changed_paths`.

Before final refresh:

- `remaining_waves` is empty in `.feature-workflow-run.json`.
- Evaluator verdict is pass in `verification.md`.
- All `blocking_proof` items have current proof records.
- Final refresh commands are run once for the successful repair cycle.

Before completion:

- `wf-state.json.current_step` is `convergence_done`.
- `wf-state.json.terminal_status` is `completed`.
- `.feature-workflow-run.json.final_refresh.status` is passed or explicitly records an allowed environment-class live-smoke skip for PR-eval-6 only.
- `.feature-workflow-sprint.json` is updated to completed by the orchestrator after final refresh.
- `verification.md` contains final evaluator verdict pass.

## Implementation Boundaries

Do not add Horizon-managed credentials for `llm_runner`.

Do not use shell execution for runner subprocess calls.

Do not change `data/config.example.json` unless implementation discovers a strict compatibility requirement; docs are the preferred example surface.

Do not modify the sibling `llm-runner` repository unless Horizon TDD or `llm-runner probe` proves a runner protocol defect. Missing auth, quota, or provider login is not a Horizon defect.
