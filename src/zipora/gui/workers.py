"""Qt workers for background archive tasks."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot

from zipora.core.archive_service import ArchiveService
from zipora.core.models import CompressionOptions, ExtractionOptions, ProgressEvent


class WorkerSignals(QObject):
    """Signals emitted by a background task."""

    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str)
    failed = pyqtSignal(str)


class CompressWorker(QRunnable):
    """Create an archive on a worker thread."""

    def __init__(
        self,
        sources: Iterable[Path],
        destination: Path,
        options: CompressionOptions,
    ) -> None:
        super().__init__()
        self.sources = list(sources)
        self.destination = destination
        self.options = options
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self) -> None:
        service = ArchiveService()
        try:
            service.create_archive(self.sources, self.destination, self.options, self._progress)
        except Exception as exc:  # noqa: BLE001
            self.signals.failed.emit(str(exc))
            return
        self.signals.finished.emit(str(self.destination))

    def _progress(self, event: ProgressEvent) -> None:
        self.signals.progress.emit(event.percent, event.message)


class ExtractWorker(QRunnable):
    """Extract an archive on a worker thread."""

    def __init__(self, archive_path: Path, destination: Path, options: ExtractionOptions) -> None:
        super().__init__()
        self.archive_path = archive_path
        self.destination = destination
        self.options = options
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self) -> None:
        service = ArchiveService()
        try:
            service.extract_archive(
                self.archive_path,
                self.destination,
                self.options,
                self._progress,
            )
        except Exception as exc:  # noqa: BLE001
            self.signals.failed.emit(str(exc))
            return
        self.signals.finished.emit(str(self.destination))

    def _progress(self, event: ProgressEvent) -> None:
        self.signals.progress.emit(event.percent, event.message)
