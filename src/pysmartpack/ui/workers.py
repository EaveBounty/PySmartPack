"""Background worker threads so the UI never blocks on scanning, advising or
packaging. Core callables run off the GUI thread; results return via signals.
"""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from ..core import scanner
from ..core.env_detector import detect_env
from ..core.llm import get_advice
from ..core.models import LLMConfig, PackConfig, ScanResult, Severity
from ..core.packager import Packager


class ScanWorker(QThread):
    finished = Signal(object)   # ScanResult
    failed = Signal(str)

    def __init__(self, path: str) -> None:
        super().__init__()
        self._path = path

    def run(self) -> None:
        try:
            result: ScanResult = scanner.scan_project(self._path)
            result.env = detect_env(result.root)
            self.finished.emit(result)
        except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
            self.failed.emit(str(exc))


class AdviceWorker(QThread):
    finished = Signal(object)   # Advice

    def __init__(self, scan: ScanResult, llm_config: LLMConfig) -> None:
        super().__init__()
        self._scan = scan
        self._cfg = llm_config

    def run(self) -> None:
        advice = get_advice(self._scan, self._cfg)  # never raises
        self.finished.emit(advice)


class PackWorker(QThread):
    log = Signal(str, object)   # (line, Severity)
    progress = Signal(int)
    finished = Signal(object)   # PackResult

    def __init__(self, cfg: PackConfig) -> None:
        super().__init__()
        self._packager = Packager(cfg)
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True
        self._packager.cancel()

    def run(self) -> None:
        def on_log(line: str, sev: Severity) -> None:
            self.log.emit(line, sev)

        def on_progress(value: int) -> None:
            self.progress.emit(value)

        result = self._packager.run(on_log, on_progress, lambda: self._cancelled)
        self.finished.emit(result)
