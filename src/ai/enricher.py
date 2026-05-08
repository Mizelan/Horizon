"""Content enrichment using AI (second-pass analysis).

For items that pass the score threshold, this module:
1. Searches the web for relevant context (via DuckDuckGo)
2. Feeds search results + item content to AI to generate grounded background knowledge
"""

import json
import re
import asyncio
from pathlib import Path
from typing import List, Optional
from tenacity import retry, stop_after_attempt, wait_exponential
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, MofNCompleteColumn
from ddgs import DDGS

from .cache import AIResultCache, build_item_cache_key
from .client import AIClient
from .prompts import (
    CONCEPT_EXTRACTION_SYSTEM, CONCEPT_EXTRACTION_USER,
    CONTENT_ENRICHMENT_SYSTEM, CONTENT_ENRICHMENT_USER,
)
from .utils import parse_json_response
from ..models import ContentItem

ENRICHMENT_PROMPT_VERSION = "enrichment-v1"
ENRICHMENT_METADATA_KEYS = (
    "title_ko",
    "detailed_summary_ko",
    "background_ko",
    "community_discussion_ko",
    "sources",
)


class ContentEnricher:
    """Enriches high-scoring content items with background knowledge."""

    def __init__(self, ai_client: AIClient):
        self.client = ai_client

    def _get_cache(self) -> AIResultCache | None:
        config = getattr(self.client, "config", None)
        if not config or not getattr(config, "cache_enabled", False):
            return None
        if not hasattr(config, "provider") or not hasattr(config, "model"):
            return None
        return AIResultCache(
            Path(getattr(config, "cache_dir")) / "enrichment.sqlite",
            ttl_hours=getattr(config, "cache_ttl_hours"),
            schema_version=getattr(config, "cache_schema_version"),
        )

    @staticmethod
    def _build_prompt_state(item: ContentItem, content_text: str, comments_text: str) -> str:
        return json.dumps(
            {
                "title": item.title,
                "url": str(item.url),
                "summary": item.ai_summary or item.title,
                "score": item.ai_score or 0,
                "reason": item.ai_reason or "",
                "tags": item.ai_tags,
                "content": content_text,
                "comments": comments_text,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    @staticmethod
    def _apply_enrichment_payload(item: ContentItem, payload: dict) -> None:
        for key in ENRICHMENT_METADATA_KEYS:
            if key in payload:
                item.metadata[key] = payload[key]

    @staticmethod
    def _owned_enrichment_payload(item: ContentItem) -> dict:
        return {
            key: item.metadata[key]
            for key in ENRICHMENT_METADATA_KEYS
            if key in item.metadata
        }

    async def enrich_batch(self, items: List[ContentItem]) -> None:
        """Enrich items in-place with background knowledge.

        Args:
            items: Content items to enrich (modified in-place)
        """
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            transient=True,
        ) as progress:
            task = progress.add_task("Enriching", total=len(items))

            for item in items:
                try:
                    await self._enrich_item(item)
                except Exception as e:
                    print(f"Error enriching item {item.id}: {e}")
                progress.advance(task)

    async def _web_search(self, query: str, max_results: int = 3, timeout_seconds: float = 8.0) -> list:
        """Search the web for context via DuckDuckGo.

        Returns:
            List of dicts with keys: title, url, body
        """
        def search_sync() -> list:
            ddgs = DDGS()
            results = ddgs.text(query, max_results=max_results)

            return [
                {"title": r.get("title", ""), "url": r.get("href", ""), "body": r.get("body", "")}
                for r in (results or [])
            ]

        try:
            return await asyncio.wait_for(
                asyncio.to_thread(search_sync),
                timeout=timeout_seconds,
            )
        except Exception:
            return []

    @staticmethod
    def _parse_json_response(response: str) -> Optional[dict]:
        """Try multiple strategies to extract a JSON object from an AI response.

        Returns the parsed dict, or None if all strategies fail.
        """
        return parse_json_response(response)

    async def _extract_concepts(self, item: ContentItem, content_text: str) -> List[str]:
        """Ask AI to identify concepts that need explanation.

        Args:
            item: Content item
            content_text: Extracted content text

        Returns:
            List of search queries for concepts that need explanation
        """
        user_prompt = CONCEPT_EXTRACTION_USER.format(
            title=item.title,
            summary=item.ai_summary or item.title,
            tags=", ".join(item.ai_tags) if item.ai_tags else "",
            content=content_text[:1000],
        )

        try:
            response = await self.client.complete(
                system=CONCEPT_EXTRACTION_SYSTEM,
                user=user_prompt,
            )
            result = self._parse_json_response(response)
            if result is None:
                return []
            queries = result.get("queries", [])
            return queries[:3]
        except Exception:
            return []

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=10)
    )
    async def _enrich_item(self, item: ContentItem) -> None:
        """Enrich a single item with background knowledge.

        Steps:
        1. Ask AI which concepts in the news need explanation
        2. Search the web for those concepts
        3. Ask AI to generate background based on search results

        Args:
            item: Content item to enrich (modified in-place via metadata)
        """
        # Extract content text and comments separately
        content_text = ""
        comments_text = ""
        if item.content:
            if "--- Top Comments ---" in item.content:
                main, comments_part = item.content.split("--- Top Comments ---", 1)
                content_text = main.strip()[:4000]
                comments_text = comments_part.strip()[:2000]
            else:
                content_text = item.content[:4000]

        cache = self._get_cache()
        cache_key = None
        if cache is not None:
            config = getattr(self.client, "config")
            prompt_state = self._build_prompt_state(item, content_text, comments_text)
            cache_key = build_item_cache_key(
                stage="enrichment",
                prompt_version=ENRICHMENT_PROMPT_VERSION,
                config=config,
                item=item,
                prompt_content=prompt_state,
                schema_version=getattr(config, "cache_schema_version"),
                extra={
                    "ai_score": item.ai_score,
                    "ai_reason": item.ai_reason,
                    "ai_summary": item.ai_summary,
                    "ai_tags": item.ai_tags,
                },
            )
            cached_payload = cache.get(cache_key)
            if cached_payload is not None:
                self._apply_enrichment_payload(item, cached_payload)
                return

        # Step 1: AI identifies concepts to explain
        queries = await self._extract_concepts(item, content_text)

        # Step 2: Search web for each concept
        all_results = []
        web_sections = []
        for query in queries:
            results = await self._web_search(query)
            all_results.extend(results)
            if results:
                lines = [f"- [{r['title']}]({r['url']}): {r['body']}" for r in results]
                web_sections.append(f"**{query}:**\n" + "\n".join(lines))
        web_context = "\n\n".join(web_sections) if web_sections else ""

        # Index of available URLs for citation validation
        available_urls = {r["url"]: r["title"] for r in all_results if r.get("url")}

        # Step 3: AI generates background grounded in search results
        user_prompt = CONTENT_ENRICHMENT_USER.format(
            title=item.title,
            url=str(item.url),
            summary=item.ai_summary or item.title,
            score=item.ai_score or 0,
            reason=item.ai_reason or "",
            tags=", ".join(item.ai_tags) if item.ai_tags else "",
            content=content_text,
            comments_section=f"\n**Community Comments:**\n{comments_text}" if comments_text else "",
            web_context=web_context or "No web search results available.",
        )

        response = await self.client.complete(
            system=CONTENT_ENRICHMENT_SYSTEM,
            user=user_prompt,
        )

        # Parse JSON response with robust fallback
        result = self._parse_json_response(response)
        if result is None:
            # Gracefully degrade: skip enrichment instead of raising
            # (raising would trigger retries that won't help with a parse error)
            print(f"Warning: could not parse enrichment response for {item.id}, skipping enrichment")
            return

        # Combine structured Korean sub-fields into the summary used by renderers.
        if result.get("title_ko"):
            val = result["title_ko"]
            item.metadata["title_ko"] = val.get("text") or str(val) if isinstance(val, dict) else str(val)

        parts = []
        for field in ("whats_new", "why_it_matters", "key_details"):
            text = result.get(f"{field}_ko", "").strip()
            if text:
                parts.append(text)
        if parts:
            detailed_summary = " ".join(parts)
            item.metadata["detailed_summary_ko"] = detailed_summary

        if result.get("background_ko"):
            val = result["background_ko"]
            background = val.get("text") or str(val) if isinstance(val, dict) else str(val)
            item.metadata["background_ko"] = background

        if result.get("community_discussion_ko"):
            val = result["community_discussion_ko"]
            community_discussion = val.get("text") or str(val) if isinstance(val, dict) else str(val)
            item.metadata["community_discussion_ko"] = community_discussion

        # Store citation sources — only URLs that actually came from our search results
        if result.get("sources") and available_urls:
            valid = [
                {"url": u, "title": available_urls[u]}
                for u in result["sources"]
                if u in available_urls
            ]
            if valid:
                item.metadata["sources"] = valid

        if cache is not None and cache_key is not None:
            cache.set(cache_key, self._owned_enrichment_payload(item))
