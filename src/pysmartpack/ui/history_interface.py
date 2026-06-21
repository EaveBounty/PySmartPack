"""History interface: past packaging runs (from local history.json)."""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QHBoxLayout, QTreeWidgetItem, QVBoxLayout, QWidget
from qfluentwidgets import (
    CaptionLabel,
    FluentIcon,
    PushButton,
    TitleLabel,
    TreeWidget,
)

from ..core import persistence
from .theme import Tokens

_HEADERS = ["名称", "后端", "结果", "耗时(s)", "项目"]


class HistoryInterface(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("historyInterface")
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 18)
        root.setSpacing(14)
        root.addWidget(TitleLabel("打包历史"))
        hint = CaptionLabel("记录最近的打包任务（保存在本机 history.json）。")
        hint.setStyleSheet(f"color:{Tokens.INK_SUBTLE};")
        root.addWidget(hint)

        row = QHBoxLayout()
        self.btn_refresh = PushButton(FluentIcon.SYNC, "刷新")
        self.btn_clear = PushButton(FluentIcon.BROOM, "清空")
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_clear.clicked.connect(self._clear)
        row.addStretch(1)
        row.addWidget(self.btn_refresh)
        row.addWidget(self.btn_clear)
        root.addLayout(row)

        self.tree = TreeWidget()
        self.tree.setColumnCount(len(_HEADERS))
        self.tree.setHeaderLabels(_HEADERS)
        root.addWidget(self.tree, 1)

    def refresh(self) -> None:
        self.tree.clear()
        for entry in persistence.load_history():
            ok = "成功" if entry.get("success") else "失败"
            item = QTreeWidgetItem([
                str(entry.get("name", "")),
                str(entry.get("backend", "")),
                ok,
                str(entry.get("duration_sec", "")),
                str(entry.get("project", "")),
            ])
            self.tree.addTopLevelItem(item)
        for i in range(len(_HEADERS)):
            self.tree.resizeColumnToContents(i)

    def _clear(self) -> None:
        persistence._write_json(persistence._HISTORY_PATH, [])
        self.refresh()
