"""Add OPHOURS and CALHOURS intervals to the frozen D10 mission-count PM."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D10-var01-missions-v1.0.0" / "native-input.json"
PARENT_SHA = "6607991260e3f911d0121c7949443409a57937e95f80c7e4f3a2faa6ac20ba72"
OUTPUT = HERE / "native-input.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def build() -> dict:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA:
        raise ValueError("frozen D10 mission parent differs")
    doc = copy.deepcopy(json.loads(raw))
    tables = doc["model"]["tables"]
    if any(t["name"] == "MaterielPMInterval" for t in tables):
        raise ValueError("parent already has PM interval extension")
    label = next(t for t in tables if t["name"] == "ProblemDescription")
    label["instances"][0]["rows"][0][0] = "D10 one PM with MISSIONS, OPHOURS, CALHOURS counters"
    tables.append({
        "columns": [
            {"datatype": "string", "key": True, "name": "PMID"},
            {"datatype": "string", "key": True, "name": "OPID"},
            {"datatype": "double", "name": "PMINT"},
            {"datatype": "string", "name": "NOTE"},
        ],
        "instances": [{"instance_name": "", "rows": [
            ["MS2", "OPHOURS", 3.0, None],
            ["MS2", "CALHOURS", 24.0, None],
        ]}],
        "name": "MaterielPMInterval",
    })
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUTPUT.exists():
            raise FileExistsError(OUTPUT)
        OUTPUT.write_bytes(raw)
    elif OUTPUT.read_bytes() != raw:
        raise ValueError("frozen D10 multi-counter input differs")
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": sha(raw), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
