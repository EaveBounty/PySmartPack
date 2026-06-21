from pathlib import Path

from pysmartpack.core.size_analyzer import analyze, human_size


def test_human_size():
    assert human_size(0) == "0.0 B"
    assert human_size(1024) == "1.0 KB"
    assert human_size(1024 * 1024) == "1.0 MB"
    assert human_size(1536) == "1.5 KB"


def test_analyze_file(tmp_path: Path):
    f = tmp_path / "app.exe"
    f.write_bytes(b"x" * 2048)
    report = analyze(str(f))
    assert report.total_bytes == 2048
    assert report.entries[0].name == "app.exe"


def test_analyze_directory(tmp_path: Path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "lib.bin").write_bytes(b"y" * 4096)
    (tmp_path / "app.exe").write_bytes(b"z" * 1024)
    report = analyze(str(tmp_path))
    assert report.total_bytes == 4096 + 1024
    # largest first
    assert report.entries[0].name == "sub" and report.entries[0].is_dir
