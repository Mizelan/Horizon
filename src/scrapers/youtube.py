"""YouTube scraper implementation using yt-dlp metadata output."""

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from typing import List, Optional

import httpx

from .base import BaseScraper
from ..models import ContentItem, SourceType, YouTubeChannelConfig, YouTubeConfig

logger = logging.getLogger(__name__)


class YouTubeScraper(BaseScraper):
    """Scraper for YouTube channel metadata."""

    def __init__(self, config: YouTubeConfig, http_client: httpx.AsyncClient):
        """Initialize YouTube scraper."""
        super().__init__({"config": config}, http_client)

    async def fetch(self, since: datetime) -> List[ContentItem]:
        """Fetch YouTube videos published since the given time."""
        config: YouTubeConfig = self.config["config"]
        if not config.enabled:
            return []

        items: List[ContentItem] = []
        for channel in config.channels:
            if not channel.enabled:
                continue
            items.extend(await self._fetch_channel(channel, since, config.timeout_seconds))

        return items

    async def _fetch_channel(
        self,
        channel: YouTubeChannelConfig,
        since: datetime,
        timeout_seconds: int,
    ) -> List[ContentItem]:
        """Fetch metadata rows from a single YouTube channel."""
        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "yt_dlp",
                "--dump-json",
                "--no-download",
                "--remote-components", "ejs:github",
                "--playlist-end",
                str(channel.fetch_limit),
                self._videos_url(str(channel.url)),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout_seconds,
            )
        except (TimeoutError, asyncio.TimeoutError):
            logger.warning("Timed out fetching YouTube channel %s", channel.name)
            return []
        except Exception as exc:
            logger.warning("Error starting YouTube fetch for %s: %s", channel.name, exc)
            return []

        stdout_text = stdout.decode(errors="replace")
        items = self._parse_stdout(stdout_text, channel, since)

        if process.returncode != 0 and not items:
            message = stderr.decode(errors="replace").strip()
            logger.warning("Error fetching YouTube channel %s: %s", channel.name, message)
            return []
        elif process.returncode != 0 and items:
            stderr_text = stderr.decode(errors="replace").strip()
            logger.warning(
                "YouTube channel %s: partial fetch (%d items, stderr: %.200s)",
                channel.name, len(items), stderr_text,
            )

        return items

    def _parse_stdout(
        self,
        stdout: str,
        channel: YouTubeChannelConfig,
        since: datetime,
    ) -> List[ContentItem]:
        """Parse yt-dlp JSON lines into content items."""
        items: List[ContentItem] = []
        since = self._ensure_aware(since)

        for line in stdout.splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Skipping invalid YouTube metadata for %s", channel.name)
                continue

            published_at = self._parse_published_at(row)
            if not published_at or published_at < since:
                continue

            video_id = str(row.get("id") or row.get("display_id") or hash(row.get("url", "")))
            video_url = row.get("webpage_url") or row.get("url") or str(channel.url)
            item = ContentItem(
                id=self._generate_id(SourceType.YOUTUBE.value, "video", video_id),
                source_type=SourceType.YOUTUBE,
                title=row.get("title") or "Untitled",
                url=video_url,
                content=row.get("description") or "",
                author=row.get("uploader") or row.get("channel") or channel.name,
                published_at=published_at,
                metadata={
                    "channel_name": channel.name,
                    "channel_id": row.get("channel_id"),
                    "channel_url": str(channel.url),
                    "video_id": video_id,
                    "upload_date": row.get("upload_date"),
                    "duration": row.get("duration"),
                    "view_count": row.get("view_count"),
                    "like_count": row.get("like_count"),
                    "category": channel.category,
                },
            )
            items.append(item)

        return items

    def _parse_published_at(self, row: dict) -> Optional[datetime]:
        """Parse yt-dlp timestamp or upload_date into a timezone-aware datetime."""
        timestamp = row.get("timestamp")
        if timestamp is not None:
            try:
                return datetime.fromtimestamp(float(timestamp), tz=timezone.utc)
            except (TypeError, ValueError, OSError):
                pass

        upload_date = row.get("upload_date")
        if upload_date:
            try:
                return datetime.strptime(str(upload_date), "%Y%m%d").replace(tzinfo=timezone.utc)
            except ValueError:
                return None

        return None

    def _videos_url(self, url: str) -> str:
        """Use the channel videos tab unless the URL already names a videos feed."""
        normalized = url.rstrip("/")
        if normalized.endswith("/videos"):
            return normalized
        if "youtube.com/watch" in normalized or "youtu.be/" in normalized:
            return normalized
        return f"{normalized}/videos"

    def _ensure_aware(self, value: datetime) -> datetime:
        """Treat naive datetimes as UTC for source filtering."""
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
