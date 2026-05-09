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
        metadata={
            "title_ko": f"중요한 항목 {idx}",
            "detailed_summary_ko": f"{idx}번 항목 요약입니다.",
        },
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
    )

    assert "수집된 10개 항목 중 2개의 중요 항목을 선별했습니다." in result
    assert "1. [중요한 항목 1](https://example.com/items/1)" in result
    assert "2. [중요한 항목 2](https://example.com/items/2)" in result
    assert "Summary for item 1." not in result


def test_generate_webhook_item_renders_single_item_detail():
    summarizer = DailySummarizer()

    result = summarizer.generate_webhook_item(
        _make_item(1),
        index=1,
        total=2,
    )

    assert result.startswith("1/2 항목")
    assert "## [중요한 항목 1](https://example.com/items/1)" in result
    assert "1번 항목 요약입니다." in result
    assert "**태그**: `#AI`, `#News`" in result


def test_generate_webhook_item_includes_discussion_link_when_distinct():
    summarizer = DailySummarizer()
    item = _make_item(1)
    item.metadata["discussion_url"] = "https://news.ycombinator.com/item?id=1"

    result = summarizer.generate_webhook_item(
        item,
        index=1,
        total=1,
    )

    assert "tester · Apr 25, 08:00 · [토론](https://news.ycombinator.com/item?id=1)" in result


def test_generate_webhook_item_omits_discussion_link_when_same_as_item_url():
    summarizer = DailySummarizer()
    item = _make_item(1)
    item.metadata["discussion_url"] = item.url

    result = summarizer.generate_webhook_item(
        item,
        index=1,
        total=1,
    )

    assert "[토론](https://example.com/items/1)" not in result


