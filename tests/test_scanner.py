from pathlib import Path

from pysmartpack.core.models import FileCategory, ImportKind
from pysmartpack.core.scanner import scan_project


def test_single_file(single_file: Path):
    result = scan_project(str(single_file))
    assert result.is_single_file is True
    assert result.entry_points, "expected an entry point"
    best = result.best_entry_point
    assert best is not None and best.path.endswith("hello.py")
    assert best.has_main_guard is True
    names = {i.name for i in result.imports}
    assert {"argparse", "json", "datetime"} & names


def test_multi_package_structure(multi_package: Path):
    result = scan_project(str(multi_package))
    assert result.is_single_file is False
    assert any(p.endswith("mypkg") for p in result.packages)
    best = result.best_entry_point
    assert best is not None and best.path.endswith("main.py")


def test_multi_package_imports_classified(multi_package: Path):
    result = scan_project(str(multi_package))
    # local package import
    assert any(i.name == "mypkg" and i.kind == ImportKind.LOCAL for i in result.imports)
    # stdlib import
    assert any(i.name == "json" and i.kind == ImportKind.STDLIB for i in result.imports)
    # no third-party deps in the example
    assert result.third_party_imports == []


def test_dynamic_import_detected(multi_package: Path):
    result = scan_project(str(multi_package))
    assert len(result.dynamic_imports) >= 1
    assert all(d.is_dynamic for d in result.dynamic_imports)


def test_data_files_classified(multi_package: Path):
    result = scan_project(str(multi_package))
    cats = result.data_by_category()
    assert FileCategory.DATA_TABLE.value in cats   # sample.csv
    assert FileCategory.DATA_CONFIG.value in cats   # config.json


def test_data_heavy_categories(data_heavy: Path):
    result = scan_project(str(data_heavy))
    cats = result.data_by_category()
    assert FileCategory.DATA_MODEL.value in cats    # weights.npz
    assert FileCategory.DATA_TABLE.value in cats     # table.xlsx
    assert FileCategory.DATA_CONFIG.value in cats    # settings.yaml


def test_missing_path_raises(tmp_path: Path):
    import pytest
    with pytest.raises(FileNotFoundError):
        scan_project(str(tmp_path / "does_not_exist"))
