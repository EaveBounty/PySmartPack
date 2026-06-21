"""Data-heavy example: exercises data-file classification (not meant to be built)."""
import json
from pathlib import Path


def load_config() -> dict:
    p = Path(__file__).parent / "settings.yaml"
    return {"path": str(p)}


def main() -> None:
    print(json.dumps(load_config()))


if __name__ == "__main__":
    main()
