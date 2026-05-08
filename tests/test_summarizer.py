"""Unit tests for daily summary rendering."""

import asyncio
from datetime import datetime, timezone

from src.ai.summarizer import DailySummarizer
from src.models import ContentItem, SourceType


def run_async(coro):
    return asyncio.run(coro)


def _make_item(idx: int) -> ContentItem:
    item = ContentItem(
        id=f"rss:item-{idx}",
        source_type=SourceType.RSS,
        title=f"Important Item {idx}",
        url=f"https://example.com/items/{idx}",
        content="content",
        author="tester",
        published_at=datetime(2026, 4, 25, 8, 0, tzinfo=timezone.utc),
    )
    item.ai_score = 8.0
    item.ai_summary = f"Summary for item {idx}."
    item.ai_tags = ["AI", "News"]
    return item


def test_generate_webhook_overview_lists_items_without_full_details():
    summarizer = DailySummarizer()
    items = [_make_item(1), _make_item(2)]

    result = summarizer.generate_webhook_overview(
        items,
        date="2026-04-25",
        total_fetched=10,
        language="en",
    )

    assert "Selected 2 important items from 10 fetched items" in result
    assert "1. [Important Item 1](https://example.com/items/1)" in result
    assert "2. [Important Item 2](https://example.com/items/2)" in result
    assert "Summary for item 1." not in result


def test_generate_webhook_item_renders_single_item_detail():
    summarizer = DailySummarizer()

    result = summarizer.generate_webhook_item(
        _make_item(1),
        language="en",
        index=1,
        total=2,
    )

    assert result.startswith("Item 1/2")
    assert "## [Important Item 1](https://example.com/items/1)" in result
    assert "Summary for item 1." in result
    assert "**Tags**: `#AI`, `#News`" in result


def test_generate_webhook_item_includes_discussion_link_when_distinct():
    summarizer = DailySummarizer()
    item = _make_item(1)
    item.metadata["discussion_url"] = "https://news.ycombinator.com/item?id=1"

    result = summarizer.generate_webhook_item(
        item,
        language="en",
        index=1,
        total=1,
    )

    assert "tester · Apr 25, 08:00 · [Discussion](https://news.ycombinator.com/item?id=1)" in result


def test_generate_webhook_item_omits_discussion_link_when_same_as_item_url():
    summarizer = DailySummarizer()
    item = _make_item(1)
    item.metadata["discussion_url"] = item.url

    result = summarizer.generate_webhook_item(
        item,
        language="en",
        index=1,
        total=1,
    )

    assert "[Discussion](https://example.com/items/1)" not in result


def test_generate_webhook_item_uses_korean_discussion_label():
    summarizer = DailySummarizer()
    item = _make_item(1)
    item.metadata["discussion_url"] = "https://www.reddit.com/r/python/comments/abc123/test/"

    result = summarizer.generate_webhook_item(
        item,
        language="ko",
        index=1,
        total=1,
    )

    assert "[토론](https://www.reddit.com/r/python/comments/abc123/test/)" in result


def test_generate_summary_uses_korean_content_when_available():
    summarizer = DailySummarizer()
    item = _make_item(1)
    item.metadata.update(
        {
            "title_ko": "중요한 항목",
            "detailed_summary_ko": "한국어 상세 요약입니다.",
            "background_ko": "한국어 배경 설명입니다.",
            "community_discussion_ko": "한국어 커뮤니티 토론 요약입니다.",
        }
    )

    result = run_async(summarizer.generate_summary([item], "2026-05-08", 3, language="ko"))

    assert "# Horizon 데일리 - 2026-05-08" in result
    assert "3개 항목 중 1개의 중요 콘텐츠를 선별했습니다" in result
    assert "구독 사이트 <span class=\"source-tab-count\">1</span>" in result
    assert "중요한 항목" in result
    assert "한국어 상세 요약입니다." in result
    assert "**배경**: 한국어 배경 설명입니다." in result
    assert "**토론**: 한국어 커뮤니티 토론 요약입니다." in result


def test_generate_summary_adds_source_favicon_before_post_links():
    summarizer = DailySummarizer()
    item = _make_item(1)

    result = run_async(summarizer.generate_summary([item], "2026-05-08", 1, language="en"))

    assert 'class="post-favicon"' in result
    assert 'src="https://www.google.com/s2/favicons?domain=example.com&amp;sz=32"' in result
    assert 'alt="example.com favicon"' in result
    assert '<img class="post-favicon"' in result
    assert '## <img class="post-favicon"' in result


