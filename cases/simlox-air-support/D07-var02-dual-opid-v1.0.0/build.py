"""Freeze a dual-operation-parameter traditional failure-rate candidate."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "D02-var01-traditional-op-hours-v1.0.0" / "native-input.json"
CUSTOM = ROOT / "A15-custom-utilization-v1.0.0" / "per-hour-input.json"
RATE = ROOT / "D02-var06-traditional-clock-inputs-v1.0.0" / "native-input-rate-ophours.json"
HASHES = {
    PARENT: "9e6d264330c6f7b41752ed8b0c09a32ac45089cec9ec823ad5e3367ce7f348e2",
    CUSTOM: "2100f7d1ae7725962483419571433d64c6ef92f8fb69078dd58f6835d90ed084",
    RATE: "b76dd77056378ca06c0134ddd363816d9c9ac211e4f36181fb597eca0e9b4797",
}
OUTPUT = HERE / "native-input.json"


def tables(path: Path) -> list[dict]:
    return json.loads(path.read_bytes())["model"]["tables"]


def table(items: list[dict], name: str) -> dict:
    found = [item for item in items if item["name"] == name]
    if len(found) != 1:
        raise ValueError(f"expected one {name} table")
    return found[0]


def build() -> dict:
    for path, expected in HASHES.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"accepted source changed: {path}")
    doc = json.loads(PARENT.read_bytes())
    ts = doc["model"]["tables"]
    custom = tables(CUSTOM)
    rate = tables(RATE)
    table(ts, "ProblemDescription")["instances"][0]["rows"][0][0] = (
        "D07.var02 traditional OPHOURS plus KM failure exposure"
    )
    op = table(ts, "OperationParameter")
    op["instances"][0]["rows"] = copy.deepcopy(
        table(custom, "OperationParameter")["instances"][0]["rows"]
    )
    ts.append(copy.deepcopy(table(custom, "MissionTypeUtilization")))
    item_rate = copy.deepcopy(table(rate, "ItemFailureRate"))
    item_rate["instances"][0]["rows"] = [["TEACH-LRU-01", "KM", 5000.0, None]]
    ts.append(item_rate)
    ts.append({
        "name": "SystemFailureRate",
        "columns": [
            {"name": "SID", "datatype": "string", "key": True},
            {"name": "OPID", "datatype": "string", "key": True},
            {"name": "FRT", "datatype": "double"},
            {"name": "NOTE", "datatype": "string"},
        ],
        "instances": [{"instance_name": "", "rows": [["TEACH-AIR-01", "KM", 5000.0, None]]}],
    })
    if [table(ts, n)["instances"][0]["rows"][0][4] for n in ("System", "Item")] != ["OPHOURS"] * 2:
        raise ValueError("base OPHOURS rates changed")
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode()
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(raw)
    elif OUTPUT.read_bytes() != raw:
        raise ValueError("frozen D07.var02 input differs")
    print(json.dumps({"variant_id": "D07.var02", "input_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
