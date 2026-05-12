"""Hotspot attribution collection and storage."""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class HotspotSource:
    """A public or authorized hotspot data endpoint."""

    name: str
    url: str


@dataclass(frozen=True)
class HotspotRecord:
    """Normalized hotspot attribution record."""

    source: str
    source_url: str
    topic: str
    reason: str
    symbol: str = ""
    symbol_name: str = ""
    heat: float | None = None
    observed_at: str = ""
    raw_json: str = ""


class HotspotFetcher:
    """Rate-limited HTTP fetcher for authorized data sources."""

    def __init__(self, min_interval: float = 1.0, timeout: float = 10.0) -> None:
        self.min_interval = min_interval
        self.timeout = timeout
        self._last_request_at = 0.0

    def fetch_json(self, source: HotspotSource) -> Any:
        """Fetch one JSON source with a bounded timeout."""
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)

        request = Request(
            source.url,
            headers={
                "Accept": "application/json",
                "User-Agent": "ZiporaHotspotCollector/0.1",
            },
        )
        with urlopen(request, timeout=self.timeout) as response:
            body = response.read().decode("utf-8")
        self._last_request_at = time.monotonic()
        return json.loads(body)


class HotspotStore:
    """SQLite-backed hotspot attribution storage."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path.home() / ".zipora" / "hotspots.sqlite3"

    def save_records(self, records: list[HotspotRecord]) -> int:
        """Insert records and return the number of new rows."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            self._ensure_schema(connection)
            before = connection.total_changes
            connection.executemany(
                """
                INSERT OR IGNORE INTO hotspot_records (
                    content_hash, source, source_url, topic, reason, symbol,
                    symbol_name, heat, observed_at, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [self._row(record) for record in records],
            )
            return connection.total_changes - before

    def list_records(self, limit: int = 50) -> list[HotspotRecord]:
        """Return records in newest-first order."""
        if not self.path.exists():
            return []
        with sqlite3.connect(self.path) as connection:
            self._ensure_schema(connection)
            rows = connection.execute(
                """
                SELECT source, source_url, topic, reason, symbol, symbol_name,
                       heat, observed_at, raw_json
                FROM hotspot_records
                ORDER BY observed_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [HotspotRecord(*row) for row in rows]

    def export_csv(self, destination: Path, limit: int = 1000) -> int:
        """Export records to CSV and return row count."""
        records = self.list_records(limit=limit)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=[
                    "source",
                    "source_url",
                    "topic",
                    "reason",
                    "symbol",
                    "symbol_name",
                    "heat",
                    "observed_at",
                    "raw_json",
                ],
            )
            writer.writeheader()
            for record in records:
                writer.writerow(asdict(record))
        return len(records)

    def _ensure_schema(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS hotspot_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_hash TEXT NOT NULL UNIQUE,
                source TEXT NOT NULL,
                source_url TEXT NOT NULL,
                topic TEXT NOT NULL,
                reason TEXT NOT NULL,
                symbol TEXT NOT NULL,
                symbol_name TEXT NOT NULL,
                heat REAL,
                observed_at TEXT NOT NULL,
                raw_json TEXT NOT NULL
            )
            """
        )

    def _row(self, record: HotspotRecord) -> tuple[Any, ...]:
        return (
            _content_hash(record),
            record.source,
            record.source_url,
            record.topic,
            record.reason,
            record.symbol,
            record.symbol_name,
            record.heat,
            record.observed_at,
            record.raw_json,
        )


class HotspotCollector:
    """Collect hotspot attribution records from configured sources."""

    def __init__(self, fetcher: HotspotFetcher | None = None) -> None:
        self.fetcher = fetcher or HotspotFetcher()

    def collect(self, sources: list[HotspotSource]) -> list[HotspotRecord]:
        """Fetch and normalize all configured sources."""
        records: list[HotspotRecord] = []
        observed_at = _utc_now()
        for source in sources:
            payload = self.fetcher.fetch_json(source)
            records.extend(parse_hotspot_payload(payload, source, observed_at=observed_at))
        return records


def load_sources(path: Path) -> list[HotspotSource]:
    """Load source definitions from a JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("source config must be a JSON array")
    sources = []
    for item in data:
        if not isinstance(item, dict) or not item.get("name") or not item.get("url"):
            raise ValueError("each source must include name and url")
        sources.append(HotspotSource(name=str(item["name"]), url=str(item["url"])))
    return sources


def parse_hotspot_payload(
    payload: Any,
    source: HotspotSource,
    observed_at: str | None = None,
) -> list[HotspotRecord]:
    """Normalize hotspot attribution records from a nested JSON payload."""
    records: list[HotspotRecord] = []
    for item in _walk_dicts(payload):
        topic = _first_text(
            item,
            ("topic", "hotspot", "concept", "theme", "plateName", "boardName", "name"),
        )
        reason = _first_text(
            item,
            ("reason", "cause", "analysis", "attribution", "description", "desc", "logic"),
        )
        symbol = _first_text(item, ("symbol", "code", "stockCode", "securityCode"))
        symbol_name = _first_text(item, ("symbolName", "stockName", "securityName", "shortName"))
        if not topic and symbol_name:
            topic = symbol_name
        if not reason:
            continue
        records.append(
            HotspotRecord(
                source=source.name,
                source_url=source.url,
                topic=topic or "unknown",
                reason=reason,
                symbol=symbol,
                symbol_name=symbol_name,
                heat=_first_float(item, ("heat", "score", "rank", "popularity")),
                observed_at=observed_at or _utc_now(),
                raw_json=json.dumps(item, ensure_ascii=False, sort_keys=True),
            )
        )
    return records


def _walk_dicts(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        found = [value]
        for child in value.values():
            found.extend(_walk_dicts(child))
        return found
    if isinstance(value, list):
        found: list[dict[str, Any]] = []
        for child in value:
            found.extend(_walk_dicts(child))
        return found
    return []


def _first_text(item: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = item.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _first_float(item: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = item.get(key)
        if value in (None, ""):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _content_hash(record: HotspotRecord) -> str:
    normalized = "|".join(
        (
            record.source,
            record.source_url,
            record.topic,
            record.reason,
            record.symbol,
            record.symbol_name,
            record.observed_at,
        )
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
