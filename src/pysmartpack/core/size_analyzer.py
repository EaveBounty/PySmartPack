"""Output size analyzer (Milestone 3).

After a build, summarise where the bytes went so users can spot bloat
(e.g. a 400 MB torch folder). Works for both onedir and onefile outputs.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class SizeEntry:
    name: str
    bytes: int
    is_dir: bool = False

    @property
    def human(self) -> str:
        return human_size(self.bytes)


@dataclass
class SizeReport:
    total_bytes: int
    entries: List[SizeEntry]

    @property
    def total_human(self) -> str:
        return human_size(self.total_bytes)


def human_size(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num) < 1024.0:
            return f"{num:.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} PB"


def _dir_size(path: Path) -> int:
    total = 0
    for p in path.rglob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except OSError:
            continue
    return total


def analyze(output_path: str) -> SizeReport:
    """Analyze a packaged output (file or directory)."""
    path = Path(output_path)
    entries: List[SizeEntry] = []

    if path.is_file():
        size = path.stat().st_size if path.exists() else 0
        return SizeReport(total_bytes=size,
                          entries=[SizeEntry(path.name, size, is_dir=False)])

    target_dir = path if path.is_dir() else path.parent
    if not target_dir.exists():
        return SizeReport(total_bytes=0, entries=[])

    total = 0
    for child in target_dir.iterdir():
        try:
            if child.is_dir():
                size = _dir_size(child)
                entries.append(SizeEntry(child.name, size, is_dir=True))
            else:
                size = child.stat().st_size
                entries.append(SizeEntry(child.name, size, is_dir=False))
            total += size
        except OSError:
            continue

    entries.sort(key=lambda e: e.bytes, reverse=True)
    return SizeReport(total_bytes=total, entries=entries)
