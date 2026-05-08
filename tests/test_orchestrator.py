import asyncio
from datetime import datetime, timezone

from src.models import (
    AIConfig,
    Config,
    ContentItem,
    FilteringConfig,
    SourceType,
    SourcesConfig,
    YouTubeChannelConfig,
    YouTubeConfig,
)
from src.orchestrator import HorizonOrchestrator
from src.storage.manager import StorageManager


def _item(item_id: str, url: str) -> ContentItem:
    return ContentItem(
        id=item_id,
        source_type=SourceType.RSS,
        title=item_id,
        url=url,
        published_at=datetime(2026, 5, 8, tzinfo=timezone.utc),
        metadata={"feed_name": "GeekNews"},
    )


def _orchestrator(tmp_path):
    config = Config(
        ai=AIConfig(provider="llm_runner", model="gpt-5.5"),
        sources=SourcesConfig(),
        filtering=FilteringConfig(),
    )
    return HorizonOrchestrator(config, StorageManager(str(tmp_path)))


def test_cross_source_dedup_keeps_query_string_identities(tmp_path):
    orchestrator = _orchestrator(tmp_path)
    first = _item("rss:geeknews:29288", "https://news.hada.io/topic?id=29288")
    second = _item("rss:geeknews:29289", "https://news.hada.io/topic?id=29289")

    merged = orchestrator.merge_cross_source_duplicates([first, second])

    assert len(merged) == 2


def test_sub_source_label_prefers_youtube_channel_name(tmp_path):
    orchestrator = _orchestrator(tmp_path)
    item = ContentItem(
        id="youtube:video:abc123",
        source_type=SourceType.YOUTUBE,
        title="A video",
        url="https://www.youtube.com/watch?v=abc123",
        published_at=datetime(2026, 5, 8, tzinfo=timezone.utc),
        author="Uploader Name",
        metadata={"channel_name": "The Diary Of A CEO"},
    )

    assert orchestrator._sub_source_label(item) == "The Diary Of A CEO"


def test_fetch_all_sources_wires_configured_youtube_channels(tmp_path, monkeypatch):
    config = Config(
        ai=AIConfig(provider="llm_runner", model="gpt-5.5"),
        sources=SourcesConfig(
            github=[],
            rss=[],
            youtube=YouTubeConfig(
                enabled=True,
                channels=[
                    YouTubeChannelConfig(
                        name="The Diary Of A CEO",
                        url="https://www.youtube.com/@TheDiaryOfACEO",
                    )
                ],
            ),
        ),
        filtering=FilteringConfig(),
    )
    config.sources.hackernews.enabled = False
    config.sources.reddit.enabled = False
    config.sources.telegram.enabled = False
    orchestrator = HorizonOrchestrator(config, StorageManager(str(tmp_path)))
    fetched = [
        ContentItem(
            id="youtube:video:abc123",
            source_type=SourceType.YOUTUBE,
            title="A video",
            url="https://www.youtube.com/watch?v=abc123",
            published_at=datetime(2026, 5, 8, tzinfo=timezone.utc),
            metadata={"channel_name": "The Diary Of A CEO"},
        )
    ]
    calls = []

    class FakeYouTubeScraper:
        def __init__(self, youtube_config, client):
            calls.append((youtube_config, client))

        async def fetch(self, since):
            return fetched

    monkeypatch.setattr("src.orchestrator.YouTubeScraper", FakeYouTubeScraper)

    result = asyncio.run(orchestrator.fetch_all_sources(datetime(2026, 5, 7, tzinfo=timezone.utc)))

    assert result == fetched
    assert calls[0][0].channels[0].name == "The Diary Of A CEO"
