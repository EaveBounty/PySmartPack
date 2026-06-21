"""Knowledge base of common third-party packages and their packaging quirks.

PyInstaller's static analysis misses data files, dynamically-imported submodules
and some native backends for a well-known set of libraries. This table encodes
the community-known fixes so the config generator and the rule-based advisor can
apply them automatically (and the LLM advisor can use them as grounding).

Keys are **top-level import names** (what you ``import``), not PyPI dist names.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class PackHint:
    hidden_imports: List[str] = field(default_factory=list)
    collect_all: List[str] = field(default_factory=list)        # --collect-all
    collect_data: List[str] = field(default_factory=list)       # --collect-data
    collect_submodules: List[str] = field(default_factory=list)  # --collect-submodules
    excludes: List[str] = field(default_factory=list)
    prefer_onedir: bool = False  # large/native libs are happier as one-dir
    note: str = ""


# Curated, conservative set. Extend freely.
HINTS: Dict[str, PackHint] = {
    "numpy": PackHint(prefer_onedir=True, note="大型 C 扩展，onefile 启动较慢。"),
    "pandas": PackHint(hidden_imports=["pandas._libs.tslibs.timedeltas"],
                       prefer_onedir=True),
    "scipy": PackHint(collect_submodules=["scipy"], prefer_onedir=True,
                      note="scipy 子模块需 --collect-submodules。"),
    "sklearn": PackHint(collect_submodules=["sklearn"],
                        hidden_imports=["sklearn.utils._typedefs",
                                        "sklearn.neighbors._partition_nodes"]),
    "matplotlib": PackHint(collect_data=["matplotlib"],
                           hidden_imports=["matplotlib.backends.backend_qtagg"],
                           note="字体/样式为数据文件，需 --collect-data。"),
    "PIL": PackHint(hidden_imports=["PIL._tkinter_finder"]),
    "cv2": PackHint(collect_all=["cv2"], prefer_onedir=True,
                    note="opencv 含原生 dll，建议 --collect-all。"),
    "torch": PackHint(collect_all=["torch"], prefer_onedir=True,
                      note="PyTorch 体积巨大且含 CUDA dll，强烈建议 onedir + --collect-all。"),
    "tensorflow": PackHint(collect_all=["tensorflow"], prefer_onedir=True),
    "transformers": PackHint(collect_data=["transformers"], collect_submodules=["transformers"]),
    "scipy.special": PackHint(collect_submodules=["scipy.special"]),
    "win32com": PackHint(hidden_imports=["win32com", "pythoncom", "pywintypes"],
                         note="pywin32 需显式 hidden-import。"),
    "cryptography": PackHint(collect_submodules=["cryptography"]),
    "lxml": PackHint(hidden_imports=["lxml._elementpath"]),
    "jinja2": PackHint(collect_data=["jinja2"]),
    "flask": PackHint(collect_submodules=["flask"]),
    "django": PackHint(collect_all=["django"], prefer_onedir=True),
    "sqlalchemy": PackHint(collect_submodules=["sqlalchemy"]),
    "pydantic": PackHint(collect_submodules=["pydantic"]),
    "pkg_resources": PackHint(hidden_imports=["pkg_resources.py2_warn"]),
    "qfluentwidgets": PackHint(collect_all=["qfluentwidgets"],
                               note="qfluentwidgets 图标/qss/字体为数据文件，需 --collect-all。"),
    "qframelesswindow": PackHint(collect_all=["qframelesswindow"],
                                 note="qfluentwidgets 的依赖，无边框窗口资源需 --collect-all。"),
    "openai": PackHint(collect_submodules=["openai"]),
    "anthropic": PackHint(collect_submodules=["anthropic"]),
}

# Top-level names that are big enough to nudge the user toward one-dir output.
HEAVY = {"torch", "tensorflow", "cv2", "scipy", "numpy", "pandas", "django"}


def hints_for(imports: List[str]) -> List[tuple[str, PackHint]]:
    """Return ``(name, hint)`` pairs for any known imports present."""
    return [(name, HINTS[name]) for name in imports if name in HINTS]


def aggregate(imports: List[str]) -> PackHint:
    """Merge all matching hints into a single :class:`PackHint`."""
    merged = PackHint()
    for _, hint in hints_for(imports):
        merged.hidden_imports += [h for h in hint.hidden_imports
                                  if h not in merged.hidden_imports]
        merged.collect_all += [c for c in hint.collect_all if c not in merged.collect_all]
        merged.collect_data += [c for c in hint.collect_data if c not in merged.collect_data]
        merged.collect_submodules += [c for c in hint.collect_submodules
                                      if c not in merged.collect_submodules]
        merged.excludes += [e for e in hint.excludes if e not in merged.excludes]
        merged.prefer_onedir = merged.prefer_onedir or hint.prefer_onedir
    return merged
