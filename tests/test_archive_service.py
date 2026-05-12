from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

import pytest

from zipora.core.archive_service import ArchiveService
from zipora.core.exceptions import UnsafeArchiveError
from zipora.core.models import ArchiveFormat, CompressionOptions, ExtractionOptions, OverwritePolicy


def test_zip_create_list_extract(tmp_path: Path) -> None:
    source = tmp_path / "hello.txt"
    source.write_text("hello zipora", encoding="utf-8")
    archive = tmp_path / "sample.zip"
    output = tmp_path / "out"

    service = ArchiveService()
    service.create_archive([source], archive, CompressionOptions(ArchiveFormat.ZIP))
    entries = service.list_entries(archive)
    service.extract_archive(archive, output, ExtractionOptions())

    assert archive.exists()
    assert entries[0].name == "hello.txt"
    assert (output / "hello.txt").read_text(encoding="utf-8") == "hello zipora"


def test_tar_gz_create_extract(tmp_path: Path) -> None:
    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "a.txt").write_text("a", encoding="utf-8")
    archive = tmp_path / "sample.tar.gz"
    output = tmp_path / "out"

    service = ArchiveService()
    service.create_archive([folder], archive, CompressionOptions(ArchiveFormat.TAR_GZ))
    service.extract_archive(archive, output, ExtractionOptions())

    assert (output / "folder" / "a.txt").read_text(encoding="utf-8") == "a"


def test_zip_path_traversal_is_blocked(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as zip_file:
        zip_file.writestr("../escape.txt", "owned")

    service = ArchiveService()
    with pytest.raises(UnsafeArchiveError):
        service.extract_archive(archive, tmp_path / "out", ExtractionOptions())


def test_tar_path_traversal_is_blocked(tmp_path: Path) -> None:
    archive = tmp_path / "unsafe.tar"
    payload = tmp_path / "payload.txt"
    payload.write_text("payload", encoding="utf-8")
    with tarfile.open(archive, "w") as tar_file:
        tar_file.add(payload, arcname="../escape.txt")

    service = ArchiveService()
    with pytest.raises(UnsafeArchiveError):
        service.extract_archive(archive, tmp_path / "out", ExtractionOptions())


def test_rename_conflicting_extracted_file(tmp_path: Path) -> None:
    source = tmp_path / "hello.txt"
    source.write_text("new", encoding="utf-8")
    archive = tmp_path / "sample.zip"
    output = tmp_path / "out"
    output.mkdir()
    (output / "hello.txt").write_text("old", encoding="utf-8")

    service = ArchiveService()
    service.create_archive([source], archive, CompressionOptions(ArchiveFormat.ZIP))
    service.extract_archive(
        archive,
        output,
        ExtractionOptions(overwrite_policy=OverwritePolicy.RENAME),
    )

    assert (output / "hello.txt").read_text(encoding="utf-8") == "old"
    assert (output / "hello (1).txt").read_text(encoding="utf-8") == "new"


def test_zip_add_remove_rename_and_test(tmp_path: Path) -> None:
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")
    archive = tmp_path / "managed.zip"

    service = ArchiveService()
    service.create_archive([first], archive, CompressionOptions(ArchiveFormat.ZIP))
    service.add_to_zip(archive, [second])
    service.rename_in_zip(archive, "second.txt", "renamed.txt")
    service.remove_from_zip(archive, ["first.txt"])

    entries = {entry.name for entry in service.list_entries(archive)}
    assert entries == {"renamed.txt"}
    assert service.test_archive(archive) == []