def test_hackernews_item_uses_hackernews_favicon_not_target_domain():
    summarizer = DailySummarizer()
    item = ContentItem(
        id="hackernews:48053623",
        source_type=SourceType.HACKERNEWS,
        title="Dirtyfrag",
        url="https://www.openwall.com/lists/oss-security/2026/05/07/8",
        content="content",
        author="flipped",
        published_at=datetime(2026, 5, 7, 19, 21, tzinfo=timezone.utc),
    )
    item.metadata["discussion_url"] = "https://news.ycombinator.com/item?id=48053623"
    item.ai_score = 9.0
    item.ai_summary = "A security disclosure."

    result = run_async(summarizer.generate_summary([item], "2026-05-08", 1, language="ko"))

    assert "domain=news.ycombinator.com&amp;sz=32" in result
    assert "alt=\"news.ycombinator.com favicon\"" in result
    assert "domain=openwall.com" not in result


def test_generate_empty_summary_uses_korean_count_message():
    summarizer = DailySummarizer()

    result = run_async(summarizer.generate_summary([], "2026-05-08", 3, language="ko"))

    assert "# Horizon 데일리 - 2026-05-08" in result
    assert "3개 항목을 분석했지만 중요도 임계값을 넘은 항목이 없습니다." in result


def test_generate_summary_embeds_youtube_preview_for_watch_urls():
    summarizer = DailySummarizer()
    item = ContentItem(
        id="youtube:video:BTJGr78-zyw",
        source_type=SourceType.YOUTUBE,
        title="Professor Jiang",
        url="https://www.youtube.com/watch?v=BTJGr78-zyw",
        content="content",
        author="The Diary Of A CEO",
        published_at=datetime(2026, 5, 7, 7, 0, tzinfo=timezone.utc),
    )
    item.ai_score = 8.0
    item.ai_summary = "A discussion preview."

    result = run_async(summarizer.generate_summary([item], "2026-05-08", 1, language="en"))

    assert 'class="youtube-preview"' in result
    assert 'class="source-tab active" role="tab" aria-selected="true" aria-controls="source-panel-youtube"' in result
    assert 'id="source-panel-youtube" class="source-tab-panel active"' in result
    assert 'src="https://www.youtube-nocookie.com/embed/BTJGr78-zyw"' in result
    assert 'title="YouTube preview: Professor Jiang"' in result


def test_generate_summary_groups_subscribed_sites_and_youtube_in_tabs():
    summarizer = DailySummarizer()
    rss_item = _make_item(1)
    youtube_item = ContentItem(
        id="youtube:video:BTJGr78-zyw",
        source_type=SourceType.YOUTUBE,
        title="Professor Jiang",
        url="https://www.youtube.com/watch?v=BTJGr78-zyw",
        content="content",
        author="The Diary Of A CEO",
        published_at=datetime(2026, 5, 7, 7, 0, tzinfo=timezone.utc),
    )
    youtube_item.ai_score = 8.0
    youtube_item.ai_summary = "A discussion preview."

    result = run_async(
        summarizer.generate_summary([rss_item, youtube_item], "2026-05-08", 2, language="en")
    )

    assert 'class="source-tabs"' in result
    assert 'data-source-tab="sites"' in result
    assert 'Subscribed Sites <span class="source-tab-count">1</span>' in result
    assert 'data-source-tab="youtube"' in result
    assert 'YouTube <span class="source-tab-count">1</span>' in result
    assert 'id="source-panel-sites"' in result
    assert 'id="source-panel-youtube"' in result
    assert "Important Item 1" in result
    assert "Professor Jiang" in result


def test_generate_webhook_item_does_not_embed_youtube_iframe():
    summarizer = DailySummarizer()
    item = ContentItem(
        id="youtube:video:BTJGr78-zyw",
        source_type=SourceType.YOUTUBE,
        title="Professor Jiang",
        url="https://www.youtube.com/watch?v=BTJGr78-zyw",
        content="content",
        author="The Diary Of A CEO",
        published_at=datetime(2026, 5, 7, 7, 0, tzinfo=timezone.utc),
    )
    item.ai_score = 8.0
    item.ai_summary = "A discussion preview."

    result = summarizer.generate_webhook_item(item, language="en", index=1, total=1)

    assert "youtube-preview" not in result
    assert "<iframe" not in result
