"""Environment detector: identifies the virtual environment that owns a project
and extracts its dependency list.

Detection order (most specific first): explicit venv dir -> poetry -> pipenv ->
conda hints -> falls back to the running ("system") interpreter. Dependency
resolution prefers a live ``pip list`` against the detected interpreter (most
accurate) and falls back to parsing manifest files.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from .models import Dependency, EnvInfo, EnvKind

try:  # Python 3.11+
    import tomllib  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - 3.9/3.10 fallback
    try:
        import tomli as tomllib  # type: ignore
    except ModuleNotFoundError:  # pragma: no cover
        tomllib = None  # type: ignore

_VENV_DIR_NAMES = (".venv", "venv", "env", ".env")
_IS_WINDOWS = sys.platform.startswith("win")


def venv_python(venv_dir: Path) -> Optional[Path]:
    """Return the interpreter path inside a venv, cross-platform."""
    candidates = (
        [venv_dir / "Scripts" / "python.exe"] if _IS_WINDOWS
        else [venv_dir / "bin" / "python", venv_dir / "bin" / "python3"]
    )
    for c in candidates:
        if c.exists():
            return c
    return None


def find_venv(root: Path) -> Optional[Path]:
    for name in _VENV_DIR_NAMES:
        candidate = root / name
        if candidate.is_dir() and (candidate / "pyvenv.cfg").exists():
            return candidate
    return None


class EnvDetector:
    def __init__(self, root: str) -> None:
        self.root = Path(root).expanduser().resolve()

    def detect(self) -> EnvInfo:
        venv_dir = find_venv(self.root)
        if venv_dir is not None:
            return self._from_venv(venv_dir)

        kind = self._detect_manifest_kind()
        if kind == EnvKind.POETRY:
            info = self._try_poetry()
            if info is not None:
                return info
        # Fall back to system interpreter, but still try to read declared deps.
        return self._from_system(kind)

    # ------------------------------------------------------------- detection
    def _detect_manifest_kind(self) -> EnvKind:
        if (self.root / "poetry.lock").exists() or self._pyproject_has_poetry():
            return EnvKind.POETRY
        if (self.root / "Pipfile").exists():
            return EnvKind.PIPENV
        if (self.root / "environment.yml").exists() or (self.root / "conda-meta").is_dir():
            return EnvKind.CONDA
        return EnvKind.SYSTEM

    def _pyproject_has_poetry(self) -> bool:
        data = self._load_pyproject()
        return bool(data and data.get("tool", {}).get("poetry"))

    def _from_venv(self, venv_dir: Path) -> EnvInfo:
        py = venv_python(venv_dir)
        info = EnvInfo(
            kind=EnvKind.VENV,
            env_path=str(venv_dir),
            name=venv_dir.name,
            python_executable=str(py) if py else "",
        )
        self._populate_from_interpreter(info, py)
        return info

    def _try_poetry(self) -> Optional[EnvInfo]:
        try:
            out = subprocess.run(
                ["poetry", "env", "info", "--path"],
                cwd=str(self.root), capture_output=True, text=True, timeout=20,
            )
        except (FileNotFoundError, subprocess.SubprocessError):
            return None
        path = out.stdout.strip()
        if out.returncode != 0 or not path:
            return None
        env_dir = Path(path)
        py = venv_python(env_dir)
        info = EnvInfo(kind=EnvKind.POETRY, env_path=str(env_dir),
                       name=env_dir.name, python_executable=str(py) if py else "",
                       source="poetry env info")
        self._populate_from_interpreter(info, py)
        if not info.dependencies:
            info.dependencies = self._deps_from_pyproject_poetry()
            info.source = "pyproject.toml [tool.poetry]"
        return info

    def _from_system(self, kind: EnvKind) -> EnvInfo:
        py = Path(sys.executable)
        info = EnvInfo(
            kind=kind if kind != EnvKind.SYSTEM else EnvKind.SYSTEM,
            python_executable=str(py),
            name="system",
            env_path=str(py.parent),
        )
        self._populate_from_interpreter(info, py, prefer_manifest=True)
        return info

    # --------------------------------------------------------- dep resolution
    def _populate_from_interpreter(self, info: EnvInfo, py: Optional[Path],
                                   prefer_manifest: bool = False) -> None:
        if py and py.exists():
            info.python_version = self._python_version(py)
            info.site_packages = self._site_packages(py)
            if not prefer_manifest:
                deps = self._pip_list(py)
                if deps:
                    info.dependencies = deps
                    info.source = "pip list"
                    return
        # Manifest fallbacks.
        deps = (self._deps_from_requirements()
                or self._deps_from_pyproject_pep621()
                or self._deps_from_pyproject_poetry())
        if deps:
            info.dependencies = deps
            if not info.source:
                info.source = "manifest"

    @staticmethod
    def _python_version(py: Path) -> str:
        try:
            out = subprocess.run([str(py), "--version"], capture_output=True,
                                 text=True, timeout=10)
            return (out.stdout or out.stderr).strip().replace("Python ", "")
        except (FileNotFoundError, subprocess.SubprocessError):
            return ""

    @staticmethod
    def _site_packages(py: Path) -> List[str]:
        try:
            out = subprocess.run(
                [str(py), "-c", "import site,json;print(json.dumps(site.getsitepackages()))"],
                capture_output=True, text=True, timeout=15,
            )
            if out.returncode == 0:
                return list(json.loads(out.stdout.strip() or "[]"))
        except (FileNotFoundError, subprocess.SubprocessError, json.JSONDecodeError):
            pass
        return []

    @staticmethod
    def _pip_list(py: Path) -> List[Dependency]:
        try:
            out = subprocess.run(
                [str(py), "-m", "pip", "list", "--format=json", "--disable-pip-version-check"],
                capture_output=True, text=True, timeout=60,
            )
        except (FileNotFoundError, subprocess.SubprocessError):
            return []
        if out.returncode != 0:
            return []
        try:
            data = json.loads(out.stdout or "[]")
        except json.JSONDecodeError:
            return []
        return [Dependency(name=p.get("name", ""), version=p.get("version", "")) for p in data]

    def _deps_from_requirements(self) -> List[Dependency]:
        req = self.root / "requirements.txt"
        if not req.exists():
            return []
        deps: List[Dependency] = []
        for raw in req.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            name, version = self._split_requirement(line)
            if name:
                deps.append(Dependency(name=name, version=version))
        return deps

    def _deps_from_pyproject_pep621(self) -> List[Dependency]:
        data = self._load_pyproject()
        if not data:
            return []
        deps_list = data.get("project", {}).get("dependencies", [])
        out: List[Dependency] = []
        for item in deps_list:
            name, version = self._split_requirement(str(item))
            if name:
                out.append(Dependency(name=name, version=version))
        return out

    def _deps_from_pyproject_poetry(self) -> List[Dependency]:
        data = self._load_pyproject()
        if not data:
            return []
        table = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
        out: List[Dependency] = []
        for name, spec in table.items():
            if name.lower() == "python":
                continue
            version = spec if isinstance(spec, str) else ""
            out.append(Dependency(name=name, version=str(version)))
        return out

    def _load_pyproject(self) -> Optional[dict]:
        path = self.root / "pyproject.toml"
        if not path.exists() or tomllib is None:
            return None
        try:
            with path.open("rb") as fh:
                return tomllib.load(fh)
        except (OSError, ValueError):
            return None

    @staticmethod
    def _split_requirement(line: str) -> tuple[str, str]:
        line = line.split(";")[0].split("#")[0].strip()
        for sep in ("==", ">=", "<=", "~=", "!=", ">", "<", "==="):
            if sep in line:
                name, _, version = line.partition(sep)
                return name.strip(), (sep + version.strip())
        return line.strip(), ""


def detect_env(path: str) -> EnvInfo:
    """Convenience wrapper."""
    return EnvDetector(path).detect()
