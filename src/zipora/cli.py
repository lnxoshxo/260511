"""Command-line interface for Zipora."""

from __future__ import annotations

import argparse
from pathlib import Path

from tqdm import tqdm

from zipora.core.archive_service import ArchiveService, convert_archive
from zipora.core.favorites import FavoritesStore
from zipora.core.models import ArchiveFormat, CompressionOptions, ExtractionOptions, ProgressEvent
from zipora.core.utils import detect_format


def main(argv: list[str] | None = None) -> int:
    """Run the CLI or launch the GUI."""
    parser = argparse.ArgumentParser(prog="zipora", description="Zipora archive manager")
    subparsers = parser.add_subparsers(dest="command")

    create_parser = subparsers.add_parser("create", help="Create an archive")
    create_parser.add_argument("destination", type=Path)
    create_parser.add_argument("sources", nargs="+", type=Path)
    create_parser.add_argument("--format", choices=[item.value for item in ArchiveFormat])
    create_parser.add_argument("--level", type=int, default=6)
    create_parser.add_argument("--password")

    extract_parser = subparsers.add_parser("extract", help="Extract an archive")
    extract_parser.add_argument("archive", type=Path)
    extract_parser.add_argument("destination", type=Path)
    extract_parser.add_argument("--password")

    batch_create_parser = subparsers.add_parser(
        "batch-create",
        help="Create one archive per source",
    )
    batch_create_parser.add_argument("destination_dir", type=Path)
    batch_create_parser.add_argument("sources", nargs="+", type=Path)
    batch_create_parser.add_argument("--format", default=ArchiveFormat.ZIP.value)
    batch_create_parser.add_argument("--level", type=int, default=6)

    batch_extract_parser = subparsers.add_parser("batch-extract", help="Extract multiple archives")
    batch_extract_parser.add_argument("destination_dir", type=Path)
    batch_extract_parser.add_argument("archives", nargs="+", type=Path)

    list_parser = subparsers.add_parser("list", help="List archive entries")
    list_parser.add_argument("archive", type=Path)

    info_parser = subparsers.add_parser("info", help="Show archive information")
    info_parser.add_argument("archive", type=Path)
    info_parser.add_argument("--hash", action="store_true")

    test_parser = subparsers.add_parser("test", help="Test archive integrity")
    test_parser.add_argument("archive", type=Path)

    add_parser = subparsers.add_parser("zip-add", help="Add files to a ZIP archive")
    add_parser.add_argument("archive", type=Path)
    add_parser.add_argument("sources", nargs="+", type=Path)

    remove_parser = subparsers.add_parser("zip-remove", help="Remove entries from a ZIP archive")
    remove_parser.add_argument("archive", type=Path)
    remove_parser.add_argument("members", nargs="+")

    rename_parser = subparsers.add_parser("zip-rename", help="Rename one ZIP entry")
    rename_parser.add_argument("archive", type=Path)
    rename_parser.add_argument("old_name")
    rename_parser.add_argument("new_name")

    favorites_parser = subparsers.add_parser("favorites", help="Manage favorites")
    favorites_subparsers = favorites_parser.add_subparsers(dest="favorites_command")
    favorites_subparsers.add_parser("list", help="List favorites")
    favorites_add = favorites_subparsers.add_parser("add", help="Add favorite")
    favorites_add.add_argument("name")
    favorites_add.add_argument("path", type=Path)
    favorites_remove = favorites_subparsers.add_parser("remove", help="Remove favorite")
    favorites_remove.add_argument("path", type=Path)

    convert_parser = subparsers.add_parser("convert", help="Convert archive format")
    convert_parser.add_argument("source", type=Path)
    convert_parser.add_argument("destination", type=Path)
    convert_parser.add_argument(
        "--format",
        required=True,
        choices=[item.value for item in ArchiveFormat],
    )

    args = parser.parse_args(argv)
    if args.command is None:
        from zipora.app import main as gui_main

        return gui_main()

    service = ArchiveService()
    if args.command == "create":
        archive_format = (
            ArchiveFormat(args.format) if args.format else detect_format(args.destination)
        )
        progress = _progress_bar()
        service.create_archive(
            args.sources,
            args.destination,
            CompressionOptions(
                archive_format=archive_format,
                level=args.level,
                password=args.password,
            ),
            progress,
        )
        return 0
    if args.command == "extract":
        progress = _progress_bar()
        service.extract_archive(
            args.archive,
            args.destination,
            ExtractionOptions(password=args.password, create_root_folder=False),
            progress,
        )
        return 0
    if args.command == "batch-create":
        archive_format = ArchiveFormat(args.format)
        for source in args.sources:
            suffix = _suffix_for_format(archive_format)
            destination = args.destination_dir / f"{source.stem}{suffix}"
            service.create_archive(
                [source],
                destination,
                CompressionOptions(archive_format=archive_format, level=args.level),
                _progress_bar(),
            )
        return 0
    if args.command == "batch-extract":
        for archive in args.archives:
            destination = args.destination_dir / archive.name.split(".")[0]
            service.extract_archive(
                archive,
                destination,
                ExtractionOptions(create_root_folder=False),
                _progress_bar(),
            )
        return 0
    if args.command == "list":
        for entry in service.list_entries(args.archive):
            suffix = "/" if entry.is_dir else ""
            print(f"{entry.size:>12} {entry.name}{suffix}")
        return 0
    if args.command == "info":
        info = service.info(args.archive, include_hash=args.hash)
        print(f"Path: {info.path}")
        print(f"Format: {info.archive_format.value}")
        print(f"Size: {info.size}")
        print(f"Entries: {info.entries}")
        if info.sha256:
            print(f"SHA256: {info.sha256}")
        return 0
    if args.command == "test":
        bad_members = service.test_archive(args.archive)
        if bad_members:
            for member in bad_members:
                print(f"BAD: {member}")
            return 2
        print("OK")
        return 0
    if args.command == "zip-add":
        service.add_to_zip(args.archive, args.sources)
        return 0
    if args.command == "zip-remove":
        service.remove_from_zip(args.archive, args.members)
        return 0
    if args.command == "zip-rename":
        service.rename_in_zip(args.archive, args.old_name, args.new_name)
        return 0
    if args.command == "convert":
        convert_archive(args.source, args.destination, ArchiveFormat(args.format), _progress_bar())
        return 0
    if args.command == "favorites":
        return _favorites(args)
    return 1


