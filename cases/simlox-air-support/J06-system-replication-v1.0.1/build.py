"""Append bounded System TOTAL/TIME/SNAPS replication controls to J04.var01."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "J04-var01-fixed-replications-v1.0.0" / "probe-input.json"
PARENT_SHA = "4a4e2df598a515762b1c4de8894c139c6ac6bce40c523d7e5f0720514f7f5579"
OUTPUT = HERE / "replication-input.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    if sha(PARENT) != PARENT_SHA:
        raise ValueError("accepted J04.var01 input changed")
    doc = copy.deepcopy(json.loads(PARENT.read_bytes()))
    tables = doc["model"]["tables"]
    if len(tables) != 32 or any(t["name"] in {"SnapshotResultTimes", "ReplicationResultControlSystem"} for t in tables):
        raise ValueError("unexpected parent tables")
    control = next(t for t in tables if t["name"] == "Control")
    names = [c["name"] for c in control["columns"]]
    row = control["instances"][0]["rows"][0]
    if (row[names.index("NREPS")], row[names.index("TCLEV")], row[names.index("RSEED")], row[names.index("SIMPE")]) != (16, 0.0, "1", 36.0):
        raise ValueError("unexpected fixed-replication controls")
    tables.extend([
        {"name": "SnapshotResultTimes", "columns": [{"datatype": "double", "name": "SSTIM"}, {"datatype": "string", "name": "NOTE"}],
         "instances": [{"instance_name": "", "rows": [[9.0, None], [11.0, None]]}]},
        {"name": "ReplicationResultControlSystem", "columns": [
            {"datatype": "string", "key": True, "name": "SID"}, {"datatype": "string", "key": True, "name": "USTID"},
            *({"datatype": "string", "name": name} for name in ("TOTAL", "TIME", "SNAPS", "NOTE"))],
         "instances": [{"instance_name": "", "rows": [["TEACH-AIR-01", "TEACH-UNIT", "Y", "Y", "Y", None]]}]},
    ])
    return doc


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode()
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(raw)
    elif OUTPUT.read_bytes() != raw:
        raise ValueError("frozen input differs")
    print(hashlib.sha256(raw).hexdigest())
