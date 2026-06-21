"""Test configuration: make the ``src`` layout importable without installation."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
EXAMPLES = ROOT / "examples"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pytest


@pytest.fixture
def examples_dir() -> Path:
    return EXAMPLES


@pytest.fixture
def single_file(examples_dir: Path) -> Path:
    return examples_dir / "single_file" / "hello.py"


@pytest.fixture
def multi_package(examples_dir: Path) -> Path:
    return examples_dir / "multi_package"


@pytest.fixture
def data_heavy(examples_dir: Path) -> Path:
    return examples_dir / "data_heavy"
