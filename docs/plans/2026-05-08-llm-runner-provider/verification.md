# LLM Runner Provider Verification

evaluator_invocation_id: 8681ED40-0037-48B4-A9A5-A465355B152A
workflow_uuid: 00abf53d-b19f-4e7d-9bcc-1444798fda7d
artifact_dir: /Users/mizelan/Documents/GitHub/Horizon/docs/plans/2026-05-08-llm-runner-provider
repair_round: 5
verdict: pass
final_refresh_admitted: true

## Phase 1 - Role Isolation And Delivery/Proof Check

Role isolation: pass. This evaluator inspected the required context files, workflow artifacts, active plan/design documents, code, tests, docs, and recorded proof evidence directly. It did not rerun final_refresh, the full suite, live runner probes, or long-running gates.

Delivery/proof check: pass. Repair round 5 addressed the recorded final_refresh failures and left no evaluator-blocking proof gap after cheap structural review.

- PR-1: verified from recorded blocking proof evidence plus code/test inspection. `AIProvider.LLM_RUNNER`, optional `AIConfig.api_key_env`, and `create_ai_client` runner factory selection are present.
- PR-2: verified from recorded blocking proof evidence plus code inspection. SDK providers still require explicit API key environment configuration through `_required_api_key`.
- PR-3: verified from recorded blocking proof evidence plus test/code inspection. Runner subprocess tests cover argv, stdin, normalized JSON parsing, usage recording, invalid JSON, and non-success failure handling.
- PR-4: verified from recorded blocking proof evidence plus wizard/MCP inspection. `llm_runner` no longer requires a Horizon-owned AI key env at setup or MCP validation.
- PR-5: verified from recorded blocking proof evidence plus analyzer test inspection. Runner text is covered for parseable analysis JSON and non-JSON fallback.
- PR-6: verified from sprint history and recorded evidence. Targeted documentation diff hygiene passed.
- PR-eval-1: verified. Recorded repair_focus evidence passed with `9 passed`, and the full suite later passed. Qualitative inspection confirms the cross-module test exercises `AIConfig`, `create_ai_client`, `LLMRunnerClient.complete`, and `ContentAnalyzer`, mocking only `asyncio.create_subprocess_exec` as the external subprocess edge.
- PR-eval-2: verified by subsumption. The exact focused command is not separately listed in round 5 evidence, but `uv run pytest -q` passed the full suite after the pytest environment repair, which includes the MiniMax and Azure compatibility tests.
- PR-eval-3: verified from recorded final_refresh evidence. `uv run pytest -q` exited 0; summary says the full suite passed.
- PR-eval-4: verified by semantic scan evidence supplied for repair round 5 and evaluator cheap scan. Expected SDK/doc `api_key_env` hits remain; no runner secret field, generic env passthrough, Authorization header, or child-process env injection was found in the runner path.
- PR-eval-5: verified from recorded final_refresh evidence. `git diff --check` exited 0.
- PR-eval-6: verified from recorded final_refresh evidence. `command -v llm-runner && llm-runner probe --help` exited 0 and proves the installed binary plus current probe help contract; live provider probe remains environment/CLI capability evidence because the installed runner does not expose the older provider/json probe flags.

Satisfied blocking_proofs: PR-1, PR-2, PR-3, PR-4, PR-5, PR-6.

Satisfied final_refresh/repair proofs: PR-eval-1, PR-eval-2 by full-suite subsumption, PR-eval-3, PR-eval-4 semantic scan, PR-eval-5, PR-eval-6, repair-round-5-focused-mcp-smoke, repair-round-5-pytest-env-proof, repair-round-5-stale-provider-probe-scan.

## Phase 1.5 - State Integrity And Control Plane

State integrity: pass for evaluator closeout, with non-blocking terminal-sync drift.

