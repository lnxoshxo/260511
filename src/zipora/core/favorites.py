"""Favorite archive and folder storage."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class FavoriteItem:
    """A user favorite path."""

    name: str
    path: str


class FavoritesStore:
    """JSON-backed favorites storage."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path.home() / ".zipora" / "favorites.json"

    def add(self, name: str, path: Path) -> None:
        """Add or update a favorite path."""
        items = [item for item in self.list_items() if item.path != str(path)]
        items.insert(0, FavoriteItem(name=name, path=str(path)))
        self._save(items)

    def remove(self, path: Path) -> None:
        """Remove a favorite path."""
        self._save([item for item in self.list_items() if item.path != str(path)])

    def list_items(self) -> list[FavoriteItem]:
        """Return favorite paths."""
        if not self.path.exists():
            return []
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return [FavoriteItem(**item) for item in data]

    def _save(self, items: list[FavoriteItem]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps([asdict(item) for item in items], indent=2),
            encoding="utf-8",
        )
