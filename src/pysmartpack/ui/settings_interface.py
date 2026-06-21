"""Settings interface: LLM advisor configuration + appearance."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CardWidget,
    ComboBox,
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    PrimaryPushButton,
    StrongBodyLabel,
    SwitchButton,
    TitleLabel,
)

from ..core import persistence
from ..core.models import LLMConfig
from .theme import Tokens

_PROVIDERS = ["deepseek", "openai", "anthropic", "ollama"]


class SettingsInterface(QWidget):
    themeChanged = Signal(bool)  # True = dark

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("settingsInterface")
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 18)
        root.setSpacing(14)
        root.addWidget(TitleLabel("设置"))

        # --- LLM card ---
        llm_card = CardWidget()
        llm = QVBoxLayout(llm_card)
        llm.setContentsMargins(16, 14, 16, 14)
        llm.setSpacing(10)
        llm.addWidget(StrongBodyLabel("LLM 智能顾问（可选，默认关闭）"))
        note = CaptionLabel("开启后仅发送项目结构摘要（不含源码）用于生成打包建议；"
                            "关闭或失败时自动回退本地规则引擎。API Key 仅保存在本机。")
        note.setStyleSheet(f"color:{Tokens.INK_SUBTLE};")
        note.setWordWrap(True)
        llm.addWidget(note)

        enable_row = QHBoxLayout()
        enable_row.addWidget(BodyLabel("启用 LLM 顾问"))
        enable_row.addStretch(1)
        self.sw_enabled = SwitchButton()
        enable_row.addWidget(self.sw_enabled)
        llm.addLayout(enable_row)

        self.cmb_provider = ComboBox()
        self.cmb_provider.addItems(_PROVIDERS)
        llm.addLayout(self._field("提供方", self.cmb_provider))

        self.edit_model = LineEdit()
        self.edit_model.setPlaceholderText("deepseek-chat / deepseek-reasoner / gpt-4o-mini / llama3.1")
        llm.addLayout(self._field("模型", self.edit_model))

        self.edit_key = LineEdit()
        self.edit_key.setEchoMode(QLineEdit.Password)
        self.edit_key.setPlaceholderText("API Key（DeepSeek 在 platform.deepseek.com 获取；Ollama 本地可留空）")
        llm.addLayout(self._field("API Key", self.edit_key))

        self.edit_base = LineEdit()
        self.edit_base.setPlaceholderText("留空即用默认 · DeepSeek: https://api.deepseek.com · Ollama: http://localhost:11434")
        llm.addLayout(self._field("Base URL", self.edit_base))

        self.btn_save = PrimaryPushButton(FluentIcon.ACCEPT, "保存设置")
        self.btn_save.clicked.connect(self._save)
        save_row = QHBoxLayout()
        save_row.addStretch(1)
        save_row.addWidget(self.btn_save)
        llm.addLayout(save_row)
        root.addWidget(llm_card)

        # --- appearance card ---
        appear = CardWidget()
        ap = QVBoxLayout(appear)
        ap.setContentsMargins(16, 14, 16, 14)
        ap.setSpacing(10)
        ap.addWidget(StrongBodyLabel("外观"))
        theme_row = QHBoxLayout()
        theme_row.addWidget(BodyLabel("深色主题"))
        theme_row.addStretch(1)
        self.sw_dark = SwitchButton()
        self.sw_dark.setChecked(True)
        self.sw_dark.checkedChanged.connect(self._on_theme)
        theme_row.addWidget(self.sw_dark)
        ap.addLayout(theme_row)
        root.addWidget(appear)
        root.addStretch(1)

    def _field(self, label: str, widget: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        lab = BodyLabel(label)
        lab.setFixedWidth(96)
        row.addWidget(lab)
        row.addWidget(widget, 1)
        return row

    def _load(self) -> None:
        cfg = persistence.get_llm_config()
        self.sw_enabled.setChecked(cfg.enabled)
        if cfg.provider in _PROVIDERS:
            self.cmb_provider.setCurrentText(cfg.provider)
        self.edit_model.setText(cfg.model)
        self.edit_key.setText(cfg.api_key)
        self.edit_base.setText(cfg.base_url)
        settings = persistence.load_settings()
        self.sw_dark.setChecked(settings.get("theme", "dark") == "dark")

    def _save(self) -> None:
        cfg = LLMConfig(
            enabled=self.sw_enabled.isChecked(),
            provider=self.cmb_provider.currentText(),
            model=self.edit_model.text().strip(),
            api_key=self.edit_key.text().strip(),
            base_url=self.edit_base.text().strip(),
        )
        persistence.set_llm_config(cfg)
        settings = persistence.load_settings()
        settings["theme"] = "dark" if self.sw_dark.isChecked() else "light"
        persistence.save_settings(settings)
        InfoBar.success("已保存", "设置已写入本地配置文件。", duration=3000,
                        position=InfoBarPosition.TOP_RIGHT, parent=self)

    def _on_theme(self, checked: bool) -> None:
        self.themeChanged.emit(checked)
