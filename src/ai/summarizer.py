"""Daily summary generation — pure programmatic rendering."""

import html
from typing import List
from urllib.parse import parse_qs, urlparse

from ..models import ContentItem


LABELS = {
    "header": "Horizon 데일리",
    "background": "배경",
    "discussion": "토론",
    "references": "참고 링크",
    "tags": "태그",
    "tab_sites": "구독 사이트",
    "tab_youtube": "YouTube",
    "tab_twitter": "X / Twitter",
    "empty_sites": "선별된 구독 사이트 항목이 없습니다.",
    "empty_youtube": "선별된 YouTube 항목이 없습니다.",
    "empty_twitter": "선별된 X/Twitter 항목이 없습니다.",
    "empty_body": (
        "오늘은 중요한 업데이트가 없습니다. 가능한 이유는 다음과 같습니다.\n"
        "- 추적 중인 정보원이 조용한 하루를 보냈습니다\n"
        "- AI 점수 임계값이 너무 높습니다\n"
        "- 정보원을 더 다양하게 확장할 필요가 있습니다\n\n"
        "다음 조정을 고려하세요.\n"
        "1. config.json의 `ai_score_threshold`를 낮추기\n"
        "2. 더 다양한 정보원 추가하기\n"
        "3. AI 모델이 정상 동작하는지 확인하기\n"
    ),
}


