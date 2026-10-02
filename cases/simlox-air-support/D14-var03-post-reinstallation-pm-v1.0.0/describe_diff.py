"""Freeze exact table deltas from both accepted parent arms and between new arms."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D14-var02-03-zero-age-reinstallation-v1.0.0"
OUT = HERE / "exact-diff.json"
ARMS = ("monitored", "system-converted")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tables(path: Path) -> dict:
    return {t["name"]: t for t in json.loads(path.read_bytes())["model"]["tables"]}


def compare(a: dict, b: dict) -> dict:
    return {name: {"before": a.get(name), "after": b.get(name)}
            for name in sorted(set(a) | set(b)) if a.get(name) != b.get(name)}


def main() -> None:
    parents = {arm: PARENT / f"native-input-{arm}.json" for arm in ARMS}
    current = {arm: HERE / f"native-input-{arm}.json" for arm in ARMS}
    d = {"schema": "simlox-air-support-exact-table-diff/v1", "case_id": "D14",
         "variant_ids": ["D14.var03"],
         "parents": {arm: {"input_sha256": sha(path), "changed": compare(tables(path), tables(current[arm]))}
                     for arm, path in parents.items()},
         "inputs": {arm: sha(path) for arm, path in current.items()},
         "arm_contrast": compare(tables(current["monitored"]), tables(current["system-converted"]))}
    raw = (json.dumps(d, ensure_ascii=False, indent=2) + "\n").encode()
    if OUT.exists():
        if OUT.read_bytes() != raw:
            raise ValueError("frozen exact diff differs")
    else:
        OUT.write_bytes(raw)
    print(json.dumps({"diff_sha256": hashlib.sha256(raw).hexdigest(),
                      "changed_tables": {arm: sorted(d["parents"][arm]["changed"]) for arm in ARMS},
                      "arm_contrast_tables": sorted(d["arm_contrast"])}))


if __name__ == "__main__":
    main()
