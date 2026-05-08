# YouTube Source Provider wf Execution Plan

planner_invocation_id: e949b4f1-5d26-4af6-93b8-cee64f214705
workflow_uuid: d590be5e-f6d3-4f81-a018-844ce4d101c0
status: planned
source_plan: docs/plans/2026-05-08-youtube-source-provider.md

## Execution Notes

This plan is implementation handoff only. Do not modify product code during planner execution. Generator should keep tests adjacent to each wave and use existing Horizon patterns over direct transcription from the source plan.

Expensive gates are final_refresh only. Normal generator waves run targeted blocking_proof commands and repair_focus commands if evaluator findings require them.

## Feature Checklist

- feature_id: F-1
  description: Add YouTube schema, dependency, scraper, config example, and deterministic scraper tests.
  test_steps: Validate config.example parsing; run tests/test_youtube.py.
  status: pending
  proof_mapping: PR-1, PR-2

- feature_id: F-2
  description: Wire YouTube into orchestrator dispatch, sub-source labels, MCP source filters, and MCP smoke tests.
  test_steps: Run tests/test_orchestrator.py and tests/test_mcp_service_smoke.py with youtube-specific cases.
  status: pending
  proof_mapping: PR-3, PR-4

- feature_id: F-3
  description: Teach setup wizard and recommendation surfaces to build, merge, dedupe, and count YouTube source recommendations.
  test_steps: Run tests/test_setup_wizard.py with youtube build/merge/count coverage.
  status: pending
  proof_mapping: PR-5

- feature_id: F-4
  description: Update user-facing docs, README surfaces, examples, and concrete data/config.json channel entry.
  test_steps: Validate Config parsing for data/config.json and scan docs for YouTube, yt-dlp, channel id, and youtube references.
  status: pending
  proof_mapping: PR-6, PR-7

- feature_id: F-5
  description: Prove final integration through source-only live fetch, full regression, and normal Horizon/Jekyll output.
  test_steps: Run full pytest, git diff check, live YouTube fetch, limited Horizon pipeline proof, and docs Jekyll build.
  status: pending
  proof_mapping: PR-8, PR-9, PR-10

## Wave 1 - Schema, Dependency, Scraper, And Unit Contract

files_to_modify:
- src/models.py
- src/scrapers/youtube.py
- tests/test_youtube.py
- pyproject.toml
- uv.lock
- data/config.example.json

files_to_read:
- src/models.py key-patterns: SourceType enum, Pydantic config models, SourcesConfig default_factory style, HttpUrl usage.
- src/scrapers/base.py key-patterns: BaseScraper constructor, async fetch contract, _generate_id format.
- src/scrapers/rss.py key-patterns: source iteration, since filtering, ContentItem construction, logger warning style.
- pyproject.toml key-patterns: project dependency list and uv-managed lock expectation.
- data/config.example.json key-patterns: top-level sources object and disabled optional source examples.

description:
Add youtube as a first-class source model and dependency. Implement a metadata-only YouTube scraper using yt-dlp through the current Python module path. Parser must accept timestamp and upload_date, skip missing publication dates, respect since filtering, never download media, and return [] on disabled config, missing dependency, timeout, invalid JSON lines, and non-zero subprocess exit.

verification:
- PR-1 config example parsing.
- PR-2 scraper unit and fake subprocess contract.

## Wave 2 - Orchestrator And MCP Integration

files_to_modify:
- src/orchestrator.py
- tests/test_orchestrator.py
- src/mcp/horizon_adapter.py
- tests/test_mcp_service_smoke.py

files_to_read:
- src/orchestrator.py key-patterns: fetch_all_sources task assembly, scraper import placement, _fetch_with_progress labels, _sub_source_label metadata priority.
- tests/test_orchestrator.py key-patterns: minimal Config construction, ContentItem fixtures, direct helper assertions.
- src/mcp/horizon_adapter.py key-patterns: VALID_SOURCES, apply_source_filter mutation, get_enabled_sources reporting, model_copy deep clone.
- src/mcp/service.py key-patterns: get_effective_config and validate_config route through adapter source filtering.
- tests/test_mcp_service_smoke.py key-patterns: tmp config copy, SimpleNamespace fake config, service smoke style.

description:
Wire YouTube fetches into the orchestrator only when configured and add channel_name-aware display labels. Update MCP source filtering so sources=["youtube"] is accepted, preserved, and reported while all unselected sources are disabled.

verification:
- PR-3 orchestrator label test plus existing orchestrator test.
- PR-4 MCP effective config and smoke tests for YouTube filtering.

## Wave 3 - Setup Wizard And Recommendation Surfaces

files_to_modify:
- src/setup/prompts.py
- src/setup/wizard.py
- src/setup/presets.py
- data/presets.json
- tests/test_setup_wizard.py

files_to_read:
- src/setup/prompts.py key-patterns: JSON-only recommendation prompt and allowed type list.
- src/setup/wizard.py key-patterns: build_config source branching, merge_configs dedupe rules, _count_sources summary.
- src/setup/presets.py key-patterns: API transformation, source unique key dedupe, fallback local preset shape.
- data/presets.json key-patterns: domains list, source type/config object shape, tags and descriptions.
- tests/test_setup_wizard.py key-patterns: direct wizard helper tests, monkeypatch prompt style, no CLI subprocess required.
- src/models.py key-patterns: YouTube config classes created in Wave 1.

