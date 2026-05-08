import asyncio
import inspect
from datetime import datetime, timezone
from pathlib import Path

from src.ai.enricher import ContentEnricher
from src.ai.prompts import CONTENT_ENRICHMENT_SYSTEM, CONTENT_ENRICHMENT_USER
from src.ai.summarizer import DailySummarizer
from src.mcp.run_store import RunStore
from src.models import ContentItem, SourceType
from src.storage.manager import StorageManager


class KoreanOnlyClient:
    async def complete(self, system: str, user: str) -> str:
        return """
        {
          "title_ko": "한국어 제목입니다.",
          "whats_new_ko": "새로운 내용입니다.",
          "why_it_matters_ko": "중요한 이유입니다.",
          "key_details_ko": "핵심 세부사항입니다.",
          "background_ko": "배경 설명입니다.",
          "community_discussion_ko": "토론 요약입니다.",
          "sources": []
        }
        """


def test_enrichment_prompt_requests_korean_fields_only():
    prompt_text = CONTENT_ENRICHMENT_SYSTEM + CONTENT_ENRICHMENT_USER

    assert "title_ko" in prompt_text
    assert "whats_new_ko" in prompt_text
    assert "title_en" not in prompt_text
    assert "whats_new_en" not in prompt_text
    assert "English" not in prompt_text
    assert "bilingual" not in prompt_text


def test_enricher_stores_korean_metadata_only(monkeypatch):
    item = ContentItem(
        id="rss:item-1",
        source_type=SourceType.RSS,
        title="Original title",
        url="https://example.com/item",
        content="content",
        author="tester",
        published_at=datetime(2026, 5, 8, 8, 0, tzinfo=timezone.utc),
    )
    item.ai_score = 8.0
    item.ai_summary = "Original summary."

    enricher = ContentEnricher(KoreanOnlyClient())
    monkeypatch.setattr(enricher, "_web_search", lambda *args, **kwargs: asyncio.sleep(0, result=[]))

    asyncio.run(enricher._enrich_item(item))

    assert item.metadata["title_ko"] == "한국어 제목입니다."
    assert item.metadata["detailed_summary_ko"] == "새로운 내용입니다. 중요한 이유입니다. 핵심 세부사항입니다."
    assert "detailed_summary" not in item.metadata
    assert "title_en" not in item.metadata
    assert "detailed_summary_en" not in item.metadata
    assert "background_en" not in item.metadata
    assert "community_discussion_en" not in item.metadata


def test_summary_and_storage_apis_have_no_language_parameter():
    assert "language" not in inspect.signature(DailySummarizer.generate_summary).parameters
    assert "language" not in inspect.signature(DailySummarizer.generate_webhook_overview).parameters
    assert "language" not in inspect.signature(DailySummarizer.generate_webhook_item).parameters
    assert "language" not in inspect.signature(StorageManager.save_daily_summary).parameters
    assert "language" not in inspect.signature(RunStore.save_summary).parameters
    assert "language" not in inspect.signature(RunStore.load_summary).parameters


def test_summarizer_uses_korean_metadata_directly():
    summarizer = DailySummarizer()
    item = ContentItem(
        id="rss:item-1",
        source_type=SourceType.RSS,
        title="Original English title",
        url="https://example.com/item",
        content="content",
        author="tester",
        published_at=datetime(2026, 5, 8, 8, 0, tzinfo=timezone.utc),
        metadata={
            "title_ko": "한국어 제목입니다",
            "detailed_summary_ko": "한국어 요약입니다.",
            "background_ko": "한국어 배경입니다.",
            "community_discussion_ko": "한국어 토론입니다.",
        },
    )
    item.ai_score = 8.0
    item.ai_summary = "English fallback summary."

    result = asyncio.run(summarizer.generate_summary([item], "2026-05-08", 3))

    assert "한국어 제목입니다" in result
    assert "한국어 요약입니다." in result
    assert "한국어 배경입니다." in result
    assert "한국어 토론입니다." in result
    assert "Original English title" not in result
    assert "English fallback summary." not in result


def test_docs_do_not_render_korean_english_language_switch():
    root = Path(__file__).resolve().parents[1]
    js = (root / "docs/assets/js/horizon.js").read_text()
    css = (root / "docs/assets/css/horizon.css").read_text()
    index = (root / "docs/index.md").read_text()
    head = (root / "docs/_includes/head-custom.html").read_text()

    assert "setupLanguageToggle" not in js
    assert "lang-toggle" not in js
    assert ".lang-toggle" not in css
    assert 'id="lang-en"' not in index
    assert "feed-en.xml" not in index
    assert "feed-en.xml" not in head
    assert not (root / "docs/feed-en.xml").exists()
