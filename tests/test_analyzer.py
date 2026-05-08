import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import src.ai.analyzer as analyzer_module
from src.ai.analyzer import ContentAnalyzer
from src.models import ContentItem, SourceType


def _make_item(item_id: str) -> ContentItem:
    return ContentItem(
        id=item_id,
        source_type=SourceType.RSS,
        title=f"Item {item_id}",
        url="https://example.com/item",
        published_at=datetime(2026, 4, 26, tzinfo=timezone.utc),
    )


def test_analyze_batch_does_not_sleep_by_default(monkeypatch):
    analyzer = ContentAnalyzer(SimpleNamespace())
    items = [_make_item("rss:test:1"), _make_item("rss:test:2")]
    sleep_calls = []

    async def fake_analyze_item(item):
        item.ai_score = 8.0

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(analyzer, "_analyze_item", fake_analyze_item)
    monkeypatch.setattr(analyzer_module.asyncio, "sleep", fake_sleep)

    result = asyncio.run(analyzer.analyze_batch(items))

    assert len(result) == 2
    assert sleep_calls == []


def test_analyze_batch_sleeps_between_items_when_throttle_configured(monkeypatch):
    client = SimpleNamespace(config=SimpleNamespace(throttle_sec=1.5))
    analyzer = ContentAnalyzer(client)
    items = [_make_item("rss:test:1"), _make_item("rss:test:2"), _make_item("rss:test:3")]
    sleep_calls = []

    async def fake_analyze_item(item):
        item.ai_score = 8.0

    async def fake_sleep(seconds):
        sleep_calls.append(seconds)

    monkeypatch.setattr(analyzer, "_analyze_item", fake_analyze_item)
    monkeypatch.setattr(analyzer_module.asyncio, "sleep", fake_sleep)

    asyncio.run(analyzer.analyze_batch(items))

    assert sleep_calls == [1.5, 1.5]


def test_analyze_item_accepts_parseable_llm_runner_text():
    class FakeClient:
        async def complete(self, system, user):  # type: ignore[no-untyped-def]
            return '{"score": 8, "reason": "useful", "summary": "runner summary", "tags": ["ai"]}'

    item = _make_item("rss:test:runner-json")
    analyzer = ContentAnalyzer(FakeClient())

    asyncio.run(analyzer._analyze_item(item))

    assert item.ai_score == 8.0
    assert item.ai_reason == "useful"
    assert item.ai_summary == "runner summary"
    assert item.ai_tags == ["ai"]


def test_analyze_item_falls_back_on_non_json_llm_runner_text():
    class FakeClient:
        async def complete(self, system, user):  # type: ignore[no-untyped-def]
            return "not json"

    item = _make_item("rss:test:runner-text")
    analyzer = ContentAnalyzer(FakeClient())

    asyncio.run(analyzer._analyze_item(item))

    assert item.ai_score == 0.0
    assert item.ai_reason == "Analysis response parse failed"
    assert item.ai_summary == item.title
    assert item.ai_tags == []
