"""Application stylesheets."""

LIGHT_THEME = """
QMainWindow { background: #f6f7fb; }
QToolBar { background: #ffffff; border: 0; padding: 8px; spacing: 8px; }
QPushButton, QToolButton {
    background: #2563eb; color: white; border: 0; border-radius: 8px; padding: 8px 12px;
}
QPushButton:hover, QToolButton:hover { background: #1d4ed8; }
QTableWidget, QTreeWidget {
    background: #ffffff; border: 1px solid #e5e7eb; border-radius: 10px; gridline-color: #edf0f5;
}
QHeaderView::section { background: #f3f4f6; padding: 8px; border: 0; }
QProgressBar { border: 0; border-radius: 8px; background: #e5e7eb; height: 16px; }
QProgressBar::chunk { border-radius: 8px; background: #22c55e; }
QStatusBar { background: #ffffff; color: #475569; }
"""

DARK_THEME = """
QMainWindow { background: #0f172a; color: #e2e8f0; }
QToolBar { background: #111827; border: 0; padding: 8px; spacing: 8px; }
QPushButton, QToolButton {
    background: #38bdf8; color: #082f49; border: 0; border-radius: 8px; padding: 8px 12px;
}
QPushButton:hover, QToolButton:hover { background: #7dd3fc; }
QTableWidget, QTreeWidget {
    background: #111827; color: #e2e8f0; border: 1px solid #334155; border-radius: 10px;
}
QHeaderView::section { background: #1e293b; color: #e2e8f0; padding: 8px; border: 0; }
QProgressBar { border: 0; border-radius: 8px; background: #334155; height: 16px; }
QProgressBar::chunk { border-radius: 8px; background: #22c55e; }
QStatusBar { background: #111827; color: #cbd5e1; }
"""
