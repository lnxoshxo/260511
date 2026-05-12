"""Persistent application settings."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from zipora.core.models import ArchiveFormat


@dataclass
class AppSettings:
    """User-configurable application settings."""

    default_format: str = ArchiveFormat.ZIP.value
    default_level: int = 6
    default_extract_dir: str = ""
    theme: str = "light"
    language: str = "zh_CN"
    font_size: int = 10
    cpu_cores: int = 0
    memory_limit_mb: int = 0
    temp_dir: str = ""
    clear_password_seconds: int = 300


class SettingsStore:
    """JSON-backed settings storage."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path.home() / ".zipora" / "settings.json"

    def load(self) -> AppSettings:
        """Load settings from disk."""
        if not self.path.exists():
            return AppSettings()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return AppSettings(**{**asdict(AppSettings()), **data})

    def save(self, settings: AppSettings) -> None:
        """Persist settings to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
