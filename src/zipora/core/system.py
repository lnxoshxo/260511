"""System integration helpers."""

from __future__ import annotations

import os
from pathlib import Path

import psutil
from send2trash import send2trash


def system_summary() -> dict[str, str | int | float]:
    """Return a small system resource snapshot."""
    return {
        "cpu_count": os.cpu_count() or 1,
        "cpu_percent": psutil.cpu_percent(interval=0.0),
        "memory_percent": psutil.virtual_memory().percent,
    }


def safe_trash(path: Path) -> None:
    """Move a path to the OS trash."""
    send2trash(str(path))
