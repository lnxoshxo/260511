"""Archive format implementations and high-level operations."""

from __future__ import annotations

import io
import os
import shutil
import tarfile
import tempfile
import zipfile
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from pathlib import Path

from zipora.core.exceptions import MissingOptionalDependencyError, UnsupportedFormatError
from zipora.core.models import (
    ArchiveEntry,
    ArchiveFormat,
    ArchiveInfo,
    CompressionOptions,
    ExtractionOptions,
    ProgressEvent,
)
from zipora.core.utils import (
    archive_name_for,
    compression_level,
    detect_format,
    iter_input_files,
    resolve_conflict,
    safe_destination,
    sha256_file,
)

ProgressCallback = Callable[[ProgressEvent], None]


class ArchiveBackend(ABC):
    """Interface implemented by archive format backends."""

    archive_format: ArchiveFormat

    can_write: bool = True

    supports_password_write: bool = False


    @abstractmethod
    def create(
        self,
        sources: Iterable[Path],
        destination: Path,
        options: CompressionOptions,
        progress: ProgressCallback | None = None,
    ) -> None:
        """Create an archive."""

    @abstractmethod
    def extract(
        self,
        archive_path: Path,
        destination: Path,
        options: ExtractionOptions,
        progress: ProgressCallback | None = None,
    ) -> None:
        """Extract an archive."""

    @abstractmethod
    def list_entries(self, archive_path: Path, password: str | None = None) -> list[ArchiveEntry]:
        """List archive entries."""


class ZipBackend(ArchiveBackend):
    """ZIP backend using Python's standard library."""

    archive_format = ArchiveFormat.ZIP


    def create(
        self,
        sources: Iterable[Path],
        destination: Path,
        options: CompressionOptions,
        progress: ProgressCallback | None = None,
    ) -> None:
        paths = iter_input_files(sources)
        base_dir = _common_base(paths)
        compression = zipfile.ZIP_DEFLATED if options.level > 0 else zipfile.ZIP_STORED
        compresslevel = (
            compression_level(options.level) if compression == zipfile.ZIP_DEFLATED else None
        )
        files = _expand_files(paths)
        with zipfile.ZipFile(
            destination,
            "w",
            compression=compression,
            compresslevel=compresslevel,
        ) as archive:
            if options.comment:
                archive.comment = options.comment.encode("utf-8")[:65535]
            for index, file_path in enumerate(files, start=1):
                arcname = archive_name_for(file_path, base_dir)
                archive.write(file_path, arcname)
                _emit(progress, index, len(files), arcname)

    def extract(
        self,
        archive_path: Path,
        destination: Path,
        options: ExtractionOptions,
        progress: ProgressCallback | None = None,
    ) -> None:
        root = _extraction_root(archive_path, destination, options.create_root_folder)
        password = options.password.encode("utf-8") if options.password else None
        with zipfile.ZipFile(archive_path) as archive:
            members = _selected_names(archive.namelist(), options.selected_members)
            for index, name in enumerate(members, start=1):
                info = archive.getinfo(name)
                target = resolve_conflict(safe_destination(root, name), options.overwrite_policy)
                if target is None:
                    _emit(progress, index, len(members), f"Skipped {name}")
                    continue
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(info, pwd=password) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)
                _emit(progress, index, len(members), name)

    def list_entries(self, archive_path: Path, password: str | None = None) -> list[ArchiveEntry]:
        with zipfile.ZipFile(archive_path) as archive:
            return [
                ArchiveEntry(
                    name=item.filename,
                    size=item.file_size,
                    compressed_size=item.compress_size,
                    is_dir=item.is_dir(),
                )
                for item in archive.infolist()
            ]


