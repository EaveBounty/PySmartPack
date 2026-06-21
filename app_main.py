"""Frozen-app entry point.

Used by ``scripts/build_app.py`` (PyInstaller) to produce a standalone,
dependency-free PySmartPack executable. Uses an absolute import so it works
both as a normal script and inside a frozen bundle.
"""
import sys

from pysmartpack.cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
