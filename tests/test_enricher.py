import asyncio
import sys
import time

from src.ai.enricher import ContentEnricher


class DummyClient:
    pass


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
