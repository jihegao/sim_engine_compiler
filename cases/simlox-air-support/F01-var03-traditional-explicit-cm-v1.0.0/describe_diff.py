"""Check the frozen full-table delta from the accepted traditional arm."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEFT = HERE.parent / "F01-var01-two-three-level-v1.0.1/three-level-input.json"
RIGHT = HERE / "explicit-input.json"
OUT = HERE / "exact-diff.json"


def table_map(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    return {table["name"]: table for table in doc["model"]["tables"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    left, right = table_map(LEFT), table_map(RIGHT)
    changed = []
    for name in sorted(left.keys() | right.keys()):
        if left.get(name) != right.get(name):
            changed.append({"table": name, "before": left.get(name), "after": right.get(name)})
    data = {"schema": "simlox-f01-var03-exact-table-diff/v1",
            "traditional_input_sha256": hashlib.sha256(LEFT.read_bytes()).hexdigest(),
            "explicit_input_sha256": hashlib.sha256(RIGHT.read_bytes()).hexdigest(),
            "changed_tables": changed}
    raw = (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUT.exists():
            raise FileExistsError(OUT)
        OUT.write_bytes(raw)
    elif OUT.read_bytes() != raw:
        raise ValueError("frozen table diff differs")
    print(json.dumps({"changed_tables": [c["table"] for c in changed],
                      "diff_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
