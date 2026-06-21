"""Project scanner: statically analyses a Python project / single file.

Pure standard-library implementation (``ast`` + ``pathlib``). It never imports
or executes the target code, so it is safe to run on untrusted projects.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Set

from .models import (
    DataFile,
    Diagnostic,
    EntryPoint,
    FileCategory,
    ImportKind,
    ImportRef,
    ScanResult,
    Severity,
)

# Directories that should never be treated as project source.
SKIP_DIRS: Set[str] = {
    ".venv", "venv", "env", ".env", "__pycache__", ".git", ".hg", ".svn",
    "node_modules", "build", "dist", ".idea", ".vscode", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "site-packages", ".tox", ".eggs",
    "conda-meta", ".conda",
}

# Extension -> category mapping for data-file detection.
_EXT_CATEGORY = {
    # tables
    ".csv": FileCategory.DATA_TABLE, ".tsv": FileCategory.DATA_TABLE,
    ".xlsx": FileCategory.DATA_TABLE, ".xls": FileCategory.DATA_TABLE,
    ".parquet": FileCategory.DATA_TABLE, ".feather": FileCategory.DATA_TABLE,
    # models / arrays
    ".npz": FileCategory.DATA_MODEL, ".npy": FileCategory.DATA_MODEL,
    ".pkl": FileCategory.DATA_MODEL, ".pickle": FileCategory.DATA_MODEL,
    ".pt": FileCategory.DATA_MODEL, ".pth": FileCategory.DATA_MODEL,
    ".onnx": FileCategory.DATA_MODEL, ".h5": FileCategory.DATA_MODEL,
    ".joblib": FileCategory.DATA_MODEL, ".safetensors": FileCategory.DATA_MODEL,
    ".pb": FileCategory.DATA_MODEL, ".tflite": FileCategory.DATA_MODEL,
    # config
    ".json": FileCategory.DATA_CONFIG, ".yaml": FileCategory.DATA_CONFIG,
    ".yml": FileCategory.DATA_CONFIG, ".toml": FileCategory.DATA_CONFIG,
    ".ini": FileCategory.DATA_CONFIG, ".cfg": FileCategory.DATA_CONFIG,
    ".env": FileCategory.DATA_CONFIG,
    # docs
    ".md": FileCategory.DATA_DOC, ".txt": FileCategory.DATA_DOC,
    ".rst": FileCategory.DATA_DOC, ".html": FileCategory.DATA_DOC,
    # media / assets
    ".png": FileCategory.DATA_MEDIA, ".jpg": FileCategory.DATA_MEDIA,
    ".jpeg": FileCategory.DATA_MEDIA, ".gif": FileCategory.DATA_MEDIA,
    ".svg": FileCategory.DATA_MEDIA, ".ico": FileCategory.DATA_MEDIA,
    ".bmp": FileCategory.DATA_MEDIA, ".webp": FileCategory.DATA_MEDIA,
    ".ttf": FileCategory.DATA_MEDIA, ".otf": FileCategory.DATA_MEDIA,
    ".wav": FileCategory.DATA_MEDIA, ".mp3": FileCategory.DATA_MEDIA,
    ".mp4": FileCategory.DATA_MEDIA, ".qss": FileCategory.DATA_MEDIA,
    # databases
    ".db": FileCategory.DATA_DB, ".sqlite": FileCategory.DATA_DB,
    ".sqlite3": FileCategory.DATA_DB,
    # native binaries
    ".dll": FileCategory.BINARY, ".so": FileCategory.BINARY,
    ".dylib": FileCategory.BINARY, ".pyd": FileCategory.BINARY,
}

# Files that are config/metadata, never user data we should bundle.
_CONFIG_IGNORE = {
    "pyproject.toml", "setup.cfg", "tox.ini", "requirements.txt", "poetry.lock",
    "pipfile", "pipfile.lock", ".gitignore", "readme.md", "license", "license.txt",
}

_ENTRY_NAME_BONUS = {
    "__main__.py": 4, "main.py": 4, "app.py": 3, "run.py": 3,
    "cli.py": 3, "gui.py": 2, "start.py": 2, "manage.py": 2, "__init__.py": -3,
}


def _stdlib_modules() -> Set[str]:
    names = getattr(sys, "stdlib_module_names", None)
    if names:
        return set(names)
    # Fallback for Python 3.9 (sys.stdlib_module_names added in 3.10).
    return {
        "abc", "argparse", "ast", "asyncio", "base64", "collections", "configparser",
        "contextlib", "copy", "csv", "datetime", "decimal", "enum", "functools",
        "glob", "hashlib", "http", "importlib", "inspect", "io", "itertools", "json",
        "logging", "math", "multiprocessing", "os", "pathlib", "pickle", "platform",
        "queue", "random", "re", "shutil", "socket", "sqlite3", "ssl", "string",
        "struct", "subprocess", "sys", "tempfile", "threading", "time", "traceback",
        "typing", "unittest", "urllib", "uuid", "warnings", "xml", "zipfile",
    }


_STDLIB = _stdlib_modules()
_DYNAMIC_IMPORT_CALLS = {"__import__", "import_module"}


class ProjectScanner:
    """Scan a directory (or a single ``.py`` file) into a :class:`ScanResult`."""

    def __init__(self, root: str) -> None:
        self.root = Path(root).expanduser().resolve()

    # ------------------------------------------------------------------ public
    def scan(self) -> ScanResult:
        if not self.root.exists():
            raise FileNotFoundError(f"Path does not exist: {self.root}")

        if self.root.is_file():
            return self._scan_single_file(self.root)
        return self._scan_directory(self.root)

    # --------------------------------------------------------------- internals
    def _scan_single_file(self, file: Path) -> ScanResult:
        result = ScanResult(root=str(file.parent), is_single_file=True)
        local_names = {file.stem}
        self._analyse_py(file, local_names, result)
        if not result.entry_points:
            result.entry_points.append(
                EntryPoint(path=str(file), has_main_guard=False, score=1,
                           reason="single file")
            )
        result.modules.append(str(file))
        return result

    def _scan_directory(self, root: Path) -> ScanResult:
        result = ScanResult(root=str(root), is_single_file=False)

        py_files: List[Path] = []
        for path in self._walk(root):
            if path.is_dir():
                if (path / "__init__.py").exists():
                    result.packages.append(str(path))
                continue
            suffix = path.suffix.lower()
            if suffix == ".py":
                py_files.append(path)
                result.modules.append(str(path))
            elif suffix in _EXT_CATEGORY:
                self._maybe_add_data(path, result)

        local_names = self._local_top_level_names(root, py_files)

        for py in py_files:
            self._analyse_py(py, local_names, result)

        self._score_entry_points(root, result)
        self._emit_diagnostics(result)
        return result

    def _walk(self, root: Path) -> Iterable[Path]:
        """Yield every file and directory under root, pruning SKIP_DIRS."""
        stack = [root]
        while stack:
            current = stack.pop()
            try:
                children = list(current.iterdir())
            except (PermissionError, OSError):
                continue
            for child in children:
                if child.is_dir():
                    if child.name in SKIP_DIRS or child.name.startswith("."):
                        if child.name not in {".github"}:  # allow a couple of dotdirs
                            continue
                    yield child
                    stack.append(child)
                else:
                    yield child

    def _local_top_level_names(self, root: Path, py_files: List[Path]) -> Set[str]:
        names: Set[str] = set()
        for child in root.iterdir():
            if child.is_dir() and (child / "__init__.py").exists():
                names.add(child.name)
            elif child.suffix.lower() == ".py":
                names.add(child.stem)
        # also: a "src/<pkg>" layout
        src = root / "src"
        if src.is_dir():
            for child in src.iterdir():
                if child.is_dir() and (child / "__init__.py").exists():
                    names.add(child.name)
        for py in py_files:
            names.add(py.stem)
        return names

    def _maybe_add_data(self, path: Path, result: ScanResult) -> None:
        category = _EXT_CATEGORY.get(path.suffix.lower(), FileCategory.OTHER)
        if path.name.lower() in _CONFIG_IGNORE:
            return
        if category == FileCategory.BINARY:
            result.c_extensions.append(str(path))
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        result.data_files.append(DataFile(path=str(path), category=category, size_bytes=size))

    def _analyse_py(self, file: Path, local_names: Set[str], result: ScanResult) -> None:
        try:
            source = file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                source = file.read_text(encoding="latin-1")
            except OSError:
                return
        except OSError:
            return

        try:
            tree = ast.parse(source, filename=str(file))
        except SyntaxError as exc:
            result.diagnostics.append(
                Diagnostic(Severity.WARNING,
                           f"语法错误，已跳过 import 分析: {file.name} (行 {exc.lineno})",
                           "该文件无法静态解析，打包时请确认其依赖已手动补充。")
            )
            return

        has_main_guard = self._has_main_guard(tree)
        if has_main_guard:
            result.entry_points.append(
                EntryPoint(path=str(file), has_main_guard=True, score=0,
                           reason='含 if __name__ == "__main__"')
            )

        for node in ast.walk(tree):
            self._collect_import(node, file, local_names, result)
            self._collect_dynamic_import(node, file, result)

    @staticmethod
    def _has_main_guard(tree: ast.AST) -> bool:
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                test = node.test
                if (isinstance(test, ast.Compare)
                        and isinstance(test.left, ast.Name)
                        and test.left.id == "__name__"):
                    for cmp in test.comparators:
                        if isinstance(cmp, ast.Constant) and cmp.value == "__main__":
                            return True
        return False

    def _collect_import(self, node: ast.AST, file: Path, local_names: Set[str],
                        result: ScanResult) -> None:
        top_names: List[str] = []
        is_relative = False
        if isinstance(node, ast.Import):
            top_names = [alias.name.split(".")[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                is_relative = True
            elif node.module:
                top_names = [node.module.split(".")[0]]
        else:
            return

        line = getattr(node, "lineno", 0)
        loc = f"{file.name}:{line}"
        if is_relative:
            result.imports.append(ImportRef(name="(relative)", kind=ImportKind.LOCAL,
                                            location=loc))
            return
        for name in top_names:
            if not name:
                continue
            kind = self._classify(name, local_names)
            if not any(i.name == name and i.kind == kind for i in result.imports):
                result.imports.append(ImportRef(name=name, kind=kind, location=loc))

    @staticmethod
    def _classify(name: str, local_names: Set[str]) -> ImportKind:
        if name in local_names:
            return ImportKind.LOCAL
        if name in _STDLIB:
            return ImportKind.STDLIB
        return ImportKind.THIRD_PARTY

    def _collect_dynamic_import(self, node: ast.AST, file: Path, result: ScanResult) -> None:
        if not isinstance(node, ast.Call):
            return
        func = node.func
        fname = None
        if isinstance(func, ast.Name):
            fname = func.id
        elif isinstance(func, ast.Attribute):
            fname = func.attr
        if fname in _DYNAMIC_IMPORT_CALLS:
            line = getattr(node, "lineno", 0)
            target = ""
            if node.args and isinstance(node.args[0], ast.Constant):
                target = str(node.args[0].value)
            result.dynamic_imports.append(
                ImportRef(name=target or fname, kind=ImportKind.THIRD_PARTY,
                          is_dynamic=True, location=f"{file.name}:{line}")
            )

    def _score_entry_points(self, root: Path, result: ScanResult) -> None:
        for ep in result.entry_points:
            p = Path(ep.path)
            score = 5 if ep.has_main_guard else 0
            score += _ENTRY_NAME_BONUS.get(p.name.lower(), 0)
            try:
                depth = len(p.relative_to(root).parts) - 1
            except ValueError:
                depth = 0
            score -= depth  # prefer shallow scripts
            ep.score = score
        result.entry_points.sort(key=lambda e: e.score, reverse=True)

    def _emit_diagnostics(self, result: ScanResult) -> None:
        if not result.entry_points:
            result.diagnostics.append(
                Diagnostic(Severity.ERROR, "未找到入口脚本",
                           '没有发现含 if __name__ == "__main__" 的文件，请手动指定入口。')
            )
        if result.dynamic_imports:
            names = ", ".join(sorted({d.name for d in result.dynamic_imports})[:8])
            result.diagnostics.append(
                Diagnostic(Severity.WARNING,
                           f"检测到动态导入（{len(result.dynamic_imports)} 处）: {names}",
                           "PyInstaller 无法静态发现这些模块，可能需加入 --hidden-import。")
            )
        if result.c_extensions:
            result.diagnostics.append(
                Diagnostic(Severity.INFO,
                           f"检测到 {len(result.c_extensions)} 个原生扩展 (.dll/.so/.pyd)",
                           "将作为二进制资源一并打包；CUDA/MKL 等大型库请确认体积。")
            )


def scan_project(path: str) -> ScanResult:
    """Convenience wrapper."""
    return ProjectScanner(path).scan()
