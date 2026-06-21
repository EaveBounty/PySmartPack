from pathlib import Path

from pysmartpack.core.llm import get_advice, rule_based_advice
from pysmartpack.core.models import (
    EnvInfo,
    EnvKind,
    ImportKind,
    ImportRef,
    LLMConfig,
    OutputMode,
    PackBackend,
    ScanResult,
)
from pysmartpack.core.scanner import scan_project


def _torch_scan() -> ScanResult:
    return ScanResult(
        root="x",
        imports=[ImportRef(name="torch", kind=ImportKind.THIRD_PARTY)],
        env=EnvInfo(kind=EnvKind.CONDA, source="pip list"),
    )


def test_rule_based_light_project(multi_package: Path):
    scan = scan_project(str(multi_package))
    advice = rule_based_advice(scan)
    assert advice.source == "rule"
    assert advice.recommended_backend == PackBackend.PYINSTALLER
    # no heavy libs -> onefile
    assert advice.recommended_output_mode == OutputMode.ONEFILE
    # dynamic import should surface a warning
    assert any("动态导入" in w for w in advice.hidden_import_warnings)


def test_rule_based_heavy_project():
    advice = rule_based_advice(_torch_scan())
    assert advice.recommended_output_mode == OutputMode.ONEDIR
    assert any("torch" in w for w in advice.hidden_import_warnings)


def test_get_advice_defaults_to_rule(multi_package: Path):
    scan = scan_project(str(multi_package))
    assert get_advice(scan, None).source == "rule"
    assert get_advice(scan, LLMConfig(enabled=False)).source == "rule"


def test_get_advice_llm_failure_falls_back():
    # enabled but unreachable endpoint -> graceful rule fallback
    cfg = LLMConfig(enabled=True, provider="openai", api_key="invalid",
                    base_url="http://127.0.0.1:9", timeout=2)
    advice = get_advice(_torch_scan(), cfg)
    assert advice.source.startswith("rule")
    assert advice.recommended_output_mode == OutputMode.ONEDIR
