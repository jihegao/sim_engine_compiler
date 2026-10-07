"""One-time exact custody copies of unpublished, excluded E08 diagnostic source.

The default invocation verifies an existing map and never writes. --write
creates only absent package copies and the map, with exact contract SHA/size.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import replay

HERE = Path(__file__).resolve().parent
OUT = HERE / "preserved-excluded-source"
MAP = HERE / "excluded-source-custody-map.json"


def records(write: bool = False) -> list[dict]:
    result = []
    for history in replay.CONTRACT["excluded_history"]:
        for pin in history["source_files"]:
            original = replay.repo_path(pin["path"])
            replay.verify_pin(pin)
            copy = OUT / history["package"] / original.name
            expected = {"bytes": pin["bytes"], "sha256": pin["sha256"]}
            if write and not copy.exists():
                copy.parent.mkdir(parents=True, exist_ok=True)
                copy.write_bytes(original.read_bytes())
            assert copy.is_file() and replay.digest(copy) == expected, str(copy)
            result.append({"status": "excluded_unpublished_source", "package": history["package"],
                           "original_path": str(original),
                           "copy_path": copy.relative_to(HERE).as_posix(), **expected})
    assert len(result) == 22 and len({x["copy_path"] for x in result}) == 22
    return sorted(result, key=lambda x: x["original_path"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.write:
        assert not MAP.exists(), "never overwrite custody map"
        result = records(write=True)
        MAP.write_bytes((json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    else:
        result = records()
        assert json.loads(MAP.read_text(encoding="utf-8")) == result
    print(json.dumps({"excluded_source_copies": len(result), "written": args.write}, sort_keys=True))


if __name__ == "__main__":
    main()