class DailySummarizer:
    """Generates daily Markdown summaries from pre-analyzed content items."""

    def __init__(self):
        pass

    async def generate_summary(
        self,
        items: List[ContentItem],
        date: str,
        total_fetched: int,
    ) -> str:
        """Generate a Korean daily summary in Markdown format."""
        if not items:
            return self._generate_empty_summary(date, total_fetched)

        header = (
            f"# {LABELS['header']} - {date}\n\n"
            f"> {total_fetched}개 항목 중 {len(items)}개의 중요 콘텐츠를 선별했습니다\n\n"
            "---\n\n"
        )

        indexed_items = list(enumerate(items, start=1))
        twitter_items = [(i, item) for i, item in indexed_items if item.source_type.value == "twitter"]
        youtube_items = [(i, item) for i, item in indexed_items if item.source_type.value == "youtube"]
        site_items = [(i, item) for i, item in indexed_items
                      if item.source_type.value not in ("twitter", "youtube")]

        content = self._format_tabbed_sections(site_items, youtube_items, twitter_items)

        return header + content

    def generate_webhook_overview(
        self,
        items: List[ContentItem],
        date: str,
        total_fetched: int,
    ) -> str:
        """Generate a compact overview for multi-message webhook delivery."""
        if not items:
            return self._generate_empty_summary(date, total_fetched)

        header = (
            f"# {LABELS['header']} - {date}\n\n"
            f"> 수집된 {total_fetched}개 항목 중 {len(items)}개의 중요 항목을 선별했습니다.\n\n"
            "관심 있는 제목만 골라 읽을 수 있도록 상세 내용은 항목별로 전송됩니다.\n\n"
        )

        entries = []
        for i, item in enumerate(items, start=1):
            title = str(item.metadata.get("title_ko", "")).replace("[", "(").replace("]", ")")
            score = item.ai_score or "?"
            entries.append(f"{i}. [{title}]({item.url}) ⭐️ {score}/10")

        return header + "\n".join(entries)

    def generate_webhook_item(
        self,
        item: ContentItem,
        index: int,
        total: int,
    ) -> str:
        """Generate one item message for multi-message webhook delivery."""
        prefix = f"{index}/{total} 항목\n\n"
        return prefix + self._format_item(
            item,
            index,
            include_media=False,
        ).rstrip("-\n ")

    def _format_tabbed_sections(
        self,
        site_items: List[tuple[int, ContentItem]],
        youtube_items: List[tuple[int, ContentItem]],
        twitter_items: List[tuple[int, ContentItem]],
    ) -> str:
        """Render one-page source tabs for site, YouTube, and X/Twitter items."""
        groups = [
            ("sites",  site_items,  "tab_sites"),
            ("youtube", youtube_items, "tab_youtube"),
            ("twitter", twitter_items, "tab_twitter"),
        ]
        # First non-empty group is active
        active_key = next((key for key, items, _ in groups if items), groups[0][0])

        tab_buttons = ""
        panels = ""
        for key, items, label_key in groups:
            is_active = key == active_key
            active_str = "true" if is_active else "false"
            cls = "source-tab active" if is_active else "source-tab"
            tab_buttons += (
                f'    <button type="button" class="{cls}" role="tab" '
                f'aria-selected="{active_str}" aria-controls="source-panel-{key}" '
                f'id="source-tab-{key}" data-source-tab="{key}">{LABELS[label_key]} '
                f'<span class="source-tab-count">{len(items)}</span></button>\n'
            )
            panels += self._format_tab_panel(key, items, active=is_active)

        return (
            '<div class="source-tabs" data-source-tabs>\n'
            '  <div class="source-tablist" role="tablist" aria-label="Source groups">\n'
            f'{tab_buttons}'
            "  </div>\n"
            f"{panels}"
            "</div>\n\n"
        )

    def _format_tab_panel(
        self,
        group: str,
        indexed_items: List[tuple[int, ContentItem]],
        *,
        active: bool,
    ) -> str:
        """Render one tab panel with markdown enabled for Jekyll/kramdown."""
        hidden = "" if active else " hidden"
        active_class = " active" if active else ""
        empty_label = LABELS.get(f"empty_{group}", LABELS["empty_sites"])
        panel = (
            f'  <section id="source-panel-{group}" '
            f'class="source-tab-panel{active_class}" role="tabpanel" '
            f'aria-labelledby="source-tab-{group}"{hidden} markdown="1">\n\n'
        )
        if not indexed_items:
            panel += f"{empty_label}\n\n"
        else:
            panel += self._format_toc(indexed_items)
            panel += "".join(
                self._format_item(item, index, include_media=True)
                for index, item in indexed_items
            )
        return panel + "  </section>\n"

    @staticmethod
    def _format_toc(indexed_items: List[tuple[int, ContentItem]]) -> str:
        """Render a per-tab table of contents."""
        toc_entries = []
        for index, item in indexed_items:
            title = str(item.metadata.get("title_ko", "")).replace("[", "(").replace("]", ")")
            score = item.ai_score or "?"
            favicon = DailySummarizer._favicon_html(item)
            toc_entries.append(f"{index}. {favicon} [{title}](#item-{index}) ⭐️ {score}/10")
        return "\n".join(toc_entries) + "\n\n---\n\n"

    def _format_item(
        self,
        item: ContentItem,
        index: int,
        *,
        include_media: bool,
    ) -> str:
        """Format a single ContentItem into Markdown.

        Section order: 요약 → 핵심 → 상세 → 배경 → 출처·시간·토론
        Falls back to detailed_summary_ko if individual fields are missing.
        """
        title = str(item.metadata.get("title_ko", "")).replace("[", "(").replace("]", ")")
        url = str(item.url)
        score = item.ai_score or "?"
        meta = item.metadata

        whats_new = meta.get("whats_new_ko", "")
        why_matters = meta.get("why_it_matters_ko", "")
        key_details = meta.get("key_details_ko", "")
        background = meta.get("background_ko", "")
        discussion = meta.get("community_discussion_ko", "")
        fallback_summary = meta.get("detailed_summary_ko", "")

        favicon = self._favicon_html(item) + " " if include_media else ""

        # Source line with parts joined by " · ", link appended at end
        source_type = item.source_type.value
        source_parts = [source_type]
        if meta.get("subreddit"):
            source_parts.append(f"r/{meta['subreddit']}")
        if meta.get("feed_name"):
            source_parts.append(meta["feed_name"])
        else:
            source_parts.append(item.author or "unknown")
        if item.published_at:
            day = item.published_at.strftime("%d").lstrip("0")
            source_parts.append(item.published_at.strftime(f"%b {day}, %H:%M"))
        source_line = " · ".join(source_parts)

        discussion_url = meta.get("discussion_url")
        if discussion_url:
            discussion_url = str(discussion_url)
            if discussion_url != url:
                source_line += f' · [{LABELS["discussion"]}]({discussion_url})'

        lines = [
            f'<a id="item-{index}"></a>',
            f"## {favicon}[{title}]({url}) ⭐️ {score}/10",
        ]

        if include_media:
            embed = self._youtube_embed_html(item, title)
            if embed:
                lines.extend(["", embed])

        # Render each summary section with proper spacing
        has_individual = bool(whats_new or why_matters or key_details)
        if has_individual:
            for section_text in (whats_new, why_matters, key_details):
                if section_text:
                    lines.append("")
                    lines.append(section_text)
        elif fallback_summary:
            lines.append("")
            lines.append(fallback_summary)

        lines.append("")
        lines.append(source_line)

        if background:
            lines.append("")
            lines.append(background)

        if discussion:
            lines.append("")
            lines.append(discussion)

        sources = meta.get("sources") or []
        if sources:
            items_html = "".join(f'<li><a href="{s["url"]}">{s["title"]}</a></li>\n' for s in sources)
            lines += [
                "",
                f'<details><summary>{LABELS["references"]}</summary>\n<ul>\n{items_html}\n</ul>\n</details>',
            ]

        if item.ai_tags:
            tags_str = ", ".join([f"`#{t}`" for t in item.ai_tags])
            lines.append("")
            lines.append(f"**{LABELS['tags']}**: {tags_str}")

        lines.append("")
        lines.append("---")

        return "\n".join(lines) + "\n\n"

    @staticmethod
    def _favicon_html(item: ContentItem) -> str:
        """Render an icon for the subscription/source domain."""
        # Twitter items: use the author's profile picture via unavatar
        if item.source_type.value == "twitter":
            handle = item.metadata.get("handle", "")
            if handle:
                safe_handle = html.escape(handle, quote=True)
                return (
                    f'<img class="post-favicon post-favicon-avatar" '
                    f'src="https://unavatar.io/x/{safe_handle}" '
                    f'alt="@{safe_handle}" loading="lazy" '
                    'referrerpolicy="no-referrer">'
                )

        host = DailySummarizer._favicon_host(item)
        if not host:
            return ""

        safe_host = html.escape(host, quote=True)
        safe_src = html.escape(
            f"https://www.google.com/s2/favicons?domain={host}&sz=32",
            quote=True,
        )
        return (
            f'<img class="post-favicon" src="{safe_src}" '
            f'alt="{safe_host} favicon" loading="lazy" '
            'referrerpolicy="no-referrer">'
        )

    @staticmethod
    def _favicon_host(item: ContentItem) -> str:
        """Return the host that visually identifies the source subscription."""
        source_type = item.source_type.value
        meta = item.metadata

        if source_type == "hackernews":
            return "news.ycombinator.com"
        if source_type == "github":
            return "github.com"
        if source_type == "reddit":
            return "reddit.com"
        if source_type == "telegram":
            return "t.me"
        if source_type == "twitter":
            return "x.com"
        if source_type == "youtube":
            return "youtube.com"

        feed_url = str(meta.get("feed_url") or "")
        if feed_url:
            host = (urlparse(feed_url).hostname or "").lower()
        elif meta.get("feed_name") == "GeekNews":
            host = "news.hada.io"
        elif meta.get("feed_name") == "GitHub Trending - Daily":
            host = "github.com"
        else:
            host = (urlparse(str(item.url)).hostname or "").lower()

        if host.startswith("www."):
            host = host[4:]
        return host

    @staticmethod
    def _youtube_embed_html(item: ContentItem, title: str) -> str:
        """Render a responsive YouTube preview iframe for summary pages."""
        if item.source_type.value != "youtube":
            return ""

        video_id = DailySummarizer._youtube_video_id(str(item.url))
        if not video_id:
            return ""

        safe_title = html.escape(f"YouTube preview: {title}", quote=True)
        safe_id = html.escape(video_id, quote=True)
        return (
            '<div class="youtube-preview">\n'
            f'  <iframe src="https://www.youtube-nocookie.com/embed/{safe_id}" '
            f'title="{safe_title}" loading="lazy" '
            'allow="accelerometer; autoplay; clipboard-write; encrypted-media; '
            'gyroscope; picture-in-picture; web-share" allowfullscreen></iframe>\n'
            "</div>"
        )

    @staticmethod
    def _youtube_video_id(url: str) -> str:
        """Extract a YouTube video id from common watch, short, and embed URLs."""
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]

        if host == "youtu.be":
            return parsed.path.strip("/").split("/")[0]

        if host.endswith("youtube.com"):
            if parsed.path == "/watch":
                return parse_qs(parsed.query).get("v", [""])[0]
            for prefix in ("/embed/", "/shorts/"):
                if parsed.path.startswith(prefix):
                    return parsed.path[len(prefix):].strip("/").split("/")[0]

        return ""

    def _generate_empty_summary(self, date: str, total_fetched: int) -> str:
        """Generate summary when no high-scoring items were found."""
        return (
            f"# {LABELS['header']} - {date}\n\n"
            f"> {total_fetched}개 항목을 분석했지만 중요도 임계값을 넘은 항목이 없습니다.\n\n"
            + LABELS["empty_body"]
        )
