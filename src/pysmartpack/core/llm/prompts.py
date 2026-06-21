"""Prompt templates for the LLM advisor (kept separate from logic)."""
from __future__ import annotations

import json
from typing import Any, Dict

SYSTEM_PROMPT = (
    "You are a senior Python packaging engineer. Given a static scan of a Python "
    "project, recommend an optimal PyInstaller/Nuitka packaging strategy. "
    "You MUST reply with a single JSON object and nothing else, using exactly "
    "these keys: recommended_backend ('pyinstaller'|'nuitka'), "
    "recommended_output_mode ('onefile'|'onedir'), "
    "suggested_hidden_imports (string[]), hidden_import_warnings (string[]), "
    "data_strategy (string), rationale (string). "
    "Be conservative; prefer pyinstaller + onedir for projects with heavy native "
    "libraries (torch, tensorflow, opencv, scipy). Never invent packages that are "
    "not implied by the scan."
)

_FEW_SHOT_USER = {
    "third_party_imports": ["numpy", "pandas", "torch"],
    "dynamic_imports": ["plugins.loader"],
    "data_files": {"model": ["weights.pth"], "table": ["data.csv"]},
    "env": {"kind": "conda", "name": "ml"},
}
_FEW_SHOT_ASSISTANT = {
    "recommended_backend": "pyinstaller",
    "recommended_output_mode": "onedir",
    "suggested_hidden_imports": ["plugins.loader"],
    "hidden_import_warnings": [
        "torch carries large CUDA DLLs; use --collect-all torch.",
        "Dynamic import 'plugins.loader' is invisible to static analysis.",
    ],
    "data_strategy": "Bundle weights.pth and data.csv via --add-data; keep onedir to avoid slow onefile extraction of large model weights.",
    "rationale": "Heavy native stack (torch) favours onedir; conda env detected so resolve deps from that interpreter.",
}


def build_messages(scan_summary: Dict[str, Any]) -> list:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(_FEW_SHOT_USER, ensure_ascii=False)},
        {"role": "assistant", "content": json.dumps(_FEW_SHOT_ASSISTANT, ensure_ascii=False)},
        {"role": "user", "content": json.dumps(scan_summary, ensure_ascii=False)},
    ]


def scan_summary(scan) -> Dict[str, Any]:  # type: ignore[no-untyped-def]
    """Compact, privacy-conscious summary sent to the LLM (no source code)."""
    return {
        "is_single_file": scan.is_single_file,
        "entry_points": [e.path.split("/")[-1].split("\\")[-1] for e in scan.entry_points[:5]],
        "third_party_imports": scan.third_party_imports,
        "dynamic_imports": sorted({d.name for d in scan.dynamic_imports}),
        "data_files": {k: len(v) for k, v in scan.data_by_category().items()},
        "has_c_extensions": bool(scan.c_extensions),
        "env": {"kind": scan.env.kind.value, "python": scan.env.python_version},
    }
