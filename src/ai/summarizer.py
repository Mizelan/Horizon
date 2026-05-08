"""Daily summary generation — pure programmatic rendering."""

import html
import re
from typing import List, Dict
from urllib.parse import parse_qs, urlparse

from ..models import ContentItem


_CJK = r"[\u4e00-\u9fff\u3400-\u4dbf]"
_ASCII = r"[A-Za-z0-9]"


def _pangu(text: str) -> str:
    """Insert a space between CJK and ASCII letters/digits (Pangu spacing)."""
    text = re.sub(rf"({_CJK})({_ASCII})", r"\1 \2", text)
    text = re.sub(rf"({_ASCII})({_CJK})", r"\1 \2", text)
    return text


LABELS = {
    "en": {
        "header": "Horizon Daily",
        "source": "Source",
        "background": "Background",
        "discussion": "Discussion",
        "references": "References",
        "tags": "Tags",
        "tab_sites": "Subscribed Sites",
        "tab_youtube": "YouTube",
        "empty_sites": "No subscribed site items were selected.",
        "empty_youtube": "No YouTube items were selected.",
        "empty_body": (
            "No significant developments today. This might indicate:\n"
            "- A quiet day in your tracked sources\n"
            "- The AI score threshold is too high\n"
            "- Your information sources need expansion\n\n"
            "Consider:\n"
            "1. Lowering the `ai_score_threshold` in config.json\n"
            "2. Adding more diverse information sources\n"
            "3. Checking if the AI model is working correctly\n"
        ),
    },
    "zh": {
        "header": "Horizon 每日速递",
        "source": "来源",
        "background": "背景",
        "discussion": "社区讨论",
        "references": "参考链接",
        "tags": "标签",
        "tab_sites": "订阅网站",
        "tab_youtube": "YouTube",
        "empty_sites": "没有入选的订阅网站内容。",
        "empty_youtube": "没有入选的 YouTube 内容。",
        "empty_body": (
            "今日暂无重要动态，可能原因：\n"
            "- 今天关注的信息源较平静\n"
            "- AI 评分阈值设置过高\n"
            "- 信息源种类有待扩充\n\n"
            "建议：\n"
            "1. 在 config.json 中降低 `ai_score_threshold`\n"
            "2. 添加更多多样化的信息源\n"
            "3. 检查 AI 模型是否正常工作\n"
        ),
    },
    "ko": {
        "header": "Horizon 데일리",
        "source": "출처",
        "background": "배경",
        "discussion": "토론",
        "references": "참고 링크",
        "tags": "태그",
        "tab_sites": "구독 사이트",
        "tab_youtube": "YouTube",
        "empty_sites": "선별된 구독 사이트 항목이 없습니다.",
        "empty_youtube": "선별된 YouTube 항목이 없습니다.",
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
    },
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
        language: str = "en",
    ) -> str:
        """Generate daily summary in Markdown format.

        Items are rendered in score-descending order (already sorted by orchestrator).

        Args:
            items: High-scoring content items (already enriched)
            date: Date string (YYYY-MM-DD)
            total_fetched: Total number of items fetched before filtering
            language: Output language, such as "ko" or "en"

        Returns:
            str: Markdown formatted summary
        """
        labels = LABELS.get(language, LABELS["en"])

        if not items:
            return self._generate_empty_summary(date, total_fetched, labels, language)

        if language == "ko":
            header = (
                f"# {labels['header']} - {date}\n\n"
                f"> {total_fetched}개 항목 중 {len(items)}개의 중요 콘텐츠를 선별했습니다\n\n"
                "---\n\n"
            )
        else:
            header = (
                f"# {labels['header']} - {date}\n\n"
                f"> From {total_fetched} items, {len(items)} important content pieces were selected\n\n"
                "---\n\n"
            )

        indexed_items = list(enumerate(items, start=1))
        site_items = [(i, item) for i, item in indexed_items if item.source_type.value != "youtube"]
        youtube_items = [(i, item) for i, item in indexed_items if item.source_type.value == "youtube"]

        content = self._format_tabbed_sections(site_items, youtube_items, labels, language)

        return header + content

    def generate_webhook_overview(
        self,
        items: List[ContentItem],
        date: str,
        total_fetched: int,
        language: str = "en",
    ) -> str:
        """Generate a compact overview for multi-message webhook delivery."""
        labels = LABELS.get(language, LABELS["en"])
        if not items:
            return self._generate_empty_summary(date, total_fetched, labels, language)

        if language == "ko":
            header = (
                f"# {labels['header']} - {date}\n\n"
                f"> 수집된 {total_fetched}개 항목 중 {len(items)}개의 중요 항목을 선별했습니다.\n\n"
                "관심 있는 제목만 골라 읽을 수 있도록 상세 내용은 항목별로 전송됩니다.\n\n"
            )
        elif language == "zh":
            header = (
                f"# {labels['header']} - {date}\n\n"
                f"> 从 {total_fetched} 条内容中筛选出 {len(items)} 条重要资讯。\n\n"
                "下面会按新闻逐条发送详情，你可以只看感兴趣的标题。\n\n"
            )
        else:
            header = (
                f"# {labels['header']} - {date}\n\n"
                f"> Selected {len(items)} important items from {total_fetched} fetched items.\n\n"
                "Details will be sent item by item so you can read only the topics you care about.\n\n"
            )

        entries = []
        for i, item in enumerate(items, start=1):
            title = str(item.metadata.get(f"title_{language}") or item.title).replace("[", "(").replace("]", ")")
            if language == "zh":
                title = _pangu(title)
            score = item.ai_score or "?"
            entries.append(f"{i}. [{title}]({item.url}) \u2b50\ufe0f {score}/10")

        return header + "\n".join(entries)

    def generate_webhook_item(
        self,
        item: ContentItem,
        language: str,
        index: int,
        total: int,
    ) -> str:
        """Generate one item message for multi-message webhook delivery."""
        labels = LABELS.get(language, LABELS["en"])
        if language == "ko":
            prefix = f"{index}/{total} 항목\n\n"
        elif language == "zh":
            prefix = f"第 {index}/{total} 条\n\n"
        else:
            prefix = f"Item {index}/{total}\n\n"
        return prefix + self._format_item(
            item,
            labels,
            language,
            index,
            include_media=False,
        ).rstrip("-\n ")

    def _format_tabbed_sections(
        self,
        site_items: List[tuple[int, ContentItem]],
        youtube_items: List[tuple[int, ContentItem]],
        labels: dict,
        language: str,
    ) -> str:
        """Render one-page source tabs for subscribed-site and YouTube items."""
        active_group = "sites" if site_items else "youtube"
        site_active = "true" if active_group == "sites" else "false"
        youtube_active = "true" if active_group == "youtube" else "false"
        site_class = "source-tab active" if active_group == "sites" else "source-tab"
        youtube_class = "source-tab active" if active_group == "youtube" else "source-tab"
        return (
            '<div class="source-tabs" data-source-tabs>\n'
            '  <div class="source-tablist" role="tablist" aria-label="Source groups">\n'
            f'    <button type="button" class="{site_class}" role="tab" '
            f'aria-selected="{site_active}" aria-controls="source-panel-sites" '
            f'id="source-tab-sites" data-source-tab="sites">{labels["tab_sites"]} '
            f'<span class="source-tab-count">{len(site_items)}</span></button>\n'
            f'    <button type="button" class="{youtube_class}" role="tab" '
            f'aria-selected="{youtube_active}" aria-controls="source-panel-youtube" '
            f'id="source-tab-youtube" data-source-tab="youtube">{labels["tab_youtube"]} '
            f'<span class="source-tab-count">{len(youtube_items)}</span></button>\n'
            "  </div>\n"
            f'{self._format_tab_panel("sites", site_items, labels, language, active=active_group == "sites")}'
            f'{self._format_tab_panel("youtube", youtube_items, labels, language, active=active_group == "youtube")}'
            "</div>\n\n"
        )

    def _format_tab_panel(
        self,
        group: str,
        indexed_items: List[tuple[int, ContentItem]],
        labels: dict,
        language: str,
        *,
        active: bool,
    ) -> str:
        """Render one tab panel with markdown enabled for Jekyll/kramdown."""
        hidden = "" if active else " hidden"
        active_class = " active" if active else ""
        empty_label = labels["empty_youtube"] if group == "youtube" else labels["empty_sites"]
        panel = (
            f'  <section id="source-panel-{group}" '
            f'class="source-tab-panel{active_class}" role="tabpanel" '
            f'aria-labelledby="source-tab-{group}"{hidden} markdown="1">\n\n'
        )
        if not indexed_items:
            panel += f"{empty_label}\n\n"
        else:
            panel += self._format_toc(indexed_items, language)
            panel += "".join(
                self._format_item(item, labels, language, index, include_media=True)
                for index, item in indexed_items
            )
        return panel + "  </section>\n"

    @staticmethod
    def _format_toc(indexed_items: List[tuple[int, ContentItem]], language: str) -> str:
        """Render a per-tab table of contents."""
        toc_entries = []
        for index, item in indexed_items:
            _t = item.metadata.get(f"title_{language}") or item.title
            title = str(_t).replace("[", "(").replace("]", ")")
            if language == "zh":
                title = _pangu(title)
            score = item.ai_score or "?"
            favicon = DailySummarizer._favicon_html(item)
            toc_entries.append(f"{index}. {favicon} [{title}](#item-{index}) \u2b50\ufe0f {score}/10")
        return "\n".join(toc_entries) + "\n\n---\n\n"

    def _format_item(
        self,
        item: ContentItem,
        labels: dict,
        language: str,
        index: int,
        *,
        include_media: bool,
    ) -> str:
        """Format a single ContentItem into Markdown."""
        _title = item.metadata.get(f"title_{language}") or item.title
        title = str(_title).replace("[", "(").replace("]", ")")
        url = str(item.url)
        score = item.ai_score or "?"
        meta = item.metadata

        summary = (
            meta.get(f"detailed_summary_{language}")
            or meta.get("detailed_summary")
            or item.ai_summary
            or ""
        )
        background = meta.get(f"background_{language}") or meta.get("background") or ""
        discussion = (
            meta.get(f"community_discussion_{language}")
            or meta.get("community_discussion")
            or ""
        )

        if language == "zh":
            title = _pangu(title)
            summary = _pangu(summary)
            background = _pangu(background)
            discussion = _pangu(discussion)
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
        source_line = " \u00b7 ".join(source_parts)  # ·

        discussion_url = meta.get("discussion_url")
        if discussion_url:
            discussion_url = str(discussion_url)
            if discussion_url != url:
                source_line += f' · [{labels["discussion"]}]({discussion_url})'

        lines = [
            f'<a id="item-{index}"></a>',
            f"## {favicon}[{title}]({url}) \u2b50\ufe0f {score}/10",  # ⭐️
            "",
            summary,
            "",
            source_line,
        ]

        if include_media:
            embed = self._youtube_embed_html(item, title)
            if embed:
                lines.extend(["", embed])

        if background:
            lines.append("")
            lines.append(f"**{labels['background']}**: {background}")

        sources = meta.get("sources") or []
        if sources:
            items_html = "".join(f'<li><a href="{s["url"]}">{s["title"]}</a></li>\n' for s in sources)
            lines += [
                "",
                f'<details><summary>{labels["references"]}</summary>\n<ul>\n{items_html}\n</ul>\n</details>',
            ]

        if discussion:
            lines.append("")
            lines.append(f"**{labels['discussion']}**: {discussion}")

        if item.ai_tags:
            tags_str = ", ".join([f"`#{t}`" for t in item.ai_tags])
            lines.append("")
            lines.append(f"**{labels['tags']}**: {tags_str}")

        lines.append("")
        lines.append("---")

        return "\n".join(lines) + "\n\n"

    @staticmethod
    def _favicon_html(item: ContentItem) -> str:
        """Render an icon for the subscription/source domain."""
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

    def _generate_empty_summary(self, date: str, total_fetched: int, labels: dict, language: str) -> str:
        """Generate summary when no high-scoring items were found."""
        if language == "ko":
            return (
                f"# {labels['header']} - {date}\n\n"
                f"> {total_fetched}개 항목을 분석했지만 중요도 임계값을 넘은 항목이 없습니다.\n\n"
                + labels["empty_body"]
            )

        return (
            f"# {labels['header']} - {date}\n\n"
            f"> Analyzed {total_fetched} items, but none met the importance threshold.\n\n"
            + labels["empty_body"]
        )
