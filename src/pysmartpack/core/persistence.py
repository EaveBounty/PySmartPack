"""Settings & history persistence (JSON in a per-user config directory).

No database dependency: a single ``settings.json`` plus a capped ``history.json``
in the platform config dir. API keys are stored locally only and never logged.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

from .models import LLMConfig

_APP_DIR_NAME = "PySmartPack"
_MAX_HISTORY = 50


def config_dir() -> Path:
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    d = Path(base) / _APP_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


_SETTINGS_PATH = config_dir() / "settings.json"
_HISTORY_PATH = config_dir() / "history.json"

DEFAULT_SETTINGS: Dict[str, Any] = {
    "theme": "dark",
    "language": "zh",
    "recent_projects": [],
    "default_backend": "pyinstaller",
    "default_output_mode": "onefile",
    "llm": asdict(LLMConfig()),
}


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, data: Any) -> None:
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def load_settings() -> Dict[str, Any]:
    data = _read_json(_SETTINGS_PATH, {})
    merged = {**DEFAULT_SETTINGS, **(data if isinstance(data, dict) else {})}
    # ensure llm subtree complete
    merged["llm"] = {**DEFAULT_SETTINGS["llm"], **(merged.get("llm") or {})}
    return merged


def save_settings(settings: Dict[str, Any]) -> None:
    _write_json(_SETTINGS_PATH, settings)


def get_llm_config() -> LLMConfig:
    raw = load_settings().get("llm", {})
    valid = {k: v for k, v in raw.items() if k in LLMConfig.__dataclass_fields__}
    return LLMConfig(**valid)


def set_llm_config(cfg: LLMConfig) -> None:
    settings = load_settings()
    settings["llm"] = asdict(cfg)
    save_settings(settings)


def add_recent_project(path: str) -> None:
    settings = load_settings()
    recent: List[str] = [p for p in settings.get("recent_projects", []) if p != path]
    recent.insert(0, path)
    settings["recent_projects"] = recent[:10]
    save_settings(settings)


def load_history() -> List[Dict[str, Any]]:
    data = _read_json(_HISTORY_PATH, [])
    return data if isinstance(data, list) else []


def add_history(entry: Dict[str, Any]) -> None:
    history = load_history()
    history.insert(0, entry)
    _write_json(_HISTORY_PATH, history[:_MAX_HISTORY])