class TarBackend(ArchiveBackend):
    """TAR backend supporting plain and compressed tar archives."""

    def __init__(self, archive_format: ArchiveFormat) -> None:
        self.archive_format = archive_format

    def create(
        self,
        sources: Iterable[Path],
        destination: Path,
        options: CompressionOptions,
        progress: ProgressCallback | None = None,
    ) -> None:
        paths = iter_input_files(sources)
        base_dir = _common_base(paths)
        files = _expand_files(paths)
        with tarfile.open(destination, _tar_mode(self.archive_format, write=True)) as archive:
            for index, file_path in enumerate(files, start=1):
                arcname = archive_name_for(file_path, base_dir)
                archive.add(file_path, arcname=arcname, recursive=False)
                _emit(progress, index, len(files), arcname)

    def extract(
        self,
        archive_path: Path,
        destination: Path,
        options: ExtractionOptions,
        progress: ProgressCallback | None = None,
    ) -> None:
        root = _extraction_root(archive_path, destination, options.create_root_folder)
        with tarfile.open(archive_path, _tar_mode(self.archive_format, write=False)) as archive:
            members = archive.getmembers()
            selected = set(options.selected_members or [])
            if selected:
                members = [member for member in members if member.name in selected]
            for member in members:
                safe_destination(root, member.name)
            for index, member in enumerate(members, start=1):
                target = resolve_conflict(
                    safe_destination(root, member.name),
                    options.overwrite_policy,
                )
                if target is None:
                    _emit(progress, index, len(members), f"Skipped {member.name}")
                    continue
                _extract_tar_member(archive, member, target)
                _emit(progress, index, len(members), member.name)

    def list_entries(self, archive_path: Path, password: str | None = None) -> list[ArchiveEntry]:
        with tarfile.open(archive_path, _tar_mode(self.archive_format, write=False)) as archive:
            return [
                ArchiveEntry(
                    name=item.name,
                    size=item.size,
                    is_dir=item.isdir(),
                    modified_at=item.mtime,
                )
                for item in archive.getmembers()
            ]


class SevenZipBackend(ArchiveBackend):
    """7Z backend powered by py7zr."""

    archive_format = ArchiveFormat.SEVEN_Z
    supports_password_write = True

    def create(
        self,
        sources: Iterable[Path],
        destination: Path,
        options: CompressionOptions,
        progress: ProgressCallback | None = None,
    ) -> None:
        py7zr = _import_optional("py7zr")
        paths = iter_input_files(sources)
        base_dir = _common_base(paths)
        files = _expand_files(paths)
        with py7zr.SevenZipFile(destination, "w", password=options.password) as archive:
            for index, file_path in enumerate(files, start=1):
                arcname = archive_name_for(file_path, base_dir)
                archive.write(file_path, arcname=arcname)
                _emit(progress, index, len(files), arcname)

    def extract(
        self,
        archive_path: Path,
        destination: Path,
        options: ExtractionOptions,
        progress: ProgressCallback | None = None,
    ) -> None:
        py7zr = _import_optional("py7zr")
        root = _extraction_root(archive_path, destination, options.create_root_folder)
        with py7zr.SevenZipFile(archive_path, "r", password=options.password) as archive:
            names = archive.getnames()
            for name in _selected_names(names, options.selected_members):
                safe_destination(root, name)
            targets = list(_selected_names(names, options.selected_members))
            archive.extract(path=root, targets=targets or None)
            _emit(progress, 1, 1, "7Z extraction completed")

    def list_entries(self, archive_path: Path, password: str | None = None) -> list[ArchiveEntry]:
        py7zr = _import_optional("py7zr")
        with py7zr.SevenZipFile(archive_path, "r", password=password) as archive:
            return [ArchiveEntry(name=name, size=0) for name in archive.getnames()]


class RarBackend(ArchiveBackend):
    """RAR extraction backend powered by rarfile."""

    archive_format = ArchiveFormat.RAR
    can_write = False

    def create(
        self,
        sources: Iterable[Path],
        destination: Path,
        options: CompressionOptions,
        progress: ProgressCallback | None = None,
    ) -> None:
        raise UnsupportedFormatError("RAR creation is not supported.")

    def extract(
        self,
        archive_path: Path,
        destination: Path,
        options: ExtractionOptions,
        progress: ProgressCallback | None = None,
    ) -> None:
        rarfile = _import_optional("rarfile")
        root = _extraction_root(archive_path, destination, options.create_root_folder)
        with rarfile.RarFile(archive_path) as archive:
            if options.password:
                archive.setpassword(options.password)
            infos = archive.infolist()
            names = _selected_names([item.filename for item in infos], options.selected_members)
            for name in names:
                safe_destination(root, name)
            for index, name in enumerate(names, start=1):
                info = archive.getinfo(name)
                target = resolve_conflict(safe_destination(root, name), options.overwrite_policy)
                if target is None:
                    continue
                if info.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(info) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)
                _emit(progress, index, len(names), name)

    def list_entries(self, archive_path: Path, password: str | None = None) -> list[ArchiveEntry]:
        rarfile = _import_optional("rarfile")
        with rarfile.RarFile(archive_path) as archive:
            return [
                ArchiveEntry(
                    name=item.filename,
                    size=item.file_size,
                    compressed_size=item.compress_size,
                    is_dir=item.isdir(),
                )
                for item in archive.infolist()
            ]