- `wf-state.json` matches the workflow_uuid, has `round: 5`, `current_step: evaluator`, `final_refresh.status: not_started`, `active_wave: null`, and `remaining_waves: []`.
- `.feature-workflow-run.json` matches the workflow_uuid, has `phase: completed`, `repair_state.round: 5`, `repair_state.outcome: completed`, and `remaining_waves: []`.
- `.feature-workflow-run.json` records repair round 5 red/green evidence for MCP smoke, topic-dedup fake contract, runner probe contract, pytest environment, full suite, runner CLI help, and diff hygiene.
- `.feature-workflow-sprint.json.status` remains `planned`, and its planner-time `remaining_waves` list is still populated. This is not a product-code blocker for evaluator pass, but terminal closeout must sync sprint/state/run surfaces before claiming workflow completion.
- `wf-state.json.completed_waves` lists only the original planned waves, while `.feature-workflow-run.json.completed_waves` also lists repair waves. This is acceptable for evaluator pass because both surfaces agree no wave remains, but it is a closeout readability risk.

Control-plane consistency: pass for evaluator verdict. Completion consistency is not yet satisfied because the orchestrator-owned terminal fields have not been advanced to `convergence_done` / `completed`.

## Phase 2 - Cheap Structural Scan

Verdict driver: pass.

Findings:

1. Source spoof / authority inversion: not found. `LLMRunnerClient` invokes `asyncio.create_subprocess_exec` with direct argv, stdin/stdout/stderr pipes, no shell string, and no explicit child `env` passthrough.
2. Proof tier misclassification: not found. PR-1 through PR-6 remain targeted `blocking_proof`; PR-eval-1 through PR-eval-6 remain `final_refresh`. Repair round 5 `repair_focus` proofs are scoped to the final_refresh failures.
3. Incomplete runner/provider metadata: not found in active product/design surfaces. `AIConfig` exposes `llm_runner_command: str = "llm-runner"` and `llm_runner_provider: Optional[str] = None`; `LLMRunnerClient` appends `run`, optional `--provider`, `--model`, and `--json`.
4. Stale docs/control-plane mismatch: no active implementation/doc blocker. Stale `runner_*` examples remain only in the explicitly historical/non-authoritative root plan. Active design, approved sprint plan, docs, and code use `llm_runner_command` / `llm_runner_provider`.
5. Wave split mismatch: none. Four planned waves do not require a `wave_split_justification`.
6. Missing `wave_split_justification` when wave count > 6: not applicable.

## Phase 2 Planner Feedback

task_class accuracy: accurate. This is a multi-surface integration task spanning model config, client factory, subprocess execution, operator validation, analyzer behavior, docs, and final proof environment.

wave_split_quality: good. Four waves isolate config/factory, subprocess protocol, operator/analyzer surfaces, and docs/final proof without excessive fragmentation.

key-patterns coverage: acceptable after repairs. Original planning missed stale schema and command-shape drift, but the repair sequence added negative stale-token scans and positive implementation-alignment scans.

files_to_read completeness: acceptable for evaluator pass. Evaluation covered the required context files, active design, approved plan, root historical plan, run/sprint/state artifacts, product code, tests, and docs.

## Missing Proofs

missing_proofs: []

Notes:

- PR-eval-2 was not recorded as a separate focused command in round 5, but it is covered by the recorded full-suite pass.
- PR-eval-4 was not rerun by this evaluator. The supplied semantic scan evidence and this cheap structural scan are sufficient for evaluator pass.

## Required Follow-ups

Blocking required_followups: []

Non-blocking closeout follow-ups:

- Sync terminal control-plane surfaces after the orchestrator accepts this evaluator pass: `wf-state.json.current_step = convergence_done`, `wf-state.json.terminal_status = completed`, `.feature-workflow-run.json` final_refresh status/result, `.feature-workflow-sprint.json.status = completed`, and matching verification top-level verdict.
- Preserve the root plan's historical/non-authoritative warning until the stale `runner_*` examples are archived or rewritten, so future agents do not treat that file as implementation authority.

## Risks

