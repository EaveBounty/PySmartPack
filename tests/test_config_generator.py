import ast
import os
from pathlib import Path

from pysmartpack.core.config_generator import (
    NuitkaGenerator,
    PyInstallerGenerator,
    build_pack_config,
    render,
)
from pysmartpack.core.models import OutputMode, PackBackend
from pysmartpack.core.scanner import scan_project


def test_build_pack_config(multi_package: Path):
    scan = scan_project(str(multi_package))
    cfg = build_pack_config(scan)
    assert cfg.entry_script.endswith("main.py")
    assert cfg.app_name == "main"
    # data files were turned into --add-data sources
    srcs = [s for s, _ in cfg.add_data]
    assert any(s.endswith("config.json") for s in srcs)
    assert any(s.endswith("sample.csv") for s in srcs)


def test_pyinstaller_cli_args(multi_package: Path):
    scan = scan_project(str(multi_package))
    cfg = build_pack_config(scan, output_mode=OutputMode.ONEFILE)
    args = PyInstallerGenerator.cli_args(cfg)
    assert "--onefile" in args
    assert "--name" in args and "main" in args
    assert args[-1] == cfg.entry_script
    add_data_vals = [args[i + 1] for i, a in enumerate(args) if a == "--add-data"]
    assert add_data_vals and all(os.pathsep in v for v in add_data_vals)


def test_pyinstaller_spec_is_valid_python(multi_package: Path):
    scan = scan_project(str(multi_package))
    cfg = build_pack_config(scan)
    spec = PyInstallerGenerator.spec_text(cfg)
    ast.parse(spec)  # raises SyntaxError if malformed
    assert "Analysis(" in spec and "PYZ(" in spec


def test_render_includes_args_and_spec(multi_package: Path):
    scan = scan_project(str(multi_package))
    cfg = build_pack_config(scan)
    out = render(cfg)
    assert out["args"] and isinstance(out["args"], list)
    assert "Analysis(" in out["spec"]


def test_nuitka_args(multi_package: Path):
    scan = scan_project(str(multi_package))
    cfg = build_pack_config(scan, backend=PackBackend.NUITKA,
                            output_mode=OutputMode.ONEFILE)
    args = NuitkaGenerator.cli_args(cfg)
    assert "--onefile" in args
    assert args[-1] == cfg.entry_script