class SingleFileBackend(ArchiveBackend):
    """Single-file LZ4 and Zstandard backend."""

    def __init__(self, archive_format: ArchiveFormat) -> None:
        self.archive_format = archive_format

    def create(
        self,
        sources: Iterable[Path],
        destination: Path,
        options: CompressionOptions,
        progress: ProgressCallback | None = None,
    ) -> None:
        paths = iter_input_files(sources)
        if len(paths) != 1 or not paths[0].is_file():
            raise UnsupportedFormatError(
                "LZ4 and ZSTD currently support one input file per archive."
            )
        source = paths[0]
        if self.archive_format == ArchiveFormat.LZ4:
            frame = _import_optional("lz4.frame")
            with source.open("rb") as input_file, frame.open(destination, "wb") as output_file:
                shutil.copyfileobj(input_file, output_file)
        else:
            zstandard = _import_optional("zstandard")
            compressor = zstandard.ZstdCompressor(level=compression_level(options.level, 1, 22))
            with source.open("rb") as input_file, destination.open("wb") as output_file:
                compressor.copy_stream(input_file, output_file)
        _emit(progress, 1, 1, source.name)

    def extract(
        self,
        archive_path: Path,
        destination: Path,
        options: ExtractionOptions,
        progress: ProgressCallback | None = None,
    ) -> None:
        root = _extraction_root(archive_path, destination, options.create_root_folder)
        output_name = _strip_single_file_suffix(archive_path)
        target = resolve_conflict(safe_destination(root, output_name), options.overwrite_policy)
        if target is None:
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        if self.archive_format == ArchiveFormat.LZ4:
            frame = _import_optional("lz4.frame")
            with frame.open(archive_path, "rb") as input_file, target.open("wb") as output_file:
                shutil.copyfileobj(input_file, output_file)
        else:
            zstandard = _import_optional("zstandard")
            decompressor = zstandard.ZstdDecompressor()
            with archive_path.open("rb") as input_file, target.open("wb") as output_file:
                decompressor.copy_stream(input_file, output_file)
        _emit(progress, 1, 1, target.name)

    def list_entries(self, archive_path: Path, password: str | None = None) -> list[ArchiveEntry]:
        return [
            ArchiveEntry(
                name=_strip_single_file_suffix(archive_path),
                size=archive_path.stat().st_size,
            )
        ]


