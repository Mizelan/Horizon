"""SQLite-backed cache primitives for AI stage results."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..models import AIConfig, ContentItem


class AIResultCache:
    """Persist JSON AI results keyed by deterministic stage inputs."""

    def __init__(self, db_path: str | Path, *, ttl_hours: int, schema_version: int):
        self.db_path = Path(db_path)
        self.ttl_hours = ttl_hours
        self.schema_version = schema_version
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def get(self, cache_key: str, *, now: datetime | None = None) -> dict[str, Any] | None:
        now = now or datetime.now(timezone.utc)
        with sqlite3.connect(self.db_path) as db:
            row = db.execute(
                """
                SELECT payload, created_at
                FROM ai_cache_entries
                WHERE cache_key = ? AND schema_version = ?
                """,
                (cache_key, self.schema_version),
            ).fetchone()

        if row is None:
            return None

        payload_json, created_at_text = row
        created_at = datetime.fromisoformat(created_at_text)
        if now - created_at > self._ttl_delta:
            return None
        return json.loads(payload_json)

    def set(self, cache_key: str, payload: dict[str, Any], *, now: datetime | None = None) -> None:
        now = now or datetime.now(timezone.utc)
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                """
                INSERT INTO ai_cache_entries (cache_key, schema_version, payload, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    schema_version = excluded.schema_version,
                    payload = excluded.payload,
                    created_at = excluded.created_at
                """,
                (cache_key, self.schema_version, payload_json, now.isoformat()),
            )

    @property
    def _ttl_delta(self):
        from datetime import timedelta

        return timedelta(hours=self.ttl_hours)

    def _ensure_schema(self) -> None:
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_cache_entries (
                    cache_key TEXT PRIMARY KEY,
                    schema_version INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )


def build_item_cache_key(
    *,
    stage: str,
    prompt_version: str,
    config: AIConfig,
    item: ContentItem,
    prompt_content: str,
    schema_version: int,
    extra: dict[str, Any] | None = None,
) -> str:
    """Build a deterministic key from provider, item, prompt, and schema inputs."""

    key_material = {
        "stage": stage,
        "prompt_version": prompt_version,
        "schema_version": schema_version,
        "provider": config.provider.value,
        "model": config.model,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "item": {
            "id": item.id,
            "source_type": item.source_type.value,
            "url": str(item.url),
            "title": item.title,
            "content": item.content,
            "published_at": item.published_at.isoformat(),
        },
        "prompt_sha256": hashlib.sha256(prompt_content.encode("utf-8")).hexdigest(),
        "extra": extra or {},
    }
    encoded = json.dumps(key_material, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
