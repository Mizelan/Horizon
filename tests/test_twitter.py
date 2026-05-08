"""Tests for TwitterScraper with the pluggable TwitterClient interface."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from src.models import TwitterConfig, ContentItem, SourceType
from src.scrapers.twitter import TwitterScraper, TwitterClient


class FakeTwitterClient(TwitterClient):
    """Returns canned data — no subprocess or HTTP needed."""

    def __init__(self, tweets: Optional[list] = None, replies: Optional[list] = None):
        self.tweets = tweets or []
        self.replies = replies or []
        self.fetch_user_tweets_calls: list = []
        self.fetch_replies_calls: list = []

    async def fetch_user_tweets(self, username: str, limit: int) -> list:
        self.fetch_user_tweets_calls.append((username, limit))
        return self.tweets

    async def fetch_replies(self, tweet_id: str) -> list:
        self.fetch_replies_calls.append(tweet_id)
        return self.replies


# ── helpers ─────────────────────────────────────────────────────────────

def _make_config(**kwargs) -> TwitterConfig:
    defaults = dict(enabled=True, users=["karpathy"], fetch_limit=3)
    defaults.update(kwargs)
    return TwitterConfig(**defaults)


def _tweet(
    tweet_id: str = "123456",
    screen_name: str = "karpathy",
    text: str = "Hello world",
    conversation_id: str = None,
    **extra,
) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "id": tweet_id,
        "createdAt": now.strftime("%a %b %d %H:%M:%S +0000 %Y"),
        "conversationId": conversation_id or tweet_id,
        "text": text,
        "author": {"username": screen_name, "name": screen_name.capitalize()},
        "likeCount": 10,
        "retweetCount": 2,
        "replyCount": 1,
        **extra,
    }


def _reply_row(
    tweet_id: str = "999",
    handle: str = "someone",
    text: str = "Great point!",
    likes: int = 5,
) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "id": tweet_id,
        "text": text,
        "likeCount": likes,
        "replyCount": 0,
        "createdAt": now.strftime("%a %b %d %H:%M:%S +0000 %Y"),
        "author": {"username": handle, "name": handle},
    }


# ── fetch tests ─────────────────────────────────────────────────────────

def test_disabled_returns_empty():
    client = FakeTwitterClient(tweets=[_tweet("1")])
    scraper = TwitterScraper(_make_config(enabled=False), client=client)
    result = asyncio.run(scraper.fetch(datetime.now(timezone.utc)))
    assert result == []
    assert client.fetch_user_tweets_calls == []


def test_no_users_returns_empty():
    client = FakeTwitterClient(tweets=[_tweet("1")])
    scraper = TwitterScraper(_make_config(users=[]), client=client)
    result = asyncio.run(scraper.fetch(datetime.now(timezone.utc)))
    assert result == []


def test_successful_fetch_returns_items():
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    tweets = [_tweet("1"), _tweet("2", text="Another tweet")]
    client = FakeTwitterClient(tweets=tweets)
    scraper = TwitterScraper(_make_config(), client=client)
    result = asyncio.run(scraper.fetch(since))

    assert len(result) == 2
    assert result[0].source_type.value == "twitter"
    assert result[0].metadata["favorite_count"] == 10
    assert client.fetch_user_tweets_calls == [("karpathy", 3)]


def test_metadata_keys_aligned_for_analyzer():
    """Analyzer reads favorite_count/retweet_count/reply_count — verify set."""
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    tweets = [_tweet("42", likeCount=99, retweetCount=7, replyCount=3)]
    client = FakeTwitterClient(tweets=tweets)
    scraper = TwitterScraper(_make_config(), client=client)
    result = asyncio.run(scraper.fetch(since))

    assert len(result) == 1
    meta = result[0].metadata
    assert meta["favorite_count"] == 99
    assert meta["retweet_count"] == 7
    assert meta["reply_count"] == 3
    assert meta["tweet_id"] == "42"
    assert meta["conversation_id"] == "42"


def test_filters_old_tweets():
    since = datetime.now(timezone.utc)
    old = (since - timedelta(hours=2)).strftime("%a %b %d %H:%M:%S +0000 %Y")
    client = FakeTwitterClient(tweets=[_tweet("1", createdAt=old)])
    scraper = TwitterScraper(_make_config(), client=client)
    result = asyncio.run(scraper.fetch(since))
    assert result == []


def test_empty_results_returns_empty():
    client = FakeTwitterClient(tweets=[])
    scraper = TwitterScraper(_make_config(), client=client)
    result = asyncio.run(scraper.fetch(datetime.now(timezone.utc) - timedelta(hours=1)))
    assert result == []


def test_handles_fetch_exception_gracefully():
    class BrokenClient(TwitterClient):
        async def fetch_user_tweets(self, username, limit):
            raise RuntimeError("broken")
        async def fetch_replies(self, tweet_id):
            return []

    client = BrokenClient()
    scraper = TwitterScraper(_make_config(), client=client)
    result = asyncio.run(scraper.fetch(datetime.now(timezone.utc) - timedelta(hours=1)))
    assert result == []


# ── reply / discussion-expansion tests ──────────────────────────────────

def test_fetch_replies_disabled_by_default():
    cfg = TwitterConfig()
    assert cfg.fetch_reply_text is False


def test_fetch_replies_appends_top_comments():
    replies = [
        _reply_row("r1", "alice", "Interesting take!", likes=20),
        _reply_row("r2", "bob", "I disagree because...", likes=5),
        _reply_row("r3", "carol", "Great point!", likes=15),
        _reply_row("r4", "dave", "Low quality reply", likes=0),
    ]
    client = FakeTwitterClient(replies=replies)
    cfg = _make_config(fetch_reply_text=True, max_replies_per_tweet=3, reply_min_likes=1)
    scraper = TwitterScraper(cfg, client=client)

    item = ContentItem(
        id="twitter:tweet:42",
        source_type=SourceType.TWITTER,
        title="@karpathy: test tweet",
        url="https://twitter.com/karpathy/status/42",
        content="test tweet body",
        author="Andrej Karpathy",
        published_at=datetime.now(timezone.utc),
        metadata={"tweet_id": "42", "conversation_id": "42"},
    )

    reply_lines = asyncio.run(scraper.fetch_replies_for_item(item))

    assert len(reply_lines) == 3
    assert "alice" in reply_lines[0]
    assert "Interesting take!" in reply_lines[0]
    assert not any("dave" in l for l in reply_lines)


def test_append_discussion_content_adds_marker():
    item = ContentItem(
        id="twitter:tweet:1", source_type=SourceType.TWITTER, title="test",
        url="https://twitter.com/x/status/1", content="original text",
        author="x", published_at=datetime.now(timezone.utc), metadata={},
    )
    changed = TwitterScraper.append_discussion_content(
        item, ["[@alice | ❤️ 5 | 💬 1] reply text"]
    )
    assert changed is True
    assert "--- Top Comments ---" in item.content
    assert "alice" in item.content


def test_append_discussion_content_empty_lines_no_change():
    item = ContentItem(
        id="twitter:tweet:2", source_type=SourceType.TWITTER, title="test",
        url="https://twitter.com/x/status/2", content="original",
        author="x", published_at=datetime.now(timezone.utc), metadata={},
    )
    changed = TwitterScraper.append_discussion_content(item, [])
    assert changed is False
    assert item.content == "original"


def test_fetch_replies_no_tweet_id_returns_empty():
    client = FakeTwitterClient()
    cfg = _make_config(fetch_reply_text=True)
    scraper = TwitterScraper(cfg, client=client)
    item = ContentItem(
        id="twitter:tweet:x", source_type=SourceType.TWITTER, title="test",
        url="https://twitter.com/x/status/x", content="body",
        author="x", published_at=datetime.now(timezone.utc),
        metadata={},  # no tweet_id
    )
    result = asyncio.run(scraper.fetch_replies_for_item(item))
    assert result == []
