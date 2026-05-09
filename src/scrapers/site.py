"""Scraper for websites without RSS feeds (Anthropic Blog, Tildes, Refetch)."""

import asyncio
import json
import logging
import re
import shutil
import sys as sys_module
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from .base import BaseScraper
from ..models import ContentItem, SiteConfig, SiteSourceConfig, SourceType

logger = logging.getLogger(__name__)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/135.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

PLAYWRIGHT_HELPER = Path(__file__).parent / "playwright_fetch.py"


class SiteScraper(BaseScraper):
    """Scraper for websites without RSS feeds.

    Supports multiple site types with different parsing strategies:
    - anthropic_blog: Server-rendered Next.js blog page
    - tildes: Server-rendered link-aggregator listing
    - refetch: Client-rendered SPA (requires Playwright subprocess)
    """

    def __init__(self, config: SiteConfig, http_client: httpx.AsyncClient):
        super().__init__(config.model_dump(), http_client)
        self.site_config = config
        self._playwright_python: Optional[str] = None

    async def fetch(self, since: datetime) -> List[ContentItem]:
        if not self.site_config.enabled:
            return []

        tasks = []
        for site in self.site_config.sites:
            if not site.enabled:
                continue
            tasks.append(self._fetch_site(site, since))

        if not tasks:
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)
        items: List[ContentItem] = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning("Error fetching site: %s", result)
            elif isinstance(result, list):
                items.extend(result)
        return items

    async def _fetch_site(self, site: SiteSourceConfig, since: datetime) -> List[ContentItem]:
        try:
            if site.type == "anthropic_blog":
                return await self._fetch_anthropic_blog(site, since)
            elif site.type == "tildes":
                return await self._fetch_tildes(site, since)
            elif site.type == "refetch":
                return await self._fetch_refetch(site, since)
            else:
                logger.warning("Unknown site type: %s", site.type)
                return []
        except Exception as exc:
            logger.warning("Error fetching %s (%s): %s", site.name, site.type, exc)
            return []

    # ── Anthropic Blog ──────────────────────────────────────────────────

    async def _fetch_anthropic_blog(self, site: SiteSourceConfig, since: datetime) -> List[ContentItem]:
        response = await self.client.get(
            str(site.url), headers=BROWSER_HEADERS, follow_redirects=True, timeout=30.0
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        items: List[ContentItem] = []
        seen_urls: set = set()

        for article_tag in soup.find_all("article"):
            link = article_tag.find("a", href=True)
            if not link:
                continue
            href = link["href"]
            if not href.startswith("/engineering/") and "/engineering/" not in href:
                continue

            full_url = urljoin(str(site.url), href)
            if full_url in seen_urls:
                continue
            seen_urls.add(full_url)

            title = (link.get("title") or link.get_text(strip=True) or "").strip()
            if not title:
                continue

            article_text = article_tag.get_text(separator=" ", strip=True)
            published_at = self._extract_anthropic_date(article_text) or datetime.now(timezone.utc)
            if published_at < since:
                continue

            items.append(
                ContentItem(
                    id=self._generate_id(SourceType.SITE.value, site.type, full_url),
                    source_type=SourceType.SITE,
                    title=title,
                    url=full_url,
                    content="",
                    author="Anthropic",
                    published_at=published_at,
                    metadata={
                        "site_name": site.name,
                        "site_type": site.type,
                        "category": site.category,
                    },
                )
            )
            if len(items) >= site.fetch_limit:
                break

        # Enrich with article body text (rate-limited)
        if items:
            sem = asyncio.Semaphore(3)

            async def _fetch_article(item: ContentItem) -> None:
                async with sem:
                    try:
                        resp = await self.client.get(
                            str(item.url), headers=BROWSER_HEADERS, follow_redirects=True, timeout=15.0
                        )
                        resp.raise_for_status()
                        art_soup = BeautifulSoup(resp.text, "html.parser")
                        paragraphs = art_soup.find_all(["p", "h2", "h3", "li"])
                        body = "\n\n".join(
                            p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)
                        )
                        if body:
                            item.content = body

                        time_tag = art_soup.find("time")
                        if time_tag:
                            dt = time_tag.get("datetime") or time_tag.get_text(strip=True)
                            if dt:
                                parsed = self._try_parse_absolute_date(dt)
                                if parsed:
                                    item.published_at = parsed
                    except Exception as exc:
                        logger.debug("Failed to fetch article body %s: %s", item.url, exc)

            await asyncio.gather(*[_fetch_article(item) for item in items], return_exceptions=True)

        return items

    @staticmethod
    def _extract_anthropic_date(text: str) -> Optional[datetime]:
        """Extract date like 'Apr 08, 2026' from article text."""
        m = re.search(r"([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})", text)
        if m:
            return SiteScraper._try_parse_absolute_date(m.group(1))
        return None

    @staticmethod
    def _try_parse_absolute_date(text: str) -> Optional[datetime]:
        from dateutil import parser as dateparser
        try:
            dt = dateparser.parse(text)
            if dt and not dt.tzinfo:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

    # ── Tildes ──────────────────────────────────────────────────────────

    async def _fetch_tildes(self, site: SiteSourceConfig, since: datetime) -> List[ContentItem]:
        response = await self.client.get(
            str(site.url), headers=BROWSER_HEADERS, follow_redirects=True, timeout=30.0
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        items: List[ContentItem] = []

        for topic_tag in soup.select("article.topic"):
            title_el = topic_tag.select_one("h1 a, .topic-title a, a")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            url = title_el.get("href", "")
            if not title or not url:
                continue
            full_url = urljoin(str(site.url), url)

            group_el = topic_tag.select_one(".topic-group, .link-group")
            group = group_el.get_text(strip=True) if group_el else ""

            comments_el = topic_tag.select_one(".topic-info-comments")
            comment_count = 0
            if comments_el:
                m = re.search(r"(\d+)\s*comments?", comments_el.get_text())
                comment_count = int(m.group(1)) if m else 0

            votes_el = topic_tag.select_one(".topic-voting")
            vote_count = 0
            if votes_el:
                m = re.search(r"(\d+)", votes_el.get_text())
                vote_count = int(m.group(1)) if m else 0

            info_el = topic_tag.select_one(".topic-info")
            published_at = datetime.now(timezone.utc)
            if info_el:
                time_text = info_el.get_text()
                relative = self._parse_relative_time(time_text)
                if relative:
                    published_at = relative

            if published_at < since:
                continue

            items.append(
                ContentItem(
                    id=self._generate_id(SourceType.SITE.value, site.type, full_url),
                    source_type=SourceType.SITE,
                    title=title,
                    url=full_url,
                    content="",
                    author=group or "Tildes",
                    published_at=published_at,
                    metadata={
                        "site_name": site.name,
                        "site_type": site.type,
                        "category": site.category,
                        "group": group,
                        "score": vote_count,
                        "num_comments": comment_count,
                    },
                )
            )
            if len(items) >= site.fetch_limit:
                break

        return items

    # ── Refetch ─────────────────────────────────────────────────────────

    async def _fetch_refetch(self, site: SiteSourceConfig, since: datetime) -> List[ContentItem]:
        python_path = await self._resolve_playwright_python()
        if not python_path:
            logger.warning("Playwright not available, skipping Refetch: %s", site.name)
            return []

        timeout_ms = self.site_config.timeout_seconds * 1000

        try:
            process = await asyncio.create_subprocess_exec(
                python_path,
                str(PLAYWRIGHT_HELPER),
                str(site.url),
                str(timeout_ms),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.site_config.timeout_seconds + 10,
            )
        except (TimeoutError, asyncio.TimeoutError):
            logger.warning("Playwright timed out for Refetch: %s", site.name)
            return []
        except Exception as exc:
            logger.warning("Playwright subprocess error for %s: %s", site.name, exc)
            return []

        if process.returncode != 0:
            msg = stderr.decode(errors="replace").strip()
            logger.warning("Playwright failed for %s: %s", site.name, msg)
            return []

        try:
            data = json.loads(stdout.decode(errors="replace"))
        except json.JSONDecodeError:
            logger.warning("Invalid JSON from Playwright for %s", site.name)
            return []

        if "error" in data:
            logger.warning("Playwright error for %s: %s", site.name, data["error"])
            return []

        items: List[ContentItem] = []
        seen_urls: set = set()
        for article in data.get("articles", []):
            title = (article.get("title") or "").strip()
            url = (article.get("url") or "").strip()
            if not title or not url or url in seen_urls:
                continue
            seen_urls.add(url)

            date_text = article.get("date_text")
            published_at = datetime.now(timezone.utc)
            if date_text:
                parsed = self._parse_relative_time(date_text)
                if parsed:
                    published_at = parsed

            if published_at < since:
                continue

            items.append(
                ContentItem(
                    id=self._generate_id(SourceType.SITE.value, site.type, url),
                    source_type=SourceType.SITE,
                    title=title,
                    url=url,
                    content="",
                    author="Refetch",
                    published_at=published_at,
                    metadata={
                        "site_name": site.name,
                        "site_type": site.type,
                        "category": site.category,
                    },
                )
            )
            if len(items) >= site.fetch_limit:
                break

        return items

    # ── Utilities ───────────────────────────────────────────────────────

    async def _resolve_playwright_python(self) -> Optional[str]:
        """Find a Python interpreter with Playwright installed."""
        if self._playwright_python:
            return self._playwright_python

        candidates = []
        if self.site_config.playwright_python:
            candidates.append(self.site_config.playwright_python)
        candidates.append(sys_module.executable)
        candidates.append(shutil.which("python3") or "")
        candidates.append("/usr/bin/python3")
        candidates.append("/Library/Frameworks/Python.framework/Versions/3.11/bin/python3")

        for candidate in candidates:
            if not candidate:
                continue
            try:
                proc = await asyncio.create_subprocess_exec(
                    candidate,
                    "-c",
                    "import playwright; print('ok')",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10.0)
                if proc.returncode == 0 and stdout.decode().strip() == "ok":
                    self._playwright_python = candidate
                    return candidate
            except Exception:
                continue

        return None

    @staticmethod
    def _parse_relative_time(text: str) -> Optional[datetime]:
        """Parse relative time strings like 'X hours ago', 'X days ago'."""
        m = re.search(r"(\d+)\s+(hour|day|minute|min|second)s?\s+ago", text, re.IGNORECASE)
        if not m:
            return None
        amount = int(m.group(1))
        unit = m.group(2).lower()
        now = datetime.now(timezone.utc)
        if "hour" in unit:
            return now - timedelta(hours=amount)
        elif "day" in unit:
            return now - timedelta(days=amount)
        elif "minute" in unit or "min" in unit:
            return now - timedelta(minutes=amount)
        elif "second" in unit:
            return now - timedelta(seconds=amount)
        return None
