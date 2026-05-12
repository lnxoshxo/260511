"""Main application window."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QThreadPool
from PyQt6.QtGui import QAction, QDragEnterEvent, QDropEvent, QKeySequence
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from zipora.core.archive_service import ArchiveService, preview_text
from zipora.core.favorites import FavoritesStore
from zipora.core.history import HistoryStore
from zipora.core.models import (
    ArchiveEntry,
    ArchiveFormat,
    CompressionOptions,
    ExtractionOptions,
)
from zipora.core.settings import SettingsStore
from zipora.core.utils import detect_format
from zipora.gui.settings_dialog import SettingsDialog
from zipora.gui.styles import DARK_THEME, LIGHT_THEME
from zipora.gui.workers import CompressWorker, ExtractWorker


class MainWindow(QMainWindow):
    """Modern archive manager window."""

    def __init__(self) -> None:
        super().__init__()
        self.service = ArchiveService()
        self.settings_store = SettingsStore()
        self.settings = self.settings_store.load()
        self.history = HistoryStore()
        self.favorites = FavoritesStore()
        self.thread_pool = QThreadPool.globalInstance()
        self.current_archive: Path | None = None
        self.selected_sources: list[Path] = []
        self.setAcceptDrops(True)
        self.setWindowTitle("Zipora 压缩解压缩工具")
        self.resize(1060, 700)
        self._build_ui()
        self._apply_theme()

    def _build_ui(self) -> None:
        self._build_actions()
        self._build_menu()
        self._build_toolbar()

        title = QLabel("拖拽文件到窗口，或使用工具栏开始压缩与解压")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: 600; padding: 16px;")

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["名称", "大小", "压缩后", "类型", "修改时间"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemDoubleClicked.connect(self._preview_selected)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addWidget(self.table)
        layout.addWidget(self.progress)
        wrapper = QWidget()
        wrapper.setLayout(layout)
        self.setCentralWidget(wrapper)
        self.statusBar().showMessage("就绪")

    def _build_actions(self) -> None:
        self.open_action = QAction("打开压缩包", self)
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.triggered.connect(self.open_archive)

        self.compress_action = QAction("压缩", self)
        self.compress_action.setShortcut("Ctrl+N")
        self.compress_action.triggered.connect(self.compress_files)

        self.extract_action = QAction("解压", self)
        self.extract_action.setShortcut("Ctrl+E")
        self.extract_action.triggered.connect(self.extract_archive)

        self.info_action = QAction("信息", self)
        self.info_action.triggered.connect(self.show_archive_info)

        self.test_action = QAction("校验", self)
        self.test_action.triggered.connect(self.test_current_archive)

        self.add_zip_action = QAction("添加到 ZIP", self)
        self.add_zip_action.triggered.connect(self.add_files_to_zip)

        self.remove_zip_action = QAction("从 ZIP 删除", self)
        self.remove_zip_action.setShortcut(QKeySequence.StandardKey.Delete)
        self.remove_zip_action.triggered.connect(self.remove_selected_from_zip)

        self.rename_zip_action = QAction("重命名 ZIP 条目", self)
        self.rename_zip_action.setShortcut(QKeySequence.StandardKey.Rename)
        self.rename_zip_action.triggered.connect(self.rename_selected_in_zip)

        self.favorite_action = QAction("加入收藏", self)
        self.favorite_action.triggered.connect(self.add_current_to_favorites)

        self.settings_action = QAction("设置", self)
        self.settings_action.triggered.connect(self.open_settings)

        self.theme_action = QAction("切换主题", self)
        self.theme_action.triggered.connect(self.toggle_theme)

        self.exit_action = QAction("退出", self)
        self.exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self.exit_action.triggered.connect(self.close)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("文件")
        file_menu.addAction(self.open_action)
        file_menu.addAction(self.compress_action)
        file_menu.addAction(self.extract_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        view_menu = self.menuBar().addMenu("视图")
        view_menu.addAction(self.info_action)
        view_menu.addAction(self.test_action)
        view_menu.addAction(self.theme_action)

        manage_menu = self.menuBar().addMenu("管理")
        manage_menu.addAction(self.add_zip_action)
        manage_menu.addAction(self.remove_zip_action)
        manage_menu.addAction(self.rename_zip_action)
        manage_menu.addAction(self.favorite_action)
        manage_menu.addAction(self.settings_action)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        toolbar.addAction(self.open_action)
        toolbar.addAction(self.compress_action)
        toolbar.addAction(self.extract_action)
        toolbar.addAction(self.info_action)
        toolbar.addAction(self.test_action)
        toolbar.addAction(self.theme_action)
        self.addToolBar(toolbar)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        if not paths:
            return
        first = paths[0]
        try:
            detect_format(first)
        except ValueError:
            self.selected_sources = paths
            self.statusBar().showMessage(f"已选择 {len(paths)} 个输入项")
            self._show_sources(paths)
            return
        self.load_archive(first)

    def open_archive(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "打开压缩包",
            "",
            "Archives (*.zip *.7z *.rar *.tar *.tar.gz *.tgz *.tar.bz2 *.tar.xz *.lz4 *.zst)",
        )
        if path:
            self.load_archive(Path(path))

    def load_archive(self, path: Path) -> None:
        try:
            entries = self.service.list_entries(path)
        except Exception as exc:  # noqa: BLE001
            self._error("打开失败", str(exc))
            return
        self.current_archive = path
        self._show_entries(entries)
        self.statusBar().showMessage(f"已打开：{path}")

    def compress_files(self) -> None:
        paths = self.selected_sources or self._choose_sources()
        if not paths:
            return
        destination, _ = QFileDialog.getSaveFileName(
            self,
            "保存压缩包",
            str(Path.home() / "archive.zip"),
            "ZIP (*.zip);;7Z (*.7z);;TAR (*.tar);;TAR.GZ (*.tar.gz);;"
            "TAR.BZ2 (*.tar.bz2);;TAR.XZ (*.tar.xz);;LZ4 (*.lz4);;ZSTD (*.zst)",
        )
        if not destination:
            return
        try:
            archive_format = detect_format(Path(destination))
        except ValueError:
            archive_format = ArchiveFormat.ZIP
        password = self._password_prompt("设置密码（可留空）")
        options = CompressionOptions(archive_format=archive_format, password=password or None)
        worker = CompressWorker(paths, Path(destination), options)
        worker.signals.progress.connect(self._on_progress)
        worker.signals.finished.connect(lambda result: self._task_done("压缩完成", result))
        worker.signals.failed.connect(lambda message: self._error("压缩失败", message))
        self.thread_pool.start(worker)
        self.statusBar().showMessage("正在后台压缩...")

    def extract_archive(self) -> None:
        archive = self.current_archive
        if archive is None:
            path, _ = QFileDialog.getOpenFileName(self, "选择压缩包", "")
            archive = Path(path) if path else None
        if archive is None:
            return
        destination = QFileDialog.getExistingDirectory(self, "选择解压目录")
        if not destination:
            return
        password = self._password_prompt("输入密码（可留空）")
        options = ExtractionOptions(password=password or None, create_root_folder=True)
        worker = ExtractWorker(archive, Path(destination), options)
        worker.signals.progress.connect(self._on_progress)
        worker.signals.finished.connect(lambda result: self._task_done("解压完成", result))
        worker.signals.failed.connect(lambda message: self._error("解压失败", message))
        self.thread_pool.start(worker)
        self.statusBar().showMessage("正在后台解压...")

    def show_archive_info(self) -> None:
        if self.current_archive is None:
            self._error("提示", "请先打开一个压缩包。")
            return
        try:
            info = self.service.info(self.current_archive, include_hash=True)
        except Exception as exc:  # noqa: BLE001
            self._error("读取信息失败", str(exc))
            return
        QMessageBox.information(
            self,
            "压缩包信息",
            f"路径：{info.path}\n格式：{info.archive_format.value}\n大小：{info.size} 字节\n"
            f"条目数：{info.entries}\nSHA256：{info.sha256}",
        )

    def test_current_archive(self) -> None:
        if self.current_archive is None:
            self._error("提示", "请先打开一个压缩包。")
            return
        try:
            bad_members = self.service.test_archive(self.current_archive)
        except Exception as exc:  # noqa: BLE001
            self._error("校验失败", str(exc))
            return
        if bad_members:
            QMessageBox.warning(self, "校验完成", "损坏条目：\n" + "\n".join(bad_members))
            return
        QMessageBox.information(self, "校验完成", "压缩包完整性校验通过。")

    def add_files_to_zip(self) -> None:
        if self.current_archive is None:
            self._error("提示", "请先打开一个 ZIP 压缩包。")
            return
        paths = self._choose_sources()
        if not paths:
            return
        try:
            self.service.add_to_zip(self.current_archive, paths)
            self.load_archive(self.current_archive)
        except Exception as exc:  # noqa: BLE001
            self._error("添加失败", str(exc))

    def remove_selected_from_zip(self) -> None:
        member = self._selected_member_name()
        if self.current_archive is None or member is None:
            self._error("提示", "请先选择一个 ZIP 条目。")
            return
        try:
            self.service.remove_from_zip(self.current_archive, [member])
            self.load_archive(self.current_archive)
        except Exception as exc:  # noqa: BLE001
            self._error("删除失败", str(exc))

    def rename_selected_in_zip(self) -> None:
        member = self._selected_member_name()
        if self.current_archive is None or member is None:
            self._error("提示", "请先选择一个 ZIP 条目。")
            return
        new_name, ok = QInputDialog.getText(self, "重命名", "新名称：", text=member)
        if not ok or not new_name:
            return
        try:
            self.service.rename_in_zip(self.current_archive, member, new_name)
            self.load_archive(self.current_archive)
        except Exception as exc:  # noqa: BLE001
            self._error("重命名失败", str(exc))

    def add_current_to_favorites(self) -> None:
        if self.current_archive is None:
            self._error("提示", "请先打开一个压缩包。")
            return
        self.favorites.add(self.current_archive.name, self.current_archive)
        self.statusBar().showMessage("已加入收藏")

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings)
        if dialog.exec():
            self.settings = dialog.apply_to(self.settings)
            self.settings_store.save(self.settings)
            self._apply_theme()

    def toggle_theme(self) -> None:
        self.settings.theme = "dark" if self.settings.theme == "light" else "light"
        self.settings_store.save(self.settings)
        self._apply_theme()

    def _apply_theme(self) -> None:
        self.setStyleSheet(DARK_THEME if self.settings.theme == "dark" else LIGHT_THEME)

    def _choose_sources(self) -> list[Path]:
        dialog = QFileDialog(self, "选择要压缩的文件")
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        if dialog.exec():
            return [Path(path) for path in dialog.selectedFiles()]
        return []

    def _show_entries(self, entries: list[ArchiveEntry]) -> None:
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            values = [
                entry.name,
                str(entry.size),
                "" if entry.compressed_size is None else str(entry.compressed_size),
                "文件夹" if entry.is_dir else "文件",
                "" if entry.modified_at is None else str(entry.modified_at),
            ]
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))

    def _show_sources(self, paths: list[Path]) -> None:
        self.table.setRowCount(len(paths))
        for row, path in enumerate(paths):
            size = path.stat().st_size if path.is_file() else 0
            values = [path.name, str(size), "", "文件夹" if path.is_dir() else "文件", ""]
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))

    def _preview_selected(self) -> None:
        if self.current_archive is None or self.table.currentRow() < 0:
            return
        member = self.table.item(self.table.currentRow(), 0).text()
        try:
            content = preview_text(self.current_archive, member)
        except Exception as exc:  # noqa: BLE001
            self._error("预览失败", str(exc))
            return
        QMessageBox.information(self, f"预览：{member}", content[:4000])

    def _selected_member_name(self) -> str | None:
        if self.table.currentRow() < 0:
            return None
        item = self.table.item(self.table.currentRow(), 0)
        return item.text() if item else None

    def _password_prompt(self, title: str) -> str:
        password, ok = QInputDialog.getText(self, title, "密码：")
        return password if ok else ""

    def _on_progress(self, percent: int, message: str) -> None:
        self.progress.setValue(percent)
        self.statusBar().showMessage(message)

    def _task_done(self, title: str, result: str) -> None:
        self.progress.setValue(100)
        self.statusBar().showMessage(result)
        QMessageBox.information(self, title, result)

    def _error(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)
        self.statusBar().showMessage(message)


class SourcePicker(QWidget):
    """Reserved widget for future folder and batch source picking."""

    def __init__(self) -> None:
        super().__init__()
        layout = QHBoxLayout()
        layout.addWidget(QLabel("Source picker"))
        self.setLayout(layout)
