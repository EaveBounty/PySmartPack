"""Headless command-line interface.

Enables scanning / packaging without the GUI (useful for CI and scripting):

    pysmartpack                      # launch the GUI
    pysmartpack scan <path>          # print scan summary as JSON
    pysmartpack pack <path> [opts]   # scan + package headlessly
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from . import __app_name__, __version__
from .core import config_generator
from .core.env_detector import detect_env
from .core.llm import get_advice
from .core.models import OutputMode, PackBackend, Severity
from .core.packager import Packager
from .core.scanner import scan_project


def _force_utf8_stdio() -> None:
    """Make stdout/stderr tolerant of non-GBK characters (Windows consoles)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pysmartpack",
                                     description=f"{__app_name__} - 智能 Python 打包器")
    parser.add_argument("--version", action="version",
                        version=f"{__app_name__} {__version__}")
    sub = parser.add_subparsers(dest="command")

    p_scan = sub.add_parser("scan", help="扫描项目并输出结构 JSON")
    p_scan.add_argument("path")
    p_scan.add_argument("--advice", action="store_true", help="附带规则引擎打包建议")

    p_pack = sub.add_parser("pack", help="扫描并打包")
    p_pack.add_argument("path")
    p_pack.add_argument("--name", default=None)
    p_pack.add_argument("--backend", choices=["pyinstaller", "nuitka"], default="pyinstaller")
    p_pack.add_argument("--onefile", dest="onefile", action="store_true")
    p_pack.add_argument("--onedir", dest="onedir", action="store_true")
    p_pack.add_argument("--no-console", action="store_true")
    p_pack.add_argument("--no-data", action="store_true", help="不打包数据文件")
    return parser


def cmd_scan(args: argparse.Namespace) -> int:
    scan = scan_project(args.path)
    scan.env = detect_env(scan.root)
    payload = scan.to_dict()
    if args.advice:
        payload["advice"] = get_advice(scan, None).to_dict()
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_pack(args: argparse.Namespace) -> int:
    scan = scan_project(args.path)
    scan.env = detect_env(scan.root)

    if not scan.entry_points:
        print("错误：未找到入口脚本。", file=sys.stderr)
        return 2

    mode: Optional[OutputMode] = None
    if args.onefile:
        mode = OutputMode.ONEFILE
    elif args.onedir:
        mode = OutputMode.ONEDIR

    cfg = config_generator.build_pack_config(
        scan,
        backend=PackBackend(args.backend),
        output_mode=mode,
        app_name=args.name,
        console=not args.no_console,
        include_data=not args.no_data,
    )

    def on_log(line: str, sev: Severity) -> None:
        prefix = {Severity.ERROR: "[ERR ]", Severity.WARNING: "[WARN]"}.get(sev, "[INFO]")
        print(f"{prefix} {line}")

    def on_progress(value: int) -> None:
        print(f"[ %3d%% ]" % value)

    result = Packager(cfg).run(on_log, on_progress)
    if result.success:
        print(f"\n✔ 成功: {result.output_path}  ({result.duration_sec:.1f}s)")
        return 0
    print(f"\n✘ 失败: {result.message}", file=sys.stderr)
    return 1


def main(argv: Optional[List[str]] = None) -> int:
    _force_utf8_stdio()
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "scan":
        return cmd_scan(args)
    if args.command == "pack":
        return cmd_pack(args)
    # No subcommand -> launch the GUI.
    from .ui.app import run
    return run()
