"""Entry point: ``python -m pysmartpack`` (GUI) or ``pysmartpack <cmd>`` (CLI)."""
from __future__ import annotations

import sys


def main() -> int:
    from .cli import main as cli_main
    return cli_main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
