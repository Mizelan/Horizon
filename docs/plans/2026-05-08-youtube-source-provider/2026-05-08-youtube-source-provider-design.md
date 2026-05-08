# YouTube Source Provider Design

planner_invocation_id: e949b4f1-5d26-4af6-93b8-cee64f214705
workflow_uuid: d590be5e-f6d3-4f81-a018-844ce4d101c0
source_plan: docs/plans/2026-05-08-youtube-source-provider.md
status: planned

## Goal

Add first-class YouTube channel ingestion to Horizon so a channel such as https://www.youtube.com/channel/UCGq-a57w-aPwyi3pW7XLiHw can be configured as a normal source and fetched into standard ContentItem records without relying on YouTube RSS, YouTube Data API keys, browser DOM scraping, or media downloads.

## Architecture Decision

The recommended design is a native source provider with a new youtube source type, a YouTube-specific config model, and a YouTube scraper that invokes yt-dlp as a metadata-only subprocess through the active Python environment. The provider should emit the same ContentItem shape as existing scrapers, with source_type youtube, stable ids shaped like youtube video native identity, a public video URL, title, channel metadata, publication date, and optional engagement metadata when yt-dlp returns it.

The scraper boundary should remain source-only. It fetches metadata and applies date filtering; it does not score, summarize, enrich, download media, fetch transcripts, or make AI-provider decisions. Normal orchestrator, analyzer, dedupe, summary, MCP, and docs publication paths consume the resulting ContentItem records.

ASCII flow:

data/config.json sources.youtube
  -> HorizonOrchestrator.fetch_all_sources
  -> YouTubeScraper
  -> python -m yt_dlp metadata JSON lines
  -> date-filtered ContentItem records
  -> existing cross-source dedupe, AI analysis, enrichment, summary, docs output

## Interfaces

models.py owns the new source contract. SourceType gains youtube. SourcesConfig gains a YouTube config object. A YouTube channel config needs a human name, channel URL, enabled flag, per-channel fetch limit, and optional category. The top-level YouTube config needs enabled, channel list, a command/display setting if retained for config compatibility, and timeout seconds.

src/scrapers/youtube.py owns metadata extraction. It should follow the BaseScraper convention and return an empty list for disabled config, missing dependencies, timeout, subprocess failure, invalid metadata, old items, or channels with no usable publication date. It should use the current Python executable with module execution so uv-managed dependency resolution is deterministic.

src/orchestrator.py owns dispatch and display labels. It should add YouTube to fetch_all_sources only when enabled with channels, and sub-source labels should prefer YouTube channel_name metadata before falling back to author.

src/mcp/horizon_adapter.py owns source filtering. youtube must be accepted in VALID_SOURCES, preserved when explicitly selected, disabled when not selected, and reported by get_enabled_sources only when enabled with channels.

src/setup owns wizard ingestion. AI and preset recommendations may include youtube entries. build_config should create YouTube config entries from selected sources, merge_configs should dedupe by URL while preserving existing enabled state, and _count_sources should include enabled YouTube channels.

Docs and examples must explain the user-facing contract: YouTube RSS may advertise a feed that returns 404 for some channels, Horizon uses yt-dlp metadata only, no API key is needed, and no media is downloaded.

## Scope

In scope:

- Schema and config example support for sources.youtube.
- New metadata-only YouTube scraper and focused tests.
- yt-dlp dependency and lock refresh.
- Orchestrator dispatch and sub-source labeling.
- MCP source filtering and validation surfaces.
- Setup wizard prompt, build, merge, preset, and count surfaces.
- README, README_zh, docs/scrapers.md, docs/configuration.md updates.
- Concrete data/config.json entry for The Diary Of A CEO while preserving llm_runner/codex/gpt-5.5.
- Source-only live proof and downstream Horizon/Jekyll final-refresh proof.

Out of scope:

- YouTube Data API key flow.
- Browser DOM scraping as production ingestion.
- Transcript, video, or audio downloads.
- AI provider or llm-runner behavior changes.
- X/Twitter redesign.
- Database migration.

## Validation Surface

Blocking proof should cover deterministic contracts: config parsing, scraper metadata parsing, subprocess command shape through fakes, date filtering, orchestrator label integration, MCP filtering, and setup wizard config creation and merge behavior.

Final refresh should cover broader and potentially expensive proof: full pytest, diff whitespace check, live YouTube fetch for the requested channel, normal Horizon pipeline output, and Jekyll build. Live YouTube/network proof is intentionally final_refresh because transient YouTube throttling or network failure should not be confused with deterministic unit-level implementation failure.

## Control Plane Assumptions

wf-state.json remains the orchestrator-owned source of truth for current_step, active wave, repair round, final_refresh status, and terminal_status. This planner produces the planned contract in .feature-workflow-sprint.json and describes consistency checks; the orchestrator should advance wf-state.json from planner to generator before dispatch.

Before evaluator dispatch, .feature-workflow-run.json should show completed_waves matching this plan, remaining_waves empty, and proof records for blocking_proof and any repair_focus proofs executed by the generator.

Before final_refresh, evaluator verification.md should record verdict pass and .feature-workflow-run.json should record evaluator_verdict pass. final_refresh proofs should run once for the successful repair cycle.

Before completion, wf-state.json, .feature-workflow-run.json, .feature-workflow-sprint.json, and verification.md should agree that waves are complete, evaluator passed, final_refresh passed or was explicitly skipped with no final_refresh requirements, and terminal_status is completed.

## Design Assumptions Affecting Proof

yt-dlp metadata shape may vary, so parser proof must cover timestamp and upload_date. Since YouTube live state can change, live proof requires at least one recent item from the requested channel within a bounded window, not a fixed title. Since existing GeekNews work showed query-string identity matters, YouTube URL/id tests should preserve stable video identity and avoid URL normalization regressions.
