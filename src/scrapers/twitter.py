"""Twitter scraper with swappable client backends (bird CLI, twitter-cli, etc.)."""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from html import unescape
from typing import List, Optional

from .base import BaseScraper
from ..models import ContentItem, SourceType, TwitterConfig

logger = logging.getLogger(__name__)


# ── Pluggable client interface ──────────────────────────────────────────

class TwitterClient(ABC):
    """Abstract interface for fetching tweet data from X/Twitter.

    Implementations can wrap any CLI tool (bird, twitter-cli, etc.) or
    library that provides raw tweet dicts.  Subprocess-based clients handle
    their own auth (browser cookies, env vars, etc.).
    """

    @abstractmethod
    async def fetch_user_tweets(self, username: str, limit: int) -> list:
        """Return raw tweet dicts from *username*'s timeline."""
        ...

    @abstractmethod
    async def fetch_replies(self, tweet_id: str) -> list:
        """Return raw reply dicts for the given *tweet_id*."""
        ...


# ── Bird CLI client ────────────────────────────────────────────────────

class BirdTwitterClient(TwitterClient):
    """Twitter client backed by the ``bird`` CLI (X GraphQL API).

    Requires ``bird`` to be installed and authenticated (Chrome cookies
    or ``~/.config/bird/config.json5``).
    """

    async def fetch_user_tweets(self, username: str, limit: int) -> list:
        count = max(20, limit)
        proc = await asyncio.create_subprocess_exec(
            "bird", "user-tweets", f"@{username}", "-n", str(count), "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.warning("bird user-tweets @%s failed (exit %d): %s",
                           username, proc.returncode, stderr.decode().strip())
            return []
        try:
            return json.loads(stdout)
        except json.JSONDecodeError as exc:
            logger.error("bird JSON parse error for @%s: %s", username, exc)
            return []

    async def fetch_replies(self, tweet_id: str) -> list:
        proc = await asyncio.create_subprocess_exec(
            "bird", "replies", tweet_id, "--json",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.warning("bird replies %s failed (exit %d)", tweet_id, proc.returncode)
            return []
        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return []


# ── Scraper (format-agnostic) ───────────────────────────────────────────

class TwitterScraper(BaseScraper):
    """Fetch tweets via a pluggable :class:`TwitterClient`.

    Defaults to :class:`BirdTwitterClient`.  Swap by passing a different
    client at construction time — no other code changes needed.
    """

    def __init__(self, config: TwitterConfig, http_client=None,
                 client: Optional[TwitterClient] = None):
        super().__init__(config, http_client)
        self.config = config
        self._client = client or BirdTwitterClient()

    async def fetch(self, since: datetime) -> List[ContentItem]:
        if not self.config.enabled:
            return []

        users = [u.strip().lstrip("@") for u in self.config.users if u.strip()]
        if not users:
            logger.debug("No Twitter users configured, skipping.")
            return []

        items: List[ContentItem] = []
        for username in users:
            try:
                tweets = await self._client.fetch_user_tweets(username, self.config.fetch_limit)
                for tweet in tweets:
                    parsed = self._parse_tweet(tweet, since)
                    if parsed:
                        items.append(parsed)
                logger.info("Fetched %d tweets from @%s", len(tweets), username)
            except Exception as exc:
                logger.error("Failed to fetch tweets for @%s: %s", username, exc)

        logger.info("Fetched %d tweets total.", len(items))
        return items

    async def fetch_replies_for_item(self, item: ContentItem) -> List[str]:
        """Fetch reply texts for one tweet (discussion expansion)."""
        if not self.config.fetch_reply_text:
            return []

        tweet_id = str(item.metadata.get("tweet_id", ""))
        if not tweet_id:
            return []

        max_replies = max(self.config.max_replies_per_tweet, 0)
        if max_replies == 0:
            return []

        rows = await self._client.fetch_replies(tweet_id)
        return self._extract_reply_lines(item, rows, max_replies, self.config.reply_min_likes)

    # ── reply formatting ────────────────────────────────────────────────

    @staticmethod
    def _extract_reply_lines(item: ContentItem, rows: list, max_replies: int,
                              min_likes: int = 0) -> List[str]:
        min_likes = max(min_likes, 0)
        tweet_id = str(item.metadata.get("tweet_id", ""))
        own_author = (item.author or "").lstrip("@")
        candidates: list = []

        for row in rows:
            if not isinstance(row, dict):
                continue

            row_id = str(row.get("id", ""))
            if tweet_id and row_id == tweet_id:
                continue

            author = row.get("author", {}) or {}
            handle = author.get("username", "unknown")
            if handle and own_author and handle.lower() == own_author.lower():
                continue

            text = (row.get("text") or "").strip()
            if not text:
                continue

            likes = int(row.get("likeCount", 0))
            replies = int(row.get("replyCount", 0))
            if likes < min_likes:
                continue

            score = likes * 2 + replies
            line = f"[@{handle} | ❤️ {likes} | 💬 {replies}] {text[:280]}"
            candidates.append((score, line))

        candidates.sort(key=lambda x: x[0], reverse=True)
        return [line for _, line in candidates[:max_replies]]

    @staticmethod
    def append_discussion_content(item: ContentItem, reply_lines: List[str]) -> bool:
        if not reply_lines:
            return False

        existing = item.content or ""
        marker = "--- Top Comments ---"
        block = "\n".join(reply_lines)

        if marker in existing:
            if block in existing:
                return False
            item.content = existing + "\n" + block
            return True

        item.content = (existing + f"\n\n{marker}\n" + block) if existing else (f"{marker}\n" + block)
        return True

    # ── tweet parsing (bird JSON schema) ────────────────────────────────

    def _parse_tweet(self, tweet: dict, since: datetime) -> Optional[ContentItem]:
        try:
            tweet_id = str(tweet.get("id", ""))
            if not tweet_id:
                return None

            created_at_str = tweet.get("createdAt", "")
            if not created_at_str:
                return None

            try:
                published_at = datetime.strptime(created_at_str, "%a %b %d %H:%M:%S %z %Y")
            except ValueError:
                from dateutil.parser import isoparse
                published_at = isoparse(created_at_str)

            if published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=timezone.utc)

            if published_at < since:
                return None

            author_data = tweet.get("author", {}) or {}
            screen_name = author_data.get("username", "unknown")
            author_name = author_data.get("name", screen_name)

            text = (tweet.get("text") or "").strip()
            if not text:
                return None
            text = unescape(text)

            url = f"https://twitter.com/{screen_name}/status/{tweet_id}"

            title_body = text[:50].replace("\n", " ").strip()
            if len(text) > 50:
                title_body += "..."

            return ContentItem(
                id=self._generate_id(SourceType.TWITTER.value, "tweet", tweet_id),
                source_type=SourceType.TWITTER,
                title=f"@{screen_name}: {title_body}",
                url=url,
                content=text,
                author=author_name,
                published_at=published_at,
                metadata={
                    "tweet_id": tweet_id,
                    "handle": screen_name,
                    "conversation_id": str(tweet.get("conversationId", tweet_id)),
                    "favorite_count": tweet.get("likeCount", 0),
                    "retweet_count": tweet.get("retweetCount", 0),
                    "reply_count": tweet.get("replyCount", 0),
                },
            )
        except Exception as exc:
            logger.debug("Failed to parse tweet %s: %s", tweet.get("id", "?"), exc)
            return None
