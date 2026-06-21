"""Advisor: produces an :class:`Advice` from a scan result.

``get_advice`` is the single entry point. When the LLM is disabled or fails for
any reason, it returns deterministic rule-based advice grounded in
:mod:`pysmartpack.core.deps_db`.
"""
from __future__ import annotations

import json
import re
from typing import Optional

from .. import deps_db
from ..models import Advice, LLMConfig, OutputMode, PackBackend, ScanResult
from . import prompts
from .providers import LLMError, create_client

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def rule_based_advice(scan: ScanResult) -> Advice:
    third = scan.third_party_imports
    hint = deps_db.aggregate(third)

    output_mode = OutputMode.ONEDIR if hint.prefer_onedir else OutputMode.ONEFILE

    warnings = []
    if scan.dynamic_imports:
        names = sorted({d.name for d in scan.dynamic_imports})[:6]
        warnings.append(
            f"检测到动态导入 {names}：静态分析无法发现，已建议加入 hidden-import。")
    for name in third:
        h = deps_db.HINTS.get(name)
        if h and h.note:
            warnings.append(f"{name}: {h.note}")
    if scan.c_extensions:
        warnings.append(
            f"含 {len(scan.c_extensions)} 个原生扩展(.dll/.so/.pyd)，已并入二进制资源。")

    cats = scan.data_by_category()
    if cats:
        summary = ", ".join(f"{k}×{len(v)}" for k, v in cats.items())
        data_strategy = (f"识别到数据文件 [{summary}]，将通过 --add-data 一并打包；"
                         f"模型/大表数据建议使用 onedir 以加快启动。")
    else:
        data_strategy = "未发现需要额外打包的数据文件。"

    heavy = [n for n in third if n in deps_db.HEAVY]
    rationale_parts = []
    if heavy:
        rationale_parts.append(f"存在重型库 {heavy}，推荐 onedir 输出。")
    else:
        rationale_parts.append("依赖较轻，可用 onefile 获得单文件分发。")
    rationale_parts.append(
        f"虚拟环境类型: {scan.env.kind.value}，依赖来源: {scan.env.source or '未解析'}。")

    return Advice(
        recommended_backend=PackBackend.PYINSTALLER,
        recommended_output_mode=output_mode,
        suggested_hidden_imports=list(hint.hidden_imports),
        hidden_import_warnings=warnings,
        data_strategy=data_strategy,
        rationale=" ".join(rationale_parts),
        source="rule",
    )


def llm_advice(scan: ScanResult, cfg: LLMConfig) -> Advice:
    client = create_client(cfg)
    summary = prompts.scan_summary(scan)
    messages = prompts.build_messages(summary)
    raw = client.chat(messages)
    return _parse_advice(raw, cfg, fallback=rule_based_advice(scan))


def _parse_advice(raw: str, cfg: LLMConfig, fallback: Advice) -> Advice:
    match = _JSON_BLOCK.search(raw or "")
    if not match:
        raise LLMError("LLM 未返回 JSON")
    data = json.loads(match.group(0))

    def _backend(v: str) -> PackBackend:
        try:
            return PackBackend(v)
        except ValueError:
            return fallback.recommended_backend

    def _mode(v: str) -> OutputMode:
        try:
            return OutputMode(v)
        except ValueError:
            return fallback.recommended_output_mode

    return Advice(
        recommended_backend=_backend(str(data.get("recommended_backend", ""))),
        recommended_output_mode=_mode(str(data.get("recommended_output_mode", ""))),
        suggested_hidden_imports=list(data.get("suggested_hidden_imports", []))
        or fallback.suggested_hidden_imports,
        hidden_import_warnings=list(data.get("hidden_import_warnings", [])),
        data_strategy=str(data.get("data_strategy", "")) or fallback.data_strategy,
        rationale=str(data.get("rationale", "")),
        source=f"llm:{cfg.provider}",
    )


def get_advice(scan: ScanResult, cfg: Optional[LLMConfig] = None) -> Advice:
    """Single entry point. Falls back to rules when LLM is off or fails."""
    if cfg is None or not cfg.enabled:
        return rule_based_advice(scan)
    try:
        return llm_advice(scan, cfg)
    except (LLMError, json.JSONDecodeError, KeyError, ValueError):
        advice = rule_based_advice(scan)
        advice.rationale = "（LLM 不可用，已回退规则引擎）" + advice.rationale
        advice.source = "rule(fallback)"
        return advice
