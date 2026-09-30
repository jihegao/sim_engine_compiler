"""Derive explicit-zero and omitted-row C07 shift-resource probes."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C07-cross-shift-gap-v1.0.0" / "draos-y-input.json"
PARENT_SHA256 = "cab26bedc1c5bbadadc82476c34e6e4bd6e71624bebeebe46e4ca342a616674d"


def build(variant: str) -> dict:
    assert variant in ("qty-zero", "row-absent")
    raw = PARENT.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == PARENT_SHA256
    doc = copy.deepcopy(json.loads(raw))
    tables = {table["name"]: table for table in doc["model"]["tables"]}
    shift_rows = tables["ShiftResource"]["instances"][0]["rows"]
    assert shift_rows == [["DAY-OPEN", "BASE-01", "P-CREW", 1, None, None]]
    if variant == "qty-zero":
        shift_rows[0][3] = 0
    else:
        shift_rows.clear()
    assert tables["Control"]["instances"][0]["rows"][0][17] == "Y"
    tables["ProblemDescription"]["instances"][0]["rows"][0][0] = (
        f"C07 shift resource {'explicit zero' if variant == 'qty-zero' else 'row absent'}; DRAOS=Y"
    )
    return doc


def main() -> None:
    for variant in ("qty-zero", "row-absent"):
        path = HERE / f"{variant}-input.json"
        raw = (json.dumps(build(variant), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if path.exists():
            assert path.read_bytes() == raw, f"frozen source differs: {path}"
        else:
            path.write_bytes(raw)
        print(variant, hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
