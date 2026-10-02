"""Freeze complete table and cell differences against accepted D06 and between arms."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D06-explicit-position-direct-repair-v1.0.0" / "native-input.json"
OUT = HERE / "exact-diff.json"


def table_map(path: Path) -> dict:
    doc = json.loads(path.read_bytes())
    return {t["name"]: t for t in doc["model"]["tables"]}


def compare(a: dict, b: dict) -> dict:
    names = sorted(set(a) | set(b))
    return {name: {"before": a.get(name), "after": b.get(name)} for name in names if a.get(name) != b.get(name)}


def main() -> None:
    p = table_map(PARENT)
    y = table_map(HERE / "native-input-monitored.json")
    n = table_map(HERE / "native-input-system-converted.json")
    d = {"schema": "simlox-air-support-exact-table-diff/v1", "case_id": "D14", "variant_id": "D14.var01",
         "parent_input_sha256": hashlib.sha256(PARENT.read_bytes()).hexdigest(),
         "monitored_input_sha256": hashlib.sha256((HERE / "native-input-monitored.json").read_bytes()).hexdigest(),
         "system_converted_input_sha256": hashlib.sha256((HERE / "native-input-system-converted.json").read_bytes()).hexdigest(),
         "parent_to_monitored": compare(p, y), "parent_to_system_converted": compare(p, n),
         "monitored_to_system_converted": compare(y, n)}
    raw = (json.dumps(d, ensure_ascii=False, indent=2) + "\n").encode()
    if OUT.exists():
        if OUT.read_bytes() != raw:
            raise ValueError("frozen exact diff differs")
    else:
        OUT.write_bytes(raw)
    print(json.dumps({"diff_sha256": hashlib.sha256(raw).hexdigest(),
                      "parent_changed_tables": sorted(d["parent_to_monitored"]),
                      "arm_changed_tables": sorted(d["monitored_to_system_converted"])}))


if __name__ == "__main__":
    main()
