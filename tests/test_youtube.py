import asyncio
import json
from datetime import datetime, timezone

import httpx

import src.scrapers.youtube as youtube_module
from src.models import Config, SourceType, YouTubeChannelConfig, YouTubeConfig
from src.scrapers.youtube import YouTubeScraper


class FakeProcess:
    def __init__(self, stdout: str, stderr: str = "", returncode: int = 0):
        self._stdout = stdout.encode()
        self._stderr = stderr.encode()
        self.returncode = returncode

    async def communicate(self):
        return self._stdout, self._stderr


def run(coro):
    return asyncio.run(coro)


def make_scraper(config: YouTubeConfig) -> YouTubeScraper:
    return YouTubeScraper(config, httpx.AsyncClient())


def test_config_example_validates_youtube_defaults():
    payload = json.loads(open("data/config.example.json").read())

    config = Config.model_validate(payload)

    assert config.sources.youtube is not None
    assert config.sources.youtube.enabled is False
    assert config.sources.youtube.channels[0].name == "The Diary Of A CEO"
    assert str(config.sources.youtube.channels[0].url).rstrip("/") == (
        "https://www.youtube.com/@TheDiaryOfACEO"
    )


def test_disabled_youtube_config_returns_no_items(monkeypatch):
    calls = []

    async def fake_create_subprocess_exec(*args, **kwargs):
        calls.append(args)
        return FakeProcess("")

    monkeypatch.setattr(youtube_module.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    scraper = make_scraper(
        YouTubeConfig(
            enabled=False,
            channels=[
                YouTubeChannelConfig(
                    name="Disabled",
                    url="https://www.youtube.com/@disabled",
                )
            ],
        )
    )

    result = run(scraper.fetch(datetime(2026, 5, 1, tzinfo=timezone.utc)))

    assert result == []
    assert calls == []


def test_fetch_uses_full_metadata_and_parses_publication_dates(monkeypatch):
    calls = []
    rows = [
        {
            "id": "new-timestamp",
            "title": "Timestamp Video",
            "webpage_url": "https://www.youtube.com/watch?v=new-timestamp",
            "timestamp": 1777670400,
            "description": "from timestamp",
            "uploader": "The Diary Of A CEO",
            "channel": "The Diary Of A CEO",
            "channel_id": "UCGq-a57w-aPwyi3pW7XLiHw",
            "upload_date": "20260501",
            "duration": 120,
            "view_count": 456,
            "like_count": 78,
        },
        {
            "id": "old-upload-date",
            "title": "Old Video",
            "webpage_url": "https://www.youtube.com/watch?v=old-upload-date",
            "upload_date": "20260430",
        },
        {
            "id": "new-upload-date",
            "title": "Upload Date Video",
            "url": "https://www.youtube.com/watch?v=new-upload-date",
            "upload_date": "20260502",
        },
        {
            "id": "missing-date",
            "title": "No Date",
            "webpage_url": "https://www.youtube.com/watch?v=missing-date",
        },
    ]

    async def fake_create_subprocess_exec(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeProcess("\n".join(json.dumps(row) for row in rows))

    monkeypatch.setattr(youtube_module.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    scraper = make_scraper(
        YouTubeConfig(
            channels=[
                YouTubeChannelConfig(
                    name="The Diary Of A CEO",
                    url="https://www.youtube.com/@TheDiaryOfACEO",
                    fetch_limit=7,
                    category="interviews",
                )
            ]
        )
    )

    result = run(scraper.fetch(datetime(2026, 5, 1, tzinfo=timezone.utc)))

    assert [item.title for item in result] == ["Timestamp Video", "Upload Date Video"]
    assert all(item.source_type == SourceType.YOUTUBE for item in result)
    assert result[0].id == "youtube:video:new-timestamp"
    assert result[0].author == "The Diary Of A CEO"
    assert result[0].metadata["channel_name"] == "The Diary Of A CEO"
    assert result[0].metadata["channel_id"] == "UCGq-a57w-aPwyi3pW7XLiHw"
    assert result[0].metadata["upload_date"] == "20260501"
    assert result[0].metadata["duration"] == 120
    assert result[0].metadata["view_count"] == 456
    assert result[0].metadata["like_count"] == 78
    assert result[0].metadata["category"] == "interviews"
    args, kwargs = calls[0]
    assert args[:3] == (youtube_module.sys.executable, "-m", "yt_dlp")
    assert "--dump-json" in args
    assert "--flat-playlist" not in args
    assert "--no-download" in args
    assert "--playlist-end" in args
    assert "7" in args
    assert args[-1] == "https://www.youtube.com/@TheDiaryOfACEO/videos"
    assert kwargs["stdout"] == youtube_module.asyncio.subprocess.PIPE
    assert kwargs["stderr"] == youtube_module.asyncio.subprocess.PIPE


def test_fetch_tolerates_invalid_json_lines_and_subprocess_failures(monkeypatch):
    async def fake_invalid_json_process(*args, **kwargs):
        return FakeProcess(
            "\n".join(
                [
                    "{not json",
                    json.dumps(
                        {
                            "id": "valid",
                            "title": "Valid Video",
                            "webpage_url": "https://www.youtube.com/watch?v=valid",
                            "upload_date": "20260502",
                        }
                    ),
                ]
            )
        )

    monkeypatch.setattr(youtube_module.asyncio, "create_subprocess_exec", fake_invalid_json_process)
    scraper = make_scraper(
        YouTubeConfig(
            channels=[
                YouTubeChannelConfig(
                    name="Valid Channel",
                    url="https://www.youtube.com/@valid",
                )
            ]
        )
    )

    result = run(scraper.fetch(datetime(2026, 5, 1, tzinfo=timezone.utc)))

    assert [item.title for item in result] == ["Valid Video"]

    async def fake_failed_process(*args, **kwargs):
        return FakeProcess("", "No module named yt_dlp", returncode=1)

    monkeypatch.setattr(youtube_module.asyncio, "create_subprocess_exec", fake_failed_process)

    assert run(scraper.fetch(datetime(2026, 5, 1, tzinfo=timezone.utc))) == []


def test_fetch_returns_empty_on_timeout(monkeypatch):
    async def fake_create_subprocess_exec(*args, **kwargs):
        return FakeProcess("")

    async def fake_wait_for(coro, timeout):
        await coro
        raise TimeoutError

    monkeypatch.setattr(youtube_module.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr(youtube_module.asyncio, "wait_for", fake_wait_for)
    scraper = make_scraper(
        YouTubeConfig(
            channels=[
                YouTubeChannelConfig(
                    name="Slow",
                    url="https://www.youtube.com/@slow",
                )
            ],
            timeout_seconds=3,
        )
    )

    assert run(scraper.fetch(datetime(2026, 5, 1, tzinfo=timezone.utc))) == []
