"""Tests for the AI result cache contract."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from src.ai.cache import AIResultCache, build_item_cache_key
from src.models import AIConfig, AIProvider, Config, ContentItem, SourceType


def _make_config(**overrides) -> AIConfig:
    values = {
        "provider": AIProvider.OPENAI,
        "model": "gpt-4o-mini",
        "api_key_env": "OPENAI_API_KEY",
        "temperature": 0.2,
        "max_tokens": 2048,
    }
    values.update(overrides)
    return AIConfig(**values)


def _make_item(**overrides) -> ContentItem:
    values = {
        "id": "rss:example:123",
        "source_type": SourceType.RSS,
        "title": "Cacheable story",
        "url": "https://example.com/story",
        "content": "A stable article body.",
        "published_at": datetime(2026, 5, 8, tzinfo=timezone.utc),
        "fetched_at": datetime(2026, 5, 8, tzinfo=timezone.utc),
    }
    values.update(overrides)
    return ContentItem(**values)


def _cache_key(config: AIConfig | None = None, item: ContentItem | None = None, **overrides) -> str:
    values = {
        "stage": "analysis",
        "prompt_version": "analysis-v1",
        "config": config or _make_config(),
        "item": item or _make_item(),
        "prompt_content": "Analyze this article.",
        "schema_version": 1,
    }
    values.update(overrides)
    return build_item_cache_key(**values)


def test_cache_round_trip_returns_json_payload(tmp_path):
    cache = AIResultCache(tmp_path / "ai-cache.sqlite", ttl_hours=720, schema_version=1)
    key = _cache_key()
    payload = {"score": 8.5, "reason": "useful", "summary": "short", "tags": ["ai"]}

    assert cache.get(key) is None

    cache.set(key, payload)

    assert cache.get(key) == payload


def test_cache_ttl_expires_stale_rows(tmp_path):
    cache = AIResultCache(tmp_path / "ai-cache.sqlite", ttl_hours=1, schema_version=1)
    key = _cache_key()

    cache.set(key, {"score": 7})
    with sqlite3.connect(tmp_path / "ai-cache.sqlite") as db:
        db.execute("UPDATE ai_cache_entries SET created_at = ?", ("2026-05-01T00:00:00+00:00",))

    assert cache.get(key, now=datetime(2026, 5, 8, tzinfo=timezone.utc)) is None


def test_cache_refresh_replaces_stale_payload(tmp_path):
    cache = AIResultCache(tmp_path / "ai-cache.sqlite", ttl_hours=1, schema_version=1)
    key = _cache_key()

    cache.set(key, {"score": 4})
    with sqlite3.connect(tmp_path / "ai-cache.sqlite") as db:
        db.execute("UPDATE ai_cache_entries SET created_at = ?", ("2026-05-01T00:00:00+00:00",))

    cache.set(key, {"score": 9})

    assert cache.get(key, now=datetime(2026, 5, 8, tzinfo=timezone.utc)) == {"score": 9}


def test_cache_key_invalidates_on_item_prompt_config_and_schema_changes():
    base_key = _cache_key()

    assert _cache_key(item=_make_item(id="rss:example:456")) != base_key
    assert _cache_key(prompt_content="Different prompt") != base_key
    assert _cache_key(config=_make_config(model="gpt-5")) != base_key
    assert _cache_key(schema_version=2) != base_key


def test_ai_config_cache_defaults_and_example_config_parse():
    config = _make_config()

    assert config.cache_enabled is True
    assert config.cache_dir == "data/cache"
    assert config.cache_ttl_hours == 720
    assert config.cache_schema_version == 1

    with open("data/config.example.json", encoding="utf-8") as fh:
        example = Config.model_validate(json.load(fh))

    assert example.ai.cache_enabled is True
    assert example.ai.cache_dir == "data/cache"
    assert example.ai.cache_ttl_hours == 720
    assert example.ai.cache_schema_version == 1
