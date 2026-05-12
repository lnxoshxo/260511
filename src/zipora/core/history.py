"""Recent task history persistence."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class HistoryItem:
    """A completed archive operation."""

    action: str
    source: str
    destination: str
    created_at: str


class HistoryStore:
    """JSON-backed recent operation history."""

    def __init__(self, path: Path | None = None, limit: int = 100) -> None:
        self.path = path or Path.home() / ".zipora" / "history.json"
        self.limit = limit

    def add(self, action: str, source: Path, destination: Path) -> None:
        """Append a recent operation."""
        items = self.list_items()
        items.insert(
            0,
            HistoryItem(
                action=action,
                source=str(source),
                destination=str(destination),
                created_at=datetime.now(timezone.utc).isoformat(),
            ),
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(item) for item in items[: self.limit]]
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def list_items(self) -> list[HistoryItem]:
        """Return recent operations."""
        if not self.path.exists():
            return []
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return [HistoryItem(**item) for item in data]
