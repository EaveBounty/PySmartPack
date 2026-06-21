"""Demonstrates a dynamic import the scanner should flag."""
import importlib
from typing import Any


def load_plugin(module_name: str) -> Any:
    module = importlib.import_module(module_name)
    return module
