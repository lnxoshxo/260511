"""Shared helpers for archive operations."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterable
from pathlib import Path

from zipora.core.exceptions import UnsafeArchiveError
from zipora.core.models import ArchiveFormat, OverwritePolicy

FORMAT_SUFFIXES: dict[ArchiveFormat, tuple[str, ...]] = {
    ArchiveFormat.ZIP: (".zip",),
    ArchiveFormat.SEVEN_Z: (".7z",),
    ArchiveFormat.TAR: (".tar",),
    ArchiveFormat.TAR_GZ: (".tar.gz", ".tgz"),
    ArchiveFormat.TAR_BZ2: (".tar.bz2", ".tbz2"),
    ArchiveFormat.TAR_XZ: (".tar.xz", ".txz"),
    ArchiveFormat.LZ4: (".lz4",),
    ArchiveFormat.ZSTD: (".zst", ".zstd"),
    ArchiveFormat.RAR: (".rar",),
}


def detect_format(path: Path) -> ArchiveFormat:
    """Detect the archive format from a path suffix."""
    lower_name = path.name.lower()
    for archive_format, suffixes in FORMAT_SUFFIXES.items():
        if any(lower_name.endswith(suffix) for suffix in suffixes):
            return archive_format
    raise ValueError(f"Unsupported archive extension: {path.suffix}")


def iter_input_files(paths: Iterable[Path]) -> list[Path]:
    """Return existing input paths in a stable order."""
    result = [path.expanduser().resolve() for path in paths]
    missing = [str(path) for path in result if not path.exists()]
    if missing:
        raise FileNotFoundError(", ".join(missing))
    return sorted(result, key=lambda item: str(item).lower())


def archive_name_for(path: Path, base_dir: Path) -> str:
    """Build a portable archive member name."""
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(path.name)
    return relative.as_posix()


def safe_destination(root: Path, member_name: str) -> Path:
    """Resolve an extraction destination and block path traversal."""
    destination = (root / member_name).resolve()
    root_resolved = root.resolve()
    if os.path.commonpath([root_resolved, destination]) != str(root_resolved):
        raise UnsafeArchiveError(f"Unsafe archive path: {member_name}")
    return destination


def resolve_conflict(path: Path, policy: OverwritePolicy) -> Path | None:
    """Return the destination path after applying an overwrite strategy."""
    if not path.exists() or policy == OverwritePolicy.OVERWRITE:
        return path
    if policy == OverwritePolicy.SKIP:
        return None
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    index = 1
    while True:
        candidate = parent / f"{stem} ({index}){suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Calculate a SHA-256 digest without loading the whole file into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compression_level(level: int, minimum: int = 0, maximum: int = 9) -> int:
    """Clamp a user compression level into a library-supported range."""
    return max(minimum, min(maximum, level))
