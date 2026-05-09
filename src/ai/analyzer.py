"""Content analysis using AI."""

import asyncio
import json
import re
from pathlib import Path
from typing import List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, MofNCompleteColumn

from .cache import AIResultCache, build_item_cache_key
from .client import AIClient
from .prompts import CONTENT_ANALYSIS_SYSTEM, CONTENT_ANALYSIS_USER
from .utils import parse_json_response
from ..models import ContentItem

DEFAULT_THROTTLE_SEC = 0.0
ANALYSIS_PROMPT_VERSION = "analysis-v2"


class ContentAnalyzer:
    """Analyzes content items using AI to determine importance."""

    def __init__(self, ai_client: AIClient):
        self.client = ai_client

    @staticmethod
    def _parse_json_response(response: str) -> Optional[dict]:
        """Try multiple strategies to extract a JSON object from an AI response.

        Returns the parsed dict, or None if all strategies fail.
        """
        return parse_json_response(response)

    def _get_throttle_sec(self) -> float:
        """Return the configured inter-item throttle, clamped to zero or above."""
        config = getattr(self.client, "config", None)
        throttle_sec = getattr(config, "throttle_sec", DEFAULT_THROTTLE_SEC)
        return max(throttle_sec, 0.0)

    def _get_cache(self) -> AIResultCache | None:
        config = getattr(self.client, "config", None)
        if not config or not getattr(config, "cache_enabled", False):
            return None
        if not hasattr(config, "provider") or not hasattr(config, "model"):
            return None
        return AIResultCache(
            Path(getattr(config, "cache_dir")) / "analysis.sqlite",
            ttl_hours=getattr(config, "cache_ttl_hours"),
            schema_version=getattr(config, "cache_schema_version"),
        )

    def _apply_analysis_payload(self, item: ContentItem, payload: dict) -> None:
        item.ai_score = float(payload.get("ai_score", payload.get("score", 0)))
        item.ai_reason = payload.get("ai_reason", payload.get("reason", ""))
        item.ai_summary = payload.get("ai_summary", payload.get("summary", item.title))
        item.ai_tags = payload.get("ai_tags", payload.get("tags", []))

    async def analyze_batch(self, items: List[ContentItem]) -> List[ContentItem]:
        throttle_sec = self._get_throttle_sec()
        analyzed_items = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            transient=True,
        ) as progress:
            task = progress.add_task("Analyzing", total=len(items))

            for index, item in enumerate(items):
                try:
                    await self._analyze_item(item)
                    analyzed_items.append(item)
                except Exception as e:
                    print(f"Error analyzing item {item.id}: {e}")
                    item.ai_score = 0.0
                    item.ai_reason = "Analysis failed"
                    item.ai_summary = item.title
                    analyzed_items.append(item)
                progress.advance(task)
                if throttle_sec > 0 and index < len(items) - 1:
                    await asyncio.sleep(throttle_sec)

        return analyzed_items

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=10)
    )
    async def _analyze_item(self, item: ContentItem) -> None:
        """Analyze a single content item.

        Args:
            item: Content item to analyze (modified in-place)
        """
        # Prepare content section
        content_section = ""
        if item.content:
            # Split off comments if present
            content_text = item.content
            if "--- Top Comments ---" in content_text:
                main, comments_part = content_text.split("--- Top Comments ---", 1)
                content_section = f"Content: {main.strip()[:800]}"
            else:
                content_section = f"Content: {content_text[:1000]}"

        # Prepare discussion section (comments, engagement)
        discussion_parts = []
        if item.content and "--- Top Comments ---" in item.content:
            comments_part = item.content.split("--- Top Comments ---", 1)[1]
            discussion_parts.append(f"Community Comments:\n{comments_part[:1500]}")

        meta = item.metadata
        engagement_items = []
        if meta.get("score"):
            engagement_items.append(f"score: {meta['score']}")
        if meta.get("descendants"):
            engagement_items.append(f"{meta['descendants']} comments")
        if meta.get("favorite_count"):
            engagement_items.append(f"{meta['favorite_count']} likes")
        if meta.get("retweet_count"):
            engagement_items.append(f"{meta['retweet_count']} retweets")
        if meta.get("reply_count"):
            engagement_items.append(f"{meta['reply_count']} replies")
        if meta.get("views"):
            engagement_items.append(f"{meta['views']} views")
        if meta.get("bookmarks"):
            engagement_items.append(f"{meta['bookmarks']} bookmarks")
        if meta.get("upvote_ratio"):
            engagement_items.append(f"upvote ratio: {meta['upvote_ratio']:.0%}")
        if engagement_items:
            discussion_parts.append(f"Engagement: {', '.join(engagement_items)}")
        if meta.get("discussion_url"):
            discussion_parts.append(f"Discussion: {meta['discussion_url']}")
        if meta.get("community_note"):
            discussion_parts.append(f"Community Note: {meta['community_note']}")

        discussion_section = "\n".join(discussion_parts) if discussion_parts else ""

        # Generate user prompt
        user_prompt = CONTENT_ANALYSIS_USER.format(
            title=item.title,
            source=f"{item.source_type.value}",
            author=item.author or "Unknown",
            url=str(item.url),
            content_section=content_section,
            discussion_section=discussion_section
        )

        cache = self._get_cache()
        cache_key = None
        if cache is not None:
            config = getattr(self.client, "config")
            cache_key = build_item_cache_key(
                stage="analysis",
                prompt_version=ANALYSIS_PROMPT_VERSION,
                config=config,
                item=item,
                prompt_content=user_prompt,
                schema_version=getattr(config, "cache_schema_version"),
            )
            cached_payload = cache.get(cache_key)
            if cached_payload is not None:
                self._apply_analysis_payload(item, cached_payload)
                return

        # Get AI completion
        response = await self.client.complete(
            system=CONTENT_ANALYSIS_SYSTEM,
            user=user_prompt,
        )

        # Parse JSON response with robust fallback
        result = self._parse_json_response(response)
        if result is None:
            print(f"Warning: could not parse analysis response for {item.id}, using defaults")
            item.ai_score = 0.0
            item.ai_reason = "Analysis response parse failed"
            item.ai_summary = item.title
            item.ai_tags = []
            return

        # Update item with analysis results
        self._apply_analysis_payload(item, result)
        if cache is not None and cache_key is not None:
            cache.set(cache_key, {
                "ai_score": item.ai_score,
                "ai_reason": item.ai_reason,
                "ai_summary": item.ai_summary,
                "ai_tags": item.ai_tags,
            })
