"""Main application window (FluentWindow with Pack / History / Settings)."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QWidget
from qfluentwidgets import FluentIcon, FluentWindow, NavigationItemPosition

from .. import __app_name__, __version__
from .history_interface import HistoryInterface
from .pack_interface import PackInterface
from .settings_interface import SettingsInterface
from .theme import apply_theme


class MainWindow(FluentWindow):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self.pack = PackInterface(self)
        self.history = HistoryInterface(self)
        self.settings = SettingsInterface(self)

        self.addSubInterface(self.pack, FluentIcon.APPLICATION, "打包")
        self.addSubInterface(self.history, FluentIcon.HISTORY, "历史")
        self.addSubInterface(self.settings, FluentIcon.SETTING, "设置",
                             position=NavigationItemPosition.BOTTOM)

        self.settings.themeChanged.connect(self._on_theme_changed)
        self.stackedWidget.currentChanged.connect(self._on_page_changed)

        self.setWindowTitle(f"{__app_name__} v{__version__}")
        self.resize(QSize(1180, 820))

    def _on_theme_changed(self, dark: bool) -> None:
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, dark=dark)

    def _on_page_changed(self, _index: int) -> None:
        if self.stackedWidget.currentWidget() is self.history:
            self.history.refresh()
