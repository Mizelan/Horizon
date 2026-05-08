# Sprint History

## 2026-05-07 - llm-runner provider generator waves complete

Result: completed generator wave sequence through `wave-4-docs-boundary-final-refresh`; evaluator and orchestrator final_refresh remain the next workflow stages.

- Wave 1 added the `llm_runner` provider model/factory surface and SDK missing-key guard coverage.
- Wave 2 implemented the subprocess JSON protocol boundary for `LLMRunnerClient`.
- Wave 3 removed universal `api_key_env` assumptions from wizard/MCP operator surfaces and proved analyzer compatibility.
- Wave 4 documented the CLI-owned credential boundary in `docs/configuration.md`, `README.md`, and `README_zh.md`; `PR-6` passed with `git diff --check -- docs/configuration.md README.md README_zh.md`.

Self-reflection: The generator preserved the final_refresh boundary and ran only the active wave's blocking proof. A key planning gap remains that the loose root plan and approved artifact plan use different runner field names; future planner output should keep one canonical plan path and one canonical config vocabulary before generator dispatch.

## 2026-05-08 - repair round 2 evaluator follow-ups

Result: repaired evaluator-blocking proof contract gaps for `repair-round-2-evaluator-findings`; remaining_waves stays empty and final_refresh remains unrun by generator.

- Added `tests/test_llm_runner_client.py::test_llm_runner_client_integrates_config_factory_subprocess_and_analyzer`, which exercises `AIConfig`, `create_ai_client`, `LLMRunnerClient.complete`, and `ContentAnalyzer` together while mocking only the external subprocess edge.
- Updated PR-eval-1 in the approved sprint artifacts to name that integration-capable proof and to use the focused MCP runner validation test instead of the broad mock-heavy smoke file.
- Marked the duplicate root plan as historical/non-authoritative for runner config fields; approved artifacts and implementation use `llm_runner_command` and `llm_runner_provider`.
- Updated the sprint feature checklist from pending to completed for generator closeout, while leaving orchestrator final_refresh as the next stage.

Self-reflection: The first repair_focus command was still too broad because it included the whole MCP smoke file and pulled in unrelated existing failures (`feedparser` import and a legacy async mock mismatch). The corrected proof command is narrower and better aligned with the evaluator's proof-intent: real Horizon module path where needed, external subprocess mocked only at the system edge, and no full final_refresh suite in generator.

## 2026-05-08 - repair round 3 design schema follow-up

Result: repaired evaluator-blocking design schema drift for `repair-round-3-design-schema`; remaining_waves stays empty and final_refresh remains unrun by generator.

- Aligned the active design artifact's Interfaces section to the approved `llm_runner_command` / `llm_runner_provider` schema.
- Removed active design guidance for stale standalone runner config fields; provider knobs, timeout policy, heartbeat handling, and raw event storage stay owned by the local `llm-runner` CLI.
- Recorded repair round 3 checkpoint evidence in `.feature-workflow-run.json` and ran only the requested repair_focus proofs.

Self-reflection: The evaluator's pattern was correct: stale-field scans must include every markdown artifact in the active artifact directory. The required `rg` pattern also matches the approved `llm_runner_provider` substring, so future scans should add a semantic review note or use stricter boundaries for machine-only stale-field checks.

## 2026-05-08 - repair round 4 command schema follow-up

Result: repaired evaluator-blocking command schema drift for `repair-round-4-command-schema`; remaining_waves stays empty and final_refresh remains unrun by generator.

- Updated the active design artifact so `llm_runner_command` is a string command name defaulting to `"llm-runner"`, matching `AIConfig.llm_runner_command: str`.
- Recorded that `LLMRunnerClient` owns argv construction by appending `run`, `--model`, and `--json` when building the subprocess command.
- Ran only the requested repair_focus grep/diff proofs and updated `.feature-workflow-run.json` checkpoint evidence.

Self-reflection: Repair round 3 correctly removed stale field names but missed the field type/default semantics. For future schema repairs, the proof should include both a stale-token absence scan and a positive implementation-alignment scan against the active design wording before final_refresh admission.

## 2026-05-08 - repair round 5 final_refresh failures

Result: repaired the final_refresh failures for `repair-round-5-final-refresh-failures`; remaining_waves stays empty and focused plus full test proofs now pass.

- Confirmed `feedparser` was already declared in project dependencies; the actual failure was `uv run pytest` resolving to system pytest because pytest was only an optional extra. Added the uv default dev dependency group and refreshed `uv.lock`.
- Updated the MCP topic-dedup fake to match the product async `merge_topic_duplicates` contract.
- Repaired PR-eval-6 to prove the installed `llm-runner` binary and current `probe --help` contract without modifying the sibling runner repo.
- Recorded focused MCP smoke, full suite, runner proof, stale probe-command scan, pytest environment proof, and `git diff --check` in `.feature-workflow-run.json`.

Self-reflection: The earlier repair note correctly named the MCP failures but missed the command environment detail: `uv run pytest` can still fall through to a system executable when the project environment lacks pytest. Future final_refresh plans should either declare default dev groups for plain `uv run pytest` or make the proof command explicit with the required extra/group.
