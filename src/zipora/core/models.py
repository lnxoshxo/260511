"""Core data models used by archive operations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class ArchiveFormat(str, Enum):
    """Supported archive formats."""

    ZIP = "zip"
    SEVEN_Z = "7z"
    TAR = "tar"
    TAR_GZ = "tar.gz"
    TAR_BZ2 = "tar.bz2"
    TAR_XZ = "tar.xz"
    LZ4 = "lz4"
    ZSTD = "zst"
    RAR = "rar"


class OverwritePolicy(str, Enum):
    """File conflict handling strategy during extraction."""

    OVERWRITE = "overwrite"
    SKIP = "skip"
    RENAME = "rename"
    ASK = "ask"


@dataclass(frozen=True)
class CompressionOptions:
    """Options for creating an archive."""

    archive_format: ArchiveFormat
    level: int = 6
    password: str | None = None
    comment: str | None = None
    volume_size: int | None = None
    preserve_metadata: bool = True


@dataclass(frozen=True)
class ExtractionOptions:
    """Options for extracting an archive."""

    password: str | None = None
    overwrite_policy: OverwritePolicy = OverwritePolicy.RENAME
    selected_members: tuple[str, ...] | None = None
    create_root_folder: bool = False


@dataclass(frozen=True)
class ArchiveEntry:
    """A file or directory entry inside an archive."""

    name: str
    size: int
    compressed_size: int | None = None
    is_dir: bool = False
    modified_at: float | None = None


@dataclass(frozen=True)
class ArchiveInfo:
    """Computed archive information."""

    path: Path
    archive_format: ArchiveFormat
    size: int
    entries: int
    is_encrypted: bool = False
    sha256: str | None = None


@dataclass(frozen=True)
class ProgressEvent:
    """Progress update emitted by long-running operations."""

    percent: int
    message: str
    current_file: str | None = None