- Medium: terminal closeout would be misleading if control-plane surfaces remain in planner/evaluator state after this pass. Escalated to non-blocking closeout follow-up because it affects completion readability, not product correctness.
- Medium: the root-level same-topic plan still contains stale `runner_*` examples. The historical/non-authoritative banner makes this non-blocking, but it remains a future-agent drift risk.
- Low: PR-eval-4 is a semantic grep proof with expected SDK/docs hits. Future reviewers must not treat non-empty output as a failure without checking whether hits belong to SDK providers rather than the runner path.

## Proof Tier Findings

- No proof tier misclassification remains.
- PR-eval-1's integration-capable proof is admissible because Horizon-side config, factory, client, and analyzer remain real while only the external subprocess edge is mocked.
- PR-eval-6 is correctly final_refresh/CLI-contract evidence. It proves local binary availability and current help contract; it does not overclaim live provider compatibility.

## Final Refresh Evidence Assessment

final_refresh_admitted: true

Reason: all blocking proofs are satisfied; repair round 5 records focused red/green evidence for the MCP smoke failures, pytest environment failure, and runner probe contract failure; recorded final_refresh evidence shows the full suite, runner CLI-contract proof, and diff hygiene passed; semantic PR-eval-4 inspection reports no runner secret/generic env passthrough leak; cheap structural scan found no source spoof, authority inversion, active stale schema, or proof-tier blocker.

## Codex App Canonical Refresh

verdict: pass

Canonical runner config:

- `provider`: `llm_runner`
- `model`: `gpt-5.5`
- `llm_runner_command`: `llm-runner`
- `llm_runner_provider`: `codex`

Fresh evidence:

- `llm-runner run --provider codex --model gpt-5.5 --json`: exit 0, `status: succeeded`, `provider: codex`, `model: gpt-5.5`.
- Horizon `AIConfig -> create_ai_client -> ContentAnalyzer`: exit 0, returned `score: 8.0`, `reason: canonical codex ok`, `summary: analyzer ok`, `tags: ["codex", "live"]`.
- Horizon MCP `validate_config` with Codex runner config: exit 0, returned `provider: llm_runner`, `api_key_env: null`, `missing_env: []`.
- Horizon CLI no-content boot with Codex runner config: exit 0, reached `No new content found. Exiting.`
- `uv run pytest tests/test_llm_runner_client.py tests/test_setup_wizard.py tests/test_mcp_service_smoke.py tests/test_analyzer.py -q`: exit 0, `21 passed`.
- `uv run pytest -q`: exit 0, full suite passed.
- `git diff --check`: exit 0.

Ollama is not required for the canonical Horizon proof. Other provider names remain runner-owned choices outside Horizon, but the verified service path is Codex app via `llm-runner`.

Satisfied blocking_proof list: PR-1, PR-2, PR-3, PR-4, PR-5, PR-6.

Satisfied final_refresh list: PR-eval-1, PR-eval-2 by full-suite subsumption, PR-eval-3, PR-eval-4 semantic scan, PR-eval-5, PR-eval-6.

## Self-Reflection Quality Check

Independence check: I did not rely on generator summaries alone. I inspected the required context files, state/run/sprint artifacts, plans, active design, historical root plan, existing verification history, implementation code, tests, docs, and cheap structural scan output.

Severity calibration review: `04-evaluator-calibration.md` says mock-heavy integration overclaims and active schema drift are blocking. The current PR-eval-1 proof crosses real Horizon modules, and active schema drift is repaired. Remaining drift is historical/non-authoritative or terminal closeout state, so it is non-blocking.

Cross-run pattern check: I added a pattern for `uv run pytest` resolving to a system pytest when pytest is optional-only, because repair round 5 showed this can create false dependency diagnoses in final_refresh.

Blind spot disclosure: I did not rerun pytest, full final_refresh, or live gates by instruction. PR-eval-2 was accepted by full-suite subsumption rather than an exact separate focused command.

Next time behavioral change: For final_refresh repair, check the command environment (`uv run pytest --version --version` or equivalent) before diagnosing dependency declarations.

Design gap analysis: No evaluator-blocking design gap remains. The remaining work is terminal control-plane synchronization and future cleanup of stale historical examples.
