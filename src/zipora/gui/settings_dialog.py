"""Settings dialog."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from zipora.core.models import ArchiveFormat
from zipora.core.settings import AppSettings


class SettingsDialog(QDialog):
    """Simple settings editor."""

    def __init__(self, settings: AppSettings) -> None:
        super().__init__()
        self.setWindowTitle("设置")
        self.format_input = QComboBox()
        self.format_input.addItems(
            [item.value for item in ArchiveFormat if item != ArchiveFormat.RAR]
        )
        self.format_input.setCurrentText(settings.default_format)

        self.level_input = QSpinBox()
        self.level_input.setRange(0, 22)
        self.level_input.setValue(settings.default_level)

        self.extract_dir_input = QLineEdit(settings.default_extract_dir)
        self.theme_input = QComboBox()
        self.theme_input.addItems(["light", "dark"])
        self.theme_input.setCurrentText(settings.theme)

        self.font_size_input = QSpinBox()
        self.font_size_input.setRange(8, 24)
        self.font_size_input.setValue(settings.font_size)

        form = QFormLayout()
        form.addRow("默认格式", self.format_input)
        form.addRow("默认压缩级别", self.level_input)
        form.addRow("默认解压路径", self.extract_dir_input)
        form.addRow("主题", self.theme_input)
        form.addRow("字体大小", self.font_size_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def apply_to(self, settings: AppSettings) -> AppSettings:
        """Copy dialog values into settings."""
        settings.default_format = self.format_input.currentText()
        settings.default_level = self.level_input.value()
        settings.default_extract_dir = self.extract_dir_input.text()
        settings.theme = self.theme_input.currentText()
        settings.font_size = self.font_size_input.value()
        return settings