def _progress_bar():
    bar = tqdm(total=100, unit="%")

    def update(event: ProgressEvent) -> None:
        delta = max(0, event.percent - bar.n)
        bar.update(delta)
        bar.set_description(event.message[:40])
        if event.percent >= 100:
            bar.close()

    return update


def _favorites(args: argparse.Namespace) -> int:
    store = FavoritesStore()
    if args.favorites_command == "add":
        store.add(args.name, args.path)
        return 0
    if args.favorites_command == "remove":
        store.remove(args.path)
        return 0
    for item in store.list_items():
        print(f"{item.name}\t{item.path}")
    return 0


def _suffix_for_format(archive_format: ArchiveFormat) -> str:
    suffixes = {
        ArchiveFormat.ZIP: ".zip",
        ArchiveFormat.SEVEN_Z: ".7z",
        ArchiveFormat.TAR: ".tar",
        ArchiveFormat.TAR_GZ: ".tar.gz",
        ArchiveFormat.TAR_BZ2: ".tar.bz2",
        ArchiveFormat.TAR_XZ: ".tar.xz",
        ArchiveFormat.LZ4: ".lz4",
        ArchiveFormat.ZSTD: ".zst",
        ArchiveFormat.RAR: ".rar",
    }
    return suffixes[archive_format]


if __name__ == "__main__":
    raise SystemExit(main())