class ArchiveService:
    """Facade for archive operations used by the GUI and CLI."""

    def __init__(self) -> None:
        self._backends: dict[ArchiveFormat, ArchiveBackend] = {
            ArchiveFormat.ZIP: ZipBackend(),
            ArchiveFormat.SEVEN_Z: SevenZipBackend(),
            ArchiveFormat.TAR: TarBackend(ArchiveFormat.TAR),
            ArchiveFormat.TAR_GZ: TarBackend(ArchiveFormat.TAR_GZ),
            ArchiveFormat.TAR_BZ2: TarBackend(ArchiveFormat.TAR_BZ2),
            ArchiveFormat.TAR_XZ: TarBackend(ArchiveFormat.TAR_XZ),
            ArchiveFormat.LZ4: SingleFileBackend(ArchiveFormat.LZ4),
            ArchiveFormat.ZSTD: SingleFileBackend(ArchiveFormat.ZSTD),
            ArchiveFormat.RAR: RarBackend(),
        }

    def create_archive(
        self,
        sources: Iterable[Path],
        destination: Path,
        options: CompressionOptions,
        progress: ProgressCallback | None = None,
    ) -> None:
        """Create an archive with the requested backend."""
        backend = self._backend(options.archive_format)
        if not backend.can_write:
            raise UnsupportedFormatError(f"{options.archive_format.value} cannot be created.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        backend.create(sources, destination, options, progress)

    def extract_archive(
        self,
        archive_path: Path,
        destination: Path,
        options: ExtractionOptions,
        progress: ProgressCallback | None = None,
    ) -> None:
        """Extract an archive into a destination directory."""
        archive_format = detect_format(archive_path)
        destination.mkdir(parents=True, exist_ok=True)
        self._backend(archive_format).extract(archive_path, destination, options, progress)

    def list_entries(self, archive_path: Path, password: str | None = None) -> list[ArchiveEntry]:
        """List archive contents."""
        return self._backend(detect_format(archive_path)).list_entries(
            archive_path,
            password=password,
        )

    def info(self, archive_path: Path, include_hash: bool = False) -> ArchiveInfo:
        """Return basic archive metadata."""
        entries = self.list_entries(archive_path)
        return ArchiveInfo(
            path=archive_path,
            archive_format=detect_format(archive_path),
            size=archive_path.stat().st_size,
            entries=len(entries),
            sha256=sha256_file(archive_path) if include_hash else None,
        )

    def test_archive(self, archive_path: Path) -> list[str]:
        """Return corrupt member names found by a format integrity check."""
        archive_format = detect_format(archive_path)
        if archive_format == ArchiveFormat.ZIP:
            with zipfile.ZipFile(archive_path) as archive:
                bad_member = archive.testzip()
            return [bad_member] if bad_member else []
        if archive_format in {
            ArchiveFormat.TAR,
            ArchiveFormat.TAR_GZ,
            ArchiveFormat.TAR_BZ2,
            ArchiveFormat.TAR_XZ,
        }:
            with tarfile.open(archive_path, _tar_mode(archive_format, write=False)) as archive:
                for member in archive.getmembers():
                    if member.isfile():
                        extracted = archive.extractfile(member)
                        if extracted is not None:
                            while extracted.read(1024 * 1024):
                                pass
            return []
        self.list_entries(archive_path)
        return []

    def add_to_zip(self, archive_path: Path, sources: Iterable[Path]) -> None:
        """Add files or folders to an existing ZIP archive."""
        _require_zip(archive_path)
        paths = iter_input_files(sources)
        base_dir = _common_base(paths)
        files = _expand_files(paths)
        existing = {entry.name for entry in self.list_entries(archive_path)}
        with zipfile.ZipFile(archive_path, "a", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_path in files:
                arcname = archive_name_for(file_path, base_dir)
                if arcname in existing:
                    arcname = _unique_member_name(existing, arcname)
                archive.write(file_path, arcname)
                existing.add(arcname)

    def remove_from_zip(self, archive_path: Path, members: Iterable[str]) -> None:
        """Remove members from a ZIP archive by rewriting it."""
        _require_zip(archive_path)
        targets = set(members)
        _rewrite_zip(archive_path, skip=targets)

    def rename_in_zip(self, archive_path: Path, old_name: str, new_name: str) -> None:
        """Rename a member inside a ZIP archive by rewriting it."""
        _require_zip(archive_path)
        if not old_name or not new_name:
            raise ValueError("Both old and new member names are required.")
        safe_destination(Path.cwd(), new_name)
        _rewrite_zip(archive_path, rename={old_name: new_name})

    def _backend(self, archive_format: ArchiveFormat) -> ArchiveBackend:
        try:
            return self._backends[archive_format]
        except KeyError as exc:
            raise UnsupportedFormatError(archive_format.value) from exc


def _expand_files(paths: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_file():
            files.append(path)
        else:
            files.extend(sorted((item for item in path.rglob("*") if item.is_file()), key=str))
    return files


def _common_base(paths: list[Path]) -> Path:
    if len(paths) == 1:
        return paths[0].parent if paths[0].is_file() else paths[0].parent
    parents = [str(path.parent if path.is_file() else path.parent) for path in paths]
    common = os.path.commonpath(parents)
    return Path(common).resolve()


def _selected_names(names: Iterable[str], selected: tuple[str, ...] | None) -> list[str]:
    all_names = list(names)
    if not selected:
        return all_names
    selected_set = set(selected)
    return [name for name in all_names if name in selected_set]


def _emit(progress: ProgressCallback | None, index: int, total: int, message: str) -> None:
    if progress is None:
        return
    percent = int(index / max(total, 1) * 100)
    progress(ProgressEvent(percent=percent, message=message, current_file=message))


def _tar_mode(archive_format: ArchiveFormat, write: bool) -> str:
    prefix = "w" if write else "r"
    modes = {
        ArchiveFormat.TAR: f"{prefix}:",
        ArchiveFormat.TAR_GZ: f"{prefix}:gz",
        ArchiveFormat.TAR_BZ2: f"{prefix}:bz2",
        ArchiveFormat.TAR_XZ: f"{prefix}:xz",
    }
    return modes[archive_format]


def _extract_tar_member(archive: tarfile.TarFile, member: tarfile.TarInfo, target: Path) -> None:
    if member.isdir():
        target.mkdir(parents=True, exist_ok=True)
        return
    if member.issym() or member.islnk():
        return
    extracted = archive.extractfile(member)
    if extracted is None:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    with extracted, target.open("wb") as output:
        shutil.copyfileobj(extracted, output)


def _extraction_root(archive_path: Path, destination: Path, create_root_folder: bool) -> Path:
    if create_root_folder:
        root = destination / archive_path.name.split(".")[0]
        root.mkdir(parents=True, exist_ok=True)
        return root
    return destination


def _strip_single_file_suffix(path: Path) -> str:
    name = path.name
    for suffix in (".lz4", ".zstd", ".zst"):
        if name.lower().endswith(suffix):
            return name[: -len(suffix)] or "output"
    return f"{path.stem}.out"


def _require_zip(archive_path: Path) -> None:
    if detect_format(archive_path) != ArchiveFormat.ZIP:
        raise UnsupportedFormatError("Archive management is currently supported for ZIP.")


def _unique_member_name(existing: set[str], name: str) -> str:
    path = Path(name)
    stem = path.stem
    suffix = path.suffix
    parent = path.parent.as_posix()
    index = 1
    while True:
        candidate_name = f"{stem} ({index}){suffix}"
        candidate = candidate_name if parent == "." else f"{parent}/{candidate_name}"
        if candidate not in existing:
            return candidate
        index += 1


def _rewrite_zip(
    archive_path: Path,
    skip: set[str] | None = None,
    rename: dict[str, str] | None = None,
) -> None:
    skip = skip or set()
    rename = rename or {}
    with tempfile.NamedTemporaryFile(
        prefix=f".{archive_path.name}.",
        suffix=".tmp",
        dir=archive_path.parent,
        delete=False,
    ) as temp_file:
        temp_path = Path(temp_file.name)
    try:
        with zipfile.ZipFile(archive_path, "r") as source_archive, zipfile.ZipFile(
            temp_path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
        ) as target_archive:
            target_archive.comment = source_archive.comment
            for info in source_archive.infolist():
                if info.filename in skip:
                    continue
                data = source_archive.read(info.filename)
                info.filename = rename.get(info.filename, info.filename)
                target_archive.writestr(info, data)
        temp_path.replace(archive_path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise


def _import_optional(module_name: str):
    try:
        return __import__(module_name, fromlist=["*"])
    except ImportError as exc:
        raise MissingOptionalDependencyError(
            f"Install optional dependency for {module_name}."
        ) from exc


def preview_text(archive_path: Path, member_name: str, password: str | None = None) -> str:
    """Read a text member preview from ZIP archives."""
    if detect_format(archive_path) != ArchiveFormat.ZIP:
        raise UnsupportedFormatError("Text preview is currently implemented for ZIP archives.")
    pwd = password.encode("utf-8") if password else None
    with zipfile.ZipFile(archive_path) as archive, archive.open(member_name, pwd=pwd) as member:
        raw = member.read(1024 * 256)
    return raw.decode("utf-8", errors="replace")


def convert_archive(
    source_archive: Path,
    destination_archive: Path,
    archive_format: ArchiveFormat,
    progress: ProgressCallback | None = None,
) -> None:
    """Convert an archive by extracting to memory-friendly temp storage then recompressing."""
    import tempfile

    service = ArchiveService()
    with tempfile.TemporaryDirectory(prefix="zipora-convert-") as temp_dir:
        temp_path = Path(temp_dir)
        service.extract_archive(source_archive, temp_path, ExtractionOptions(), progress)
        sources = list(temp_path.iterdir())
        service.create_archive(
            sources,
            destination_archive,
            CompressionOptions(archive_format=archive_format),
            progress,
        )


def zip_from_bytes(name: str, data: bytes, destination: Path) -> None:
    """Small helper used by tests and integrations."""
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, data)


def file_preview_bytes(archive_path: Path, member_name: str) -> bytes:
    """Return a small binary preview payload from a ZIP member."""
    with zipfile.ZipFile(archive_path) as archive, archive.open(member_name) as file_obj:
        return file_obj.read(1024 * 256)


def archive_to_memory(entries: dict[str, bytes]) -> bytes:
    """Build a ZIP archive in memory."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()
