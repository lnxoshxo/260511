"""GUI application bootstrap."""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from zipora.gui.main_window import MainWindow


def main() -> int:
    """Start the Qt application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Zipora")
    app.setOrganizationName("Zipora")
    window = MainWindow()
    window.show()
    return app.exec()
