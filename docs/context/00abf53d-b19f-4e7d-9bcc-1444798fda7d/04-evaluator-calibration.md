# Evaluator Calibration

## 2026-05-08 - llm-runner provider

- Calibration: mock-only or mock-heavy cross-module proof surfaces are blocking for Phase 2 when the plan claims integration coverage.
- Severity: classify as blocking even when all recorded blocking_proof commands passed, because final_refresh would otherwise certify a proof that cannot establish its stated claim.
- Secondary calibration: duplicate same-topic plan files with conflicting schema names are at least medium risk and become blocking when future repair agents can plausibly follow the stale plan.
- Repair-round calibration: after one stale plan is demoted, any active sibling design artifact that still advertises the stale schema remains blocking for final_refresh admission because it can reintroduce the same wrong authority path.
- Repair-round 3 calibration: after stale field names are repaired, an active design artifact that still advertises a conflicting field type or default is also blocking when it can cause future repair agents to write config that the implemented model rejects.
- Repair-round 4 calibration: once the active design artifact, implementation schema, docs, and positive argv ownership scan agree on `llm_runner_command` as a string command name, stale examples left only in an explicitly historical/non-authoritative root plan are non-blocking for evaluator pass, but remain a terminal-closeout risk to mention.
- Repair-round 5 calibration: final_refresh red/green evidence can pass when the original failure root cause is repaired and recorded, even if control-plane terminal fields are not yet advanced. Classify unresolved `wf-state.json`/sprint completion drift as non-blocking closeout risk unless it hides missing proof evidence or product-code uncertainty.
