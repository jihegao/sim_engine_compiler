"""Add one third ready aircraft to the accepted A05 system-loss mission."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A05-var02-system-loss-probe-v1.0.0" / "native-input.json"
PARENT_SHA = "02e823bd09fd3e6a3c2f0ae59846adcb2d35bcbc6d0ee9b09d0d936ebf36b10c"
OUT = HERE / "native-input.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def set_one(doc: dict, name: str, field: str, before: object, after: object) -> None:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"unexpected {name} structure")
    t = found[0]
    columns = [c["name"] for c in t["columns"]]
    rows = t["instances"][0]["rows"]
    if len(rows) != 1 or field not in columns or rows[0][columns.index(field)] != before:
        raise ValueError(f"unexpected {name}.{field}")
    rows[0][columns.index(field)] = after


def build() -> dict:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA:
        raise ValueError("accepted parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    set_one(doc, "ProblemDescription", "PDESC",
            "A05 continuous four-hour two-aircraft seeded system-loss probe",
            "A05 continuous four-hour three-aircraft distinct-spare probe")
    set_one(doc, "SystemDeployment", "QTYPS", 2, 3)
    set_one(doc, "Unit", "DESCR", "Two-aircraft teaching unit", "Three-aircraft teaching unit")
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUT.exists():
            raise FileExistsError(OUT)
        OUT.write_bytes(raw)
    elif OUT.read_bytes() != raw:
        raise ValueError("frozen input differs")
    print(json.dumps({"native_input_sha256": sha(raw)}))


if __name__ == "__main__":
    main()