def test_generate_webhook_item_uses_korean_discussion_label():
    summarizer = DailySummarizer()
    item = _make_item(1)
    item.metadata["discussion_url"] = "https://www.reddit.com/r/python/comments/abc123/test/"

    result = summarizer.generate_webhook_item(
        item,
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

    result = run_async(summarizer.generate_summary([item], "2026-05-08", 3))

    assert "# Horizon 데일리 - 2026-05-08" in result
    assert "3개 항목 중 1개의 중요 콘텐츠를 선별했습니다" in result
    assert "구독 사이트 <span class=\"source-tab-count\">1</span>" in result
    assert "중요한 항목" in result
    assert "한국어 상세 요약입니다." in result
    assert "<strong>배경</strong>: 한국어 배경 설명입니다." in result
    assert "<strong>토론</strong>: 한국어 커뮤니티 토론 요약입니다." in result


def test_generate_summary_adds_source_favicon_before_post_links():
    summarizer = DailySummarizer()
    item = _make_item(1)

    result = run_async(summarizer.generate_summary([item], "2026-05-08", 1))

    assert 'class="post-favicon"' in result
    assert 'src="https://www.google.com/s2/favicons?domain=example.com&amp;sz=32"' in result
    assert 'alt="example.com favicon"' in result
    assert '<img class="post-favicon"' in result
    assert '<h2><img class="post-favicon"' in result


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
    item.metadata["title_ko"] = "더티프래그"
    item.metadata["detailed_summary_ko"] = "보안 공개 요약입니다."
    item.ai_score = 9.0
    item.ai_summary = "A security disclosure."

    result = run_async(summarizer.generate_summary([item], "2026-05-08", 1))

    assert "domain=news.ycombinator.com&amp;sz=32" in result
    assert "alt=\"news.ycombinator.com favicon\"" in result
    assert "domain=openwall.com" not in result


def test_generate_empty_summary_uses_korean_count_message():
    summarizer = DailySummarizer()

    result = run_async(summarizer.generate_summary([], "2026-05-08", 3))

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
    item.metadata["title_ko"] = "장 교수 인터뷰"
    item.metadata["detailed_summary_ko"] = "영상 토론 미리보기입니다."
    item.ai_score = 8.0
    item.ai_summary = "A discussion preview."

    result = run_async(summarizer.generate_summary([item], "2026-05-08", 1))

    assert 'class="youtube-preview"' in result
    assert 'class="source-tab active" role="tab" aria-selected="true" aria-controls="source-panel-youtube"' in result
    assert 'id="source-panel-youtube" class="source-tab-panel active"' in result
    assert 'src="https://www.youtube-nocookie.com/embed/BTJGr78-zyw"' in result
    assert 'title="YouTube preview: 장 교수 인터뷰"' in result


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
    youtube_item.metadata["title_ko"] = "장 교수 인터뷰"
    youtube_item.metadata["detailed_summary_ko"] = "영상 토론 미리보기입니다."
    youtube_item.ai_score = 8.0
    youtube_item.ai_summary = "A discussion preview."

    result = run_async(
        summarizer.generate_summary([rss_item, youtube_item], "2026-05-08", 2)
    )

    assert 'class="source-tabs"' in result
    assert 'data-source-tab="sites"' in result
    assert '구독 사이트 <span class="source-tab-count">1</span>' in result
    assert 'data-source-tab="youtube"' in result
    assert 'YouTube <span class="source-tab-count">1</span>' in result
    assert 'id="source-panel-sites"' in result
    assert 'id="source-panel-youtube"' in result
    assert "중요한 항목 1" in result
    assert "장 교수 인터뷰" in result


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
    item.metadata["title_ko"] = "장 교수 인터뷰"
    item.metadata["detailed_summary_ko"] = "영상 토론 미리보기입니다."
    item.ai_score = 8.0
    item.ai_summary = "A discussion preview."

    result = summarizer.generate_webhook_item(item, index=1, total=1)

    assert "youtube-preview" not in result
    assert "<iframe" not in result


def _make_item_with_category(idx: int, category: str) -> ContentItem:
    """Helper: create an RSS item with a specific category for sub-tab testing."""
    item = ContentItem(
        id=f"rss:item-{idx}",
        source_type=SourceType.RSS,
        title=f"Item {idx}",
        url=f"https://example.com/{idx}",
        content="content",
        author="tester",
        published_at=datetime(2026, 5, 9, 8, 0, tzinfo=timezone.utc),
    )
    item.metadata.update({
        "title_ko": f"항목 {idx}",
        "category": category,
        "detailed_summary_ko": f"{idx}번 요약",
    })
    item.ai_score = 8.0
    item.ai_tags = ["Tag"]
    return item


def test_summary_uses_style_display_none_not_hidden_attribute():
    """Inactive panels must use style=display:none, never the hidden attribute."""
    items = [
        _make_item_with_category(1, "ai"),
        _make_item_with_category(2, "technology"),
    ]
    result = run_async(DailySummarizer().generate_summary(items, "2026-05-10", 2))

    assert '[hidden]' not in result, (
        "[hidden] attribute breaks kramdown; use style=\"display:none\" instead"
    )
    assert 'style=" display: none;"' in result, (
        "inactive panels should have style=\"display:none\""
    )
    assert 'markdown="1"' not in result, (
        "markdown=\"1\" is unused; content is pre-rendered in Python"
    )


def test_summary_multiple_subtab_panels_render_for_different_categories():
    """Items in different categories must each get their own sub-tab panel."""
    items = [
        _make_item_with_category(1, "ai"),
        _make_item_with_category(2, "technology"),
        _make_item_with_category(3, "world-news"),
        _make_item_with_category(4, "startup"),
        _make_item_with_category(5, "science"),
    ]
    result = run_async(DailySummarizer().generate_summary(items, "2026-05-10", 5))

    # Each category should produce a sub-tab panel section
    assert 'id="source-subpanel-ai"' in result
    assert 'id="source-subpanel-dev-tech"' in result
    assert 'id="source-subpanel-world"' in result
    assert 'id="source-subpanel-economy"' in result
    assert 'id="source-subpanel-science"' in result

    # Content should be found inside each panel
    assert "항목 1" in result
    assert "항목 3" in result

    # The first non-empty sub-tab should be marked active
    assert 'id="source-subpanel-ai" class="source-subtab-panel active"' in result


def test_summary_toc_renders_as_html_ol_not_raw_markdown():
    """TOC should be pre-rendered to HTML <ol>, not raw markdown numbered list."""
    item = _make_item_with_category(1, "ai")
    result = run_async(DailySummarizer().generate_summary([item], "2026-05-10", 1))

    assert '<ol>' in result, "TOC should be rendered as HTML <ol>"
    assert '<li>' in result, "TOC items should be rendered as HTML <li>"
    assert '1. <img' not in result, (
        "raw markdown numbering should not appear"
    )


def test_summary_mixed_source_types_with_subtab_sites():
    """Sites with sub-tabs + YouTube tab should all render without conflicts."""
    items = [
        _make_item_with_category(1, "ai"),
        _make_item_with_category(2, "korean-tech-news"),
        ContentItem(
            id="youtube:video:BTJGr78-zyw",
            source_type=SourceType.YOUTUBE,
            title="Professor Jiang",
            url="https://www.youtube.com/watch?v=BTJGr78-zyw",
            content="content",
            author="The Diary Of A CEO",
            published_at=datetime(2026, 5, 7, 7, 0, tzinfo=timezone.utc),
        ),
    ]
    # Add Korean metadata to YouTube item
    items[2].metadata.update({
        "title_ko": "장 교수 인터뷰",
        "detailed_summary_ko": "영상 토론 미리보기입니다.",
    })
    items[2].ai_score = 8.0
    items[2].ai_summary = "A discussion preview."

    result = run_async(DailySummarizer().generate_summary(items, "2026-05-10", 3))

    # Sites tab has sub-tab panels
    assert 'id="source-subpanel-ai"' in result
    assert 'id="source-subpanel-korean"' in result
    assert 'style=" display: none;"' in result  # at least one sub-tab panel is inactive
    assert '[hidden]' not in result

    # YouTube tab panel exists and is functional
    assert 'id="source-panel-youtube"' in result
    assert 'youtube-preview' in result

    # Content from all sources present
    assert "항목 1" in result
    assert "항목 2" in result
    assert "장 교수 인터뷰" in result
