"""Theme tokens (mapped from DESIGN.md) and application-level theming helpers."""
from __future__ import annotations

import html as _html

from PySide6.QtGui import QFont
from qfluentwidgets import Theme, setTheme, setThemeColor

from ..core.models import Severity


class Tokens:
    PRIMARY = "#5E6AD2"
    PRIMARY_HOVER = "#828FFF"
    PRIMARY_PRESSED = "#5E69D1"
    ON_PRIMARY = "#FFFFFF"

    CANVAS = "#0E0E11"
    SURFACE_1 = "#16171A"
    SURFACE_2 = "#1C1D21"
    SURFACE_3 = "#222329"
    HAIRLINE = "#2A2C32"
    HAIRLINE_STRONG = "#3A3B42"

    INK = "#F7F8F8"
    INK_MUTED = "#D0D6E0"
    INK_SUBTLE = "#8A8F98"
    INK_TERTIARY = "#62666D"

    SUCCESS = "#27A644"
    WARNING = "#E2A53B"
    DANGER = "#E5484D"

    UI_FONT = "Segoe UI"
    MONO_FONT = "Cascadia Code"


_LOG_COLORS = {
    Severity.INFO: Tokens.INK_MUTED,
    Severity.WARNING: Tokens.WARNING,
    Severity.ERROR: Tokens.DANGER,
}


def apply_theme(app, dark: bool = True) -> None:
    setTheme(Theme.DARK if dark else Theme.LIGHT)
    setThemeColor(Tokens.PRIMARY)
    font = QFont(Tokens.UI_FONT, 10)
    app.setFont(font)


def log_html(text: str, severity: Severity) -> str:
    color = _LOG_COLORS.get(severity, Tokens.INK_MUTED)
    safe = _html.escape(text)
    return (f'<span style="font-family:{Tokens.MONO_FONT},Consolas,monospace;'
            f'color:{color};">{safe}</span>')
