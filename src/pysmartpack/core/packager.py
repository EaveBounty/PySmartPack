"""Packaging executor: runs the chosen backend (PyInstaller / Nuitka) as a
subprocess, streams its output through callbacks, maps known log phases to a
progress percentage and supports cooperative cancellation.

The module is UI-agnostic: callers (CLI or the Qt worker thread) supply simple
callables. Nothing here imports Qt.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from . import config_generator
from .models import OutputMode, PackBackend, PackConfig, PackResult, Severity

LogCallback = Callable[[str, Severity], None]
ProgressCallback = Callable[[int], None]
CancelCheck = Callable[[], bool]

# (substring found in a log line, progress percent to jump to). Ordered.
_PYINSTALLER_PHASES: List[Tuple[str, int]] = [
    ("PyInstaller:", 5),
    ("Extending PYTHONPATH", 8),
    ("Analyzing", 20),
    ("Processing module hooks", 35),
    ("Looking for ", 45),
    ("Graph cross-reference", 55),
    ("Building PYZ", 65),
    ("Building PKG", 75),
    ("Building EXE", 85),
    ("Building COLLECT", 92),
    ("completed successfully", 100),
]
_NUITKA_PHASES: List[Tuple[str, int]] = [
    ("Starting Python", 5),
    ("Completed Python level compilation", 30),
    ("Running data composer", 45),
    ("Backend C", 60),
    ("Linking", 85),
    ("Successfully created", 100),
]


def _classify(line: str) -> Severity:
    low = line.lower()
    if "error" in low or "traceback" in low or "fatal" in low:
        return Severity.ERROR
    if "warning" in low or "warn:" in low:
        return Severity.WARNING
    return Severity.INFO


class Packager:
    def __init__(self, cfg: PackConfig) -> None:
        self.cfg = cfg
        self._proc: Optional[subprocess.Popen] = None

    # ------------------------------------------------------------- interpreter
    def resolve_runner(self, log: LogCallback) -> str:
        """Pick the Python interpreter to drive the backend.

        Prefers the project's own environment (so the backend sees the project's
        third-party dependencies). Falls back to the current interpreter with a
        clear warning if the backend module is not installed there.
        """
        module = "PyInstaller" if self.cfg.backend == PackBackend.PYINSTALLER else "nuitka"
        env_py = self.cfg.python_executable
        if env_py and Path(env_py).exists() and self._has_module(env_py, module):
            return env_py
        if env_py and Path(env_py).exists():
            log(f"项目环境的解释器未安装 {module}，回退到 PySmartPack 自带解释器；"
                f"项目的第三方依赖可能无法被发现。建议在项目环境执行: "
                f"{env_py} -m pip install {module.lower()}", Severity.WARNING)
        return sys.executable

    @staticmethod
    def _has_module(python_exe: str, module: str) -> bool:
        try:
            out = subprocess.run([python_exe, "-c", f"import {module}"],
                                 capture_output=True, timeout=15)
            return out.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    # ------------------------------------------------------------------- build
    def build_command(self, python_exe: str) -> List[str]:
        rendered = config_generator.render(self.cfg)
        args = rendered["args"]
        module = "PyInstaller" if self.cfg.backend == PackBackend.PYINSTALLER else "nuitka"
        return [python_exe, "-m", module, *args]

    def run(self, log: LogCallback, progress: ProgressCallback,
            should_cancel: Optional[CancelCheck] = None) -> PackResult:
        should_cancel = should_cancel or (lambda: False)
        start = time.time()

        python_exe = self.resolve_runner(log)
        cmd = self.build_command(python_exe)
        log("命令: " + " ".join(_quote(c) for c in cmd), Severity.INFO)

        phases = (_PYINSTALLER_PHASES if self.cfg.backend == PackBackend.PYINSTALLER
                  else _NUITKA_PHASES)
        phase_idx = 0
        progress(1)

        try:
            self._proc = subprocess.Popen(
                cmd, cwd=self.cfg.project_root,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, encoding="utf-8", errors="replace",
            )
        except (OSError, subprocess.SubprocessError) as exc:
            return PackResult(success=False, backend=self.cfg.backend,
                              duration_sec=time.time() - start,
                              message=f"无法启动打包进程: {exc}")

        assert self._proc.stdout is not None
        for raw in self._proc.stdout:
            line = raw.rstrip("\n")
            if not line:
                continue
            log(line, _classify(line))
            while phase_idx < len(phases) and phases[phase_idx][0] in line:
                progress(phases[phase_idx][1])
                phase_idx += 1
            if should_cancel():
                self.cancel(log)
                self._proc.wait()
                return PackResult(success=False, backend=self.cfg.backend,
                                  duration_sec=time.time() - start,
                                  message="已被用户取消")

        self._proc.wait()
        code = self._proc.returncode
        duration = time.time() - start

        if code == 0:
            progress(100)
            out_path = self.output_path()
            log(f"打包成功，耗时 {duration:.1f}s -> {out_path}", Severity.INFO)
            return PackResult(success=True, output_path=out_path,
                              backend=self.cfg.backend, duration_sec=duration,
                              return_code=0, message="成功")
        log(f"打包失败 (退出码 {code})", Severity.ERROR)
        return PackResult(success=False, backend=self.cfg.backend,
                          duration_sec=duration, return_code=code,
                          message=f"后端退出码 {code}")

    def cancel(self, log: Optional[LogCallback] = None) -> None:
        if self._proc and self._proc.poll() is None:
            if log:
                log("正在取消打包...", Severity.WARNING)
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()

    # ------------------------------------------------------------------ output
    def output_path(self) -> str:
        root = Path(self.cfg.project_root)
        dist = root / self.cfg.output_dir
        exe = self.cfg.app_name + (".exe" if sys.platform.startswith("win") else "")
        if self.cfg.output_mode == OutputMode.ONEFILE:
            return str(dist / exe)
        return str(dist / self.cfg.app_name / exe)


def _quote(token: str) -> str:
    return f'"{token}"' if " " in token else token


def verify_backend(python_exe: str, backend: PackBackend) -> bool:
    module = "PyInstaller" if backend == PackBackend.PYINSTALLER else "nuitka"
    return Packager._has_module(python_exe, module)
