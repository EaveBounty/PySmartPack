"""Domain models shared across the core and UI layers.

All models are plain dataclasses (no Pydantic dependency) and are JSON-friendly
via :func:`to_dict`. ``from __future__ import annotations`` keeps the module
importable on Python 3.9+.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class FileCategory(str, Enum):
    """Classification of a non-source file discovered in the project."""

    DATA_TABLE = "table"        # .csv .tsv .xlsx .xls .parquet .feather
    DATA_MODEL = "model"        # .npz .npy .pkl .pt .pth .onnx .h5 .joblib .safetensors
    DATA_CONFIG = "config"      # .json .yaml .yml .toml .ini .cfg .env
    DATA_DOC = "doc"            # .md .txt .rst .html
    DATA_MEDIA = "media"        # images / audio / video / fonts
    DATA_DB = "db"              # .db .sqlite .sqlite3
    BINARY = "binary"           # .dll .so .dylib .pyd
    OTHER = "other"


class ImportKind(str, Enum):
    STDLIB = "stdlib"
    THIRD_PARTY = "third_party"
    LOCAL = "local"


class EnvKind(str, Enum):
    VENV = "venv"
    CONDA = "conda"
    POETRY = "poetry"
    PIPENV = "pipenv"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class PackBackend(str, Enum):
    PYINSTALLER = "pyinstaller"
    NUITKA = "nuitka"


class OutputMode(str, Enum):
    ONEFILE = "onefile"
    ONEDIR = "onedir"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class Diagnostic:
    """A user-facing note surfaced during scanning."""

    severity: Severity
    message: str
    hint: str = ""


@dataclass
class EntryPoint:
    """A candidate executable entry script."""

    path: str
    has_main_guard: bool = False
    score: int = 0  # higher == more likely the real entry point
    reason: str = ""


@dataclass
class DataFile:
    path: str
    category: FileCategory
    size_bytes: int = 0
    selected: bool = True  # user can toggle in the UI


@dataclass
class ImportRef:
    name: str
    kind: ImportKind
    is_dynamic: bool = False
    location: str = ""  # "file.py:line"


@dataclass
class Dependency:
    name: str
    version: str = ""


@dataclass
class EnvInfo:
    kind: EnvKind = EnvKind.UNKNOWN
    python_executable: str = ""
    python_version: str = ""
    env_path: str = ""
    name: str = ""
    site_packages: List[str] = field(default_factory=list)
    dependencies: List[Dependency] = field(default_factory=list)
    source: str = ""  # how deps were resolved (e.g. "requirements.txt", "pip list")


@dataclass
class ScanResult:
    """The structured output of :class:`pysmartpack.core.scanner.ProjectScanner`."""

    root: str
    is_single_file: bool = False
    entry_points: List[EntryPoint] = field(default_factory=list)
    packages: List[str] = field(default_factory=list)
    modules: List[str] = field(default_factory=list)
    data_files: List[DataFile] = field(default_factory=list)
    imports: List[ImportRef] = field(default_factory=list)
    dynamic_imports: List[ImportRef] = field(default_factory=list)
    c_extensions: List[str] = field(default_factory=list)
    env: EnvInfo = field(default_factory=EnvInfo)
    diagnostics: List[Diagnostic] = field(default_factory=list)

    # --- convenience views -------------------------------------------------
    @property
    def third_party_imports(self) -> List[str]:
        seen: List[str] = []
        for i in self.imports:
            if i.kind == ImportKind.THIRD_PARTY and i.name not in seen:
                seen.append(i.name)
        return sorted(seen)

    @property
    def best_entry_point(self) -> Optional[EntryPoint]:
        if not self.entry_points:
            return None
        return max(self.entry_points, key=lambda e: e.score)

    def data_by_category(self) -> Dict[str, List[DataFile]]:
        out: Dict[str, List[DataFile]] = {}
        for d in self.data_files:
            out.setdefault(d.category.value, []).append(d)
        return out

    def to_dict(self) -> Dict[str, Any]:
        return _to_dict(self)


@dataclass
class PackConfig:
    """A fully-resolved packaging job ready to hand to a backend."""

    project_root: str
    entry_script: str
    backend: PackBackend = PackBackend.PYINSTALLER
    output_mode: OutputMode = OutputMode.ONEDIR
    app_name: str = "app"
    output_dir: str = "dist"
    work_dir: str = "build"

    # "把所有库一起打包" vs "先编译之后再打包"
    bundle_all: bool = True       # bundle every dependency
    compile_first: bool = False   # prefer compilation (Nuitka / bytecode) before bundling

    console: bool = True
    icon: Optional[str] = None
    clean: bool = True
    upx: bool = False

    add_data: List[Tuple[str, str]] = field(default_factory=list)   # (src, dest_in_bundle)
    add_binary: List[Tuple[str, str]] = field(default_factory=list)
    hidden_imports: List[str] = field(default_factory=list)
    excludes: List[str] = field(default_factory=list)
    collect_all: List[str] = field(default_factory=list)
    collect_data: List[str] = field(default_factory=list)
    collect_submodules: List[str] = field(default_factory=list)
    extra_args: List[str] = field(default_factory=list)

    python_executable: str = ""  # interpreter that owns the deps (from EnvInfo)

    def to_dict(self) -> Dict[str, Any]:
        return _to_dict(self)


@dataclass
class LLMConfig:
    enabled: bool = False                  # OFF by default (privacy-first)
    provider: str = "deepseek"             # deepseek | openai | anthropic | ollama
    model: str = "deepseek-chat"           # DeepSeek-V3; use "deepseek-reasoner" for R1
    api_key: str = ""
    base_url: str = ""                     # blank -> provider default endpoint
    temperature: float = 0.2
    timeout: int = 60

    def redacted(self) -> Dict[str, Any]:
        d = _to_dict(self)
        if d.get("api_key"):
            d["api_key"] = "***"
        return d


@dataclass
class Advice:
    """Structured recommendation produced by the LLM advisor (or rule fallback)."""

    recommended_backend: PackBackend = PackBackend.PYINSTALLER
    recommended_output_mode: OutputMode = OutputMode.ONEDIR
    hidden_import_warnings: List[str] = field(default_factory=list)
    suggested_hidden_imports: List[str] = field(default_factory=list)
    data_strategy: str = ""
    spec_snippet: str = ""
    rationale: str = ""
    source: str = "rule"  # "rule" | "llm:<provider>"

    def to_dict(self) -> Dict[str, Any]:
        return _to_dict(self)


@dataclass
class PackResult:
    success: bool
    output_path: str = ""
    backend: PackBackend = PackBackend.PYINSTALLER
    duration_sec: float = 0.0
    return_code: int = 0
    message: str = ""


def _to_dict(obj: Any) -> Dict[str, Any]:
    """asdict that turns Enums into their values for clean JSON."""

    def _convert(value: Any) -> Any:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dict):
            return {k: _convert(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [_convert(v) for v in value]
        return value

    return {k: _convert(v) for k, v in asdict(obj).items()}