description:
Allow AI and preset recommendations to include youtube sources, build YouTube config entries from selected recommendations, merge them by URL while preserving existing enabled state, and count enabled YouTube channels in setup completion summaries. If data/presets.json is changed, keep it small and relevant to the requested source/provider behavior.

verification:
- PR-5 setup wizard tests for build_config, merge_configs, source counting, and source unique key behavior.

## Wave 4 - User Docs And Concrete Runtime Config

files_to_modify:
- docs/scrapers.md
- docs/configuration.md
- README.md
- README_zh.md
- data/config.json

files_to_read:
- docs/scrapers.md key-patterns: per-source sections, config snippets, extracted data lists.
- docs/configuration.md key-patterns: Information Sources sections, AI provider section, JSON examples.
- README.md key-patterns: feature list, How It Works source list, configuration messaging.
- README_zh.md key-patterns: Chinese mirror of README source and configuration messaging.
- data/config.json key-patterns: existing llm_runner/codex/gpt-5.5 AI config, active source layout, webhook config.
- data/config.example.json key-patterns: example youtube block added in Wave 1.

description:
Document YouTube as a metadata-only yt-dlp source, including the reason RSS is not sufficient for some channels, the no-API-key/no-media-download boundary, config fields, and extracted metadata. Add the requested channel to data/config.json while preserving the existing llm_runner/codex/gpt-5.5 AI provider settings.

verification:
- PR-6 data/config.json parses and preserves llm_runner/codex/gpt-5.5.
- PR-7 docs scan finds YouTube, yt-dlp, UCGq-a57w-aPwyi3pW7XLiHw, and youtube in all four docs surfaces.

## Wave 5 - Final Refresh And Normal Horizon Output Proof

files_to_modify:
- data/summaries/horizon-2026-05-08-en.md
- docs/_posts/2026-05-08-summary-en.md

files_to_read:
- src/orchestrator.py key-patterns: normal summary generation writes data/summaries and docs/_posts.
- src/storage/manager.py key-patterns: daily summary save path and data directory behavior.
- docs/_config.yml key-patterns: Jekyll site baseurl and post rendering path.
- data/config.json key-patterns: enabled YouTube channel and llm_runner/codex/gpt-5.5 settings.

description:
Run final-refresh proof after evaluator pass. The generator should not run expensive full closeout during earlier waves. This wave exists as a final output/proof unit: source-only live fetch should show at least one item from The Diary Of A CEO, and the normal Horizon/Jekyll path should produce inspectable summary output rather than a custom verification page.

verification:
- PR-8 live YouTube source-only fetch returns at least one item with title, watch URL, publication date, and channel_name.
- PR-9 targeted suite and full pytest pass, and git diff --check emits no output.
- PR-10 docs Jekyll build exits 0 and generated normal summary/post include The Diary Of A CEO and a YouTube watch URL.

## Proof Requirements

- PR-1 blocking_proof: Parse data/config.example.json through src.models.Config and prove sources.youtube defaults/example fields validate.
- PR-2 blocking_proof: Run tests/test_youtube.py to prove disabled behavior, timestamp and upload_date parsing, since filtering, videos URL normalization, invalid JSON tolerance, and fake subprocess command shape.
- PR-3 blocking_proof: Run tests/test_orchestrator.py to prove YouTube channel metadata becomes the sub-source label without regressing URL query dedupe.
- PR-4 blocking_proof: Run tests/test_mcp_service_smoke.py to prove youtube is accepted by MCP filtering, preserved when selected, disabled when not selected, and reported as enabled only with configured channels.
- PR-5 blocking_proof: Run tests/test_setup_wizard.py to prove recommendation build, merge/dedupe, and count behavior for youtube.
- PR-6 blocking_proof: Parse data/config.json through Config and print YouTube enabled, channel name, ai.provider, ai.model, and ai.llm_runner_provider.
- PR-7 blocking_proof: Scan docs/scrapers.md, docs/configuration.md, README.md, and README_zh.md for YouTube, yt-dlp, UCGq-a57w-aPwyi3pW7XLiHw, and youtube.
- PR-8 final_refresh: Run an opt-in live YouTube source-only fetch for the requested channel and record count, title, URL, publication date, and channel_name.
- PR-9 final_refresh: Run targeted tests, full pytest, and git diff --check.
- PR-10 final_refresh: Run the normal Horizon output proof and docs Jekyll build; verify generated summary/post contains The Diary Of A CEO and a YouTube watch URL.

## Control Plane Consistency

Before evaluator dispatch:

- .feature-workflow-run.json completed_waves should list Wave 1 through Wave 5 if final output generation is complete, or Wave 1 through Wave 4 before final_refresh admission depending on orchestrator staging.
- .feature-workflow-run.json remaining_waves should be empty before evaluator verdict.
- Proof records should exist for PR-1 through PR-7, and any repair_focus proof introduced by evaluator findings.
- changed_paths in .feature-workflow-sprint.json should match the union of all wave files_to_modify.

Before final_refresh:

- wf-state.json.current_step should be final_refresh.
- .feature-workflow-run.json evaluator_verdict should be pass.
- final_refresh proof requirements should be PR-8, PR-9, and PR-10 only.
- expensive_gate_policy remains final_refresh_once_per_successful_repair_cycle.

Before completion:

- wf-state.json.current_step should be convergence_done and terminal_status should be completed.
- .feature-workflow-run.json remaining_waves should be empty.
- .feature-workflow-run.json final_refresh.status should be passed.
- .feature-workflow-sprint.json status should be completed or the orchestrator equivalent.
- verification.md should contain final evaluator verdict pass.
