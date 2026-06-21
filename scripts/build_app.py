#!/usr/bin/env python
"""Build a portable, dependency-free PySmartPack distributable.

End users should NOT need Python. This script packages PySmartPack with
PyInstaller into either a portable folder (default, mpv-style -> zip) or a
single .exe, bundling the Qt/Fluent resources.

Usage (from repo root, inside the project venv):

    python scripts/build_app.py                 # portable folder + .zip (recommended)
    python scripts/build_app.py --onefile       # single huge .exe (slower start)
    python scripts/build_app.py --icon app.ico  # custom icon
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "app_main.py"
SRC = ROOT / "src"
DIST = ROOT / "dist"
BUILD = ROOT / "build"


def _force_utf8_stdio() -> None:
    """Tolerate non-GBK glyphs (e.g. ✔) on Windows consoles."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


# Heavy Qt modules a Widgets + Fluent app never uses. Excluding them shrinks the
# bundle dramatically (QtWebEngine alone is ~150 MB).
_QT_EXCLUDES = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.QtQml", "PySide6.QtQmlModels",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DInput", "PySide6.Qt3DLogic",
    "PySide6.Qt3DAnimation", "PySide6.Qt3DExtras",
    "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtSpatialAudio",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    "PySide6.QtSensors", "PySide6.QtSerialPort", "PySide6.QtPositioning",
    "PySide6.QtLocation", "PySide6.QtNfc", "PySide6.QtBluetooth",
    "PySide6.QtTextToSpeech", "PySide6.QtRemoteObjects", "PySide6.QtScxml",
    "PySide6.QtDesigner", "PySide6.QtUiTools", "PySide6.QtHelp", "PySide6.QtTest",
    "tkinter",
]


def build(args: argparse.Namespace) -> int:
    cmd = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--name", args.name,
        "--onefile" if args.onefile else "--onedir",
        "--console" if args.console else "--windowed",
        "--paths", str(SRC),
        # Fluent / frameless-window resources are package data PyInstaller can't
        # discover statically:
        "--collect-all", "qfluentwidgets",
        "--collect-all", "qframelesswindow",
        "--distpath", str(DIST),
        "--workpath", str(BUILD),
        "--specpath", str(BUILD),
    ]
    if args.icon:
        cmd += ["--icon", args.icon]
    if not args.fat:
        for mod in _QT_EXCLUDES:
            cmd += ["--exclude-module", mod]
    cmd.append(str(ENTRY))

    print("==> 构建命令:\n   " + " ".join(cmd) + "\n")
    code = subprocess.call(cmd)
    if code != 0:
        print(f"\n构建失败 (退出码 {code})", file=sys.stderr)
        return code

    if args.onefile:
        out = DIST / f"{args.name}.exe"
        print(f"\n✔ 单文件可执行: {out}")
        print("  直接分发这个 .exe 即可，最终用户无需安装 Python。")
    else:
        # macOS windowed onedir produces a .app bundle; prefer zipping that.
        app_bundle = DIST / f"{args.name}.app"
        if app_bundle.exists():
            base_dir, target = f"{args.name}.app", app_bundle
        else:
            base_dir, target = args.name, DIST / args.name
        zip_base = DIST / f"{args.name}_portable"
        print(f"\n✔ 便携产物: {target}")
        print("==> 正在打包为 zip ...")
        archive = shutil.make_archive(str(zip_base), "zip", root_dir=str(DIST),
                                      base_dir=base_dir)
        print(f"✔ 便携压缩包: {archive}")
        print("  把这个 .zip 发出去；用户解压后双击 "
              f"{base_dir} 即可运行，零依赖。")
    return 0


def main() -> int:
    _force_utf8_stdio()
    ap = argparse.ArgumentParser(description="构建便携版 PySmartPack")
    ap.add_argument("--onefile", action="store_true",
                    help="打包为单个 .exe（体积大、启动慢）；默认是便携文件夹 + zip")
    ap.add_argument("--console", action="store_true",
                    help="保留控制台窗口（默认隐藏，适合纯 GUI）")
    ap.add_argument("--name", default="PySmartPack")
    ap.add_argument("--icon", default=None, help="图标文件 (.ico / .icns)")
    ap.add_argument("--fat", action="store_true",
                    help="不排除任何 Qt 模块（体积更大，仅在瘦身导致缺模块时使用）")
    if not ENTRY.exists():
        print(f"找不到入口文件: {ENTRY}", file=sys.stderr)
        return 2
    return build(ap.parse_args())


if __name__ == "__main__":
    sys.exit(main())
