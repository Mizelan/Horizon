import asyncio
import sys
import time
from datetime import datetime, timezone

from src.ai.enricher import ContentEnricher
from src.models import AIConfig, AIProvider, ContentItem, SourceType


class DummyClient:
    pass


def _make_item(item_id: str) -> ContentItem:
    return ContentItem(
        id=item_id,
        source_type=SourceType.RSS,
        title=f"Item {item_id}",
        url="https://example.com/item",
        content="Main story body\n--- Top Comments ---\nUseful community context",
        published_at=datetime(2026, 4, 26, tzinfo=timezone.utc),
        ai_score=8.0,
        ai_reason="important",
        ai_summary="summary",
        ai_tags=["ai", "cache"],
    )


def _make_ai_config(tmp_path, *, cache_enabled: bool = True) -> AIConfig:
    return AIConfig(
        provider=AIProvider.OPENAI,
        model="test-model",
        api_key_env="TEST_API_KEY",
        cache_enabled=cache_enabled,
        cache_dir=str(tmp_path),
    )


def test_web_search_returns_empty_list_on_timeout(monkeypatch):
    class SlowDDGS:
        def text(self, query, max_results=3):
            time.sleep(0.2)
            return [{"title": "late", "href": "https://example.com", "body": "too late"}]

    monkeypatch.setattr("src.ai.enricher.DDGS", SlowDDGS)
    enricher = ContentEnricher(DummyClient())

    result = asyncio.run(enricher._web_search("slow query", timeout_seconds=0.01))

    assert result == []


def test_web_search_timeout_does_not_replace_process_stderr(monkeypatch):
    class SlowDDGS:
        def text(self, query, max_results=3):
            time.sleep(0.2)
            return []

    monkeypatch.setattr("src.ai.enricher.DDGS", SlowDDGS)
    enricher = ContentEnricher(DummyClient())
    original_stderr = sys.stderr

    result = asyncio.run(enricher._web_search("slow query", timeout_seconds=0.01))

    assert result == []
    assert sys.stderr is original_stderr


def test_enrich_item_cache_hit_skips_concepts_search_and_final_llm(tmp_path, monkeypatch):
    class FakeClient:
        def __init__(self):
            self.config = _make_ai_config(tmp_path)
            self.calls = []

        async def complete(self, system, user):  # type: ignore[no-untyped-def]
            self.calls.append(user)
            if len(self.calls) == 1:
                return '{"queries": ["cache boundary"]}'
            return (
                '{"title_ko": "캐시 경계", "whats_new_ko": "새로운 내용입니다.", '
                '"why_it_matters_ko": "중요한 이유입니다.", '
                '"key_details_ko": "핵심 세부 사항입니다.", '
                '"background_ko": "배경 설명입니다.", '
                '"community_discussion_ko": "논의 요약입니다.", '
                '"sources": ["https://example.com/context"]}'
            )

    client = FakeClient()
    enricher = ContentEnricher(client)
    search_calls = []

    async def fake_web_search(query):
        search_calls.append(query)
        return [{"title": "Context", "url": "https://example.com/context", "body": "grounding"}]

    monkeypatch.setattr(enricher, "_web_search", fake_web_search)

    asyncio.run(enricher._enrich_item(_make_item("rss:test:cache-hit")))
    cached_item = _make_item("rss:test:cache-hit")
    asyncio.run(enricher._enrich_item(cached_item))

    assert len(client.calls) == 2
    assert search_calls == ["cache boundary"]
    assert cached_item.metadata["title_ko"] == "캐시 경계"
    assert cached_item.metadata["detailed_summary_ko"] == "새로운 내용입니다.\n\n중요한 이유입니다.\n\n핵심 세부 사항입니다."
    assert cached_item.metadata["background_ko"] == "배경 설명입니다."
    assert cached_item.metadata["community_discussion_ko"] == "논의 요약입니다."
    assert cached_item.metadata["sources"] == [{"url": "https://example.com/context", "title": "Context"}]


def test_enrich_item_cache_hit_replays_korean_metadata_only(tmp_path, monkeypatch):
    class FakeClient:
        def __init__(self):
            self.config = _make_ai_config(tmp_path)
            self.calls = []

        async def complete(self, system, user):  # type: ignore[no-untyped-def]
            self.calls.append(user)
            if len(self.calls) == 1:
                return '{"queries": ["korean metadata"]}'
            return (
                '{"title_ko": "미러 메타데이터", "whats_new_ko": "새로운 내용입니다.", '
                '"why_it_matters_ko": "중요한 이유입니다.", '
                '"key_details_ko": "핵심 세부 사항입니다.", '
                '"background_ko": "배경 설명입니다.", '
                '"community_discussion_ko": "논의 요약입니다.", '
                '"sources": ["https://example.com/korean"]}'
            )

    client = FakeClient()
    enricher = ContentEnricher(client)

    async def fake_web_search(query):
        return [{"title": "Korean", "url": "https://example.com/korean", "body": "grounding"}]

    monkeypatch.setattr(enricher, "_web_search", fake_web_search)

    asyncio.run(enricher._enrich_item(_make_item("rss:test:korean-cache")))
    cached_item = _make_item("rss:test:korean-cache")
    asyncio.run(enricher._enrich_item(cached_item))

    assert len(client.calls) == 2
    assert cached_item.metadata["detailed_summary_ko"] == "새로운 내용입니다.\n\n중요한 이유입니다.\n\n핵심 세부 사항입니다."
    assert cached_item.metadata["background_ko"] == "배경 설명입니다."
    assert cached_item.metadata["community_discussion_ko"] == "논의 요약입니다."
    assert "detailed_summary" not in cached_item.metadata
    assert "background" not in cached_item.metadata
    assert "community_discussion" not in cached_item.metadata


def test_enrich_item_parse_failure_is_not_cached(tmp_path, monkeypatch):
    class FakeClient:
        def __init__(self):
            self.config = _make_ai_config(tmp_path)
            self.calls = 0

        async def complete(self, system, user):  # type: ignore[no-untyped-def]
            self.calls += 1
            if self.calls in (1, 3):
                return '{"queries": ["parse retry"]}'
            if self.calls == 2:
                return "not json"
            return (
                '{"title_ko": "재시도 성공", "whats_new_ko": "다시 생성했습니다.", '
                '"why_it_matters_ko": "실패 결과를 재사용하지 않습니다.", '
                '"key_details_ko": "성공한 결과만 저장합니다.", '
                '"background_ko": "", "community_discussion_ko": "", '
                '"sources": ["https://example.com/retry"]}'
            )

    client = FakeClient()
    enricher = ContentEnricher(client)
    search_calls = []

    async def fake_web_search(query):
        search_calls.append(query)
        return [{"title": "Retry", "url": "https://example.com/retry", "body": "grounding"}]

    monkeypatch.setattr(enricher, "_web_search", fake_web_search)

    failed_item = _make_item("rss:test:parse-failure")
    asyncio.run(enricher._enrich_item(failed_item))
    retried_item = _make_item("rss:test:parse-failure")
    asyncio.run(enricher._enrich_item(retried_item))

    assert client.calls == 4
    assert search_calls == ["parse retry", "parse retry"]
    assert "title_ko" not in failed_item.metadata
    assert retried_item.metadata["title_ko"] == "재시도 성공"
