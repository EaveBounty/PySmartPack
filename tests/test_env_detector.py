import sys
from pathlib import Path

from pysmartpack.core.env_detector import (
    EnvDetector,
    detect_env,
    find_venv,
    venv_python,
)
from pysmartpack.core.models import EnvKind


def test_split_requirement():
    assert EnvDetector._split_requirement("numpy==1.26.0") == ("numpy", "==1.26.0")
    assert EnvDetector._split_requirement("requests>=2.0") == ("requests", ">=2.0")
    assert EnvDetector._split_requirement("flask") == ("flask", "")
    assert EnvDetector._split_requirement("pandas ; python_version>'3.8'") == ("pandas", "")


def test_find_venv(tmp_path: Path):
    assert find_venv(tmp_path) is None
    venv = tmp_path / ".venv"
    venv.mkdir()
    (venv / "pyvenv.cfg").write_text("home = x\n", encoding="utf-8")
    found = find_venv(tmp_path)
    assert found is not None and found.name == ".venv"


def test_venv_python_layout(tmp_path: Path):
    venv = tmp_path / ".venv"
    if sys.platform.startswith("win"):
        exe = venv / "Scripts" / "python.exe"
    else:
        exe = venv / "bin" / "python"
    exe.parent.mkdir(parents=True)
    exe.write_text("", encoding="utf-8")
    assert venv_python(venv) == exe


def test_detect_system_fallback(multi_package: Path):
    info = detect_env(str(multi_package))
    assert info.kind in {EnvKind.SYSTEM, EnvKind.VENV}
    assert info.python_executable
