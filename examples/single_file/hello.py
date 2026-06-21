"""Single-file example for PySmartPack (stdlib-only so it always packages)."""
import argparse
import datetime as dt
import json


def build_payload(name: str) -> dict:
    return {"greeting": f"Hello, {name}!", "time": dt.datetime.now().isoformat()}


def main() -> None:
    parser = argparse.ArgumentParser(description="PySmartPack single-file demo")
    parser.add_argument("--name", default="World")
    args = parser.parse_args()
    print(json.dumps(build_payload(args.name), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
