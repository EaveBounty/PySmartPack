"""Entry point of the multi-package example."""
import json
from pathlib import Path

from mypkg.util import greet
from mypkg.plugins import load_plugin


def main() -> None:
    print(greet("PySmartPack"))
    cfg_path = Path(__file__).parent / "data" / "config.json"
    if cfg_path.exists():
        print("config:", json.loads(cfg_path.read_text(encoding="utf-8")))
    load_plugin("mypkg.util")


if __name__ == "__main__":
    main()
