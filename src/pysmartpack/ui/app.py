"""Application bootstrap."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from ..core import persistence
from .main_window import MainWindow
from .theme import apply_theme


def run() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    settings = persistence.load_settings()
    apply_theme(app, dark=settings.get("theme", "dark") == "dark")
    window = MainWindow()
    window.show()
    return app.exec()
