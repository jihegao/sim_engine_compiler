"""Freeze accepted I01.var01 parent and the APID blank child delta."""
from __future__ import annotations

import argparse
import hashlib
import json

from build import HERE, PARENT, PARENT_SHA


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def tables(raw: bytes) -> dict:
    items = json.loads(raw)["model"]["tables"]
    result = {item["name"]: item for item in items}
    assert len(result) == len(items)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    parent_raw = PARENT.read_bytes()
    selected_raw = (HERE / "selected-input.json").read_bytes()
    blank_raw = (HERE / "blank-input.json").read_bytes()
    assert sha(parent_raw) == PARENT_SHA and selected_raw == parent_raw
    selected, blank = tables(selected_raw), tables(blank_raw)
    assert selected.keys() == blank.keys()
    changed = {name: {"before": table, "after": blank[name]}
               for name, table in selected.items() if table != blank[name]}
    assert set(changed) == {"Control", "ProblemDescription"}
    assert changed["Control"]["before"]["instances"][0]["rows"][0][3] == "AIR_BASIC"
    assert changed["Control"]["after"]["instances"][0]["rows"][0][3] is None
    result = {"schema": "simlox-i01-var02-blank-apid-exact-diff/v1",
              "parent_sha256": sha(parent_raw), "selected_sha256": sha(selected_raw),
              "blank_sha256": sha(blank_raw), "changed_tables": changed,
              "unchanged_table_count": len(selected) - len(changed)}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    path = HERE / "exact-diff.json"
    if args.write:
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(raw)
    elif path.read_bytes() != raw:
        raise ValueError("frozen exact diff differs")
    print(json.dumps({"sha256": sha(raw), "changed": sorted(changed)}))


if __name__ == "__main__":
    main()
