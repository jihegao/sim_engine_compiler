"""Derive fixed-count random-time missions from accepted A02."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A02-single-aircraft-repeated-missions" / "native-input.json"
PARENT_SHA = "84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8"
OUT = HERE / "native-input.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def one(doc: dict, name: str) -> tuple[list[str], list[list]]:
    table, = (t for t in doc["model"]["tables"] if t["name"] == name)
    instance, = table["instances"]
    return [c["name"] for c in table["columns"]], instance["rows"]


def set_one(doc: dict, name: str, field: str, before: object, after: object) -> None:
    columns, rows = one(doc, name)
    if len(rows) != 1 or field not in columns or rows[0][columns.index(field)] != before:
        raise ValueError(f"unexpected {name}.{field}")
    rows[0][columns.index(field)] = after


def build() -> dict:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA:
        raise ValueError("accepted A02 parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    set_one(doc, "ProblemDescription", "PDESC",
            "A01/A02 generic one-aircraft teaching case; no J35/F35 equivalence",
            "A08.var01 three random-time missions per period, 32 replications")
    set_one(doc, "Control", "NREPS", 1, 32)
    set_one(doc, "SystemDeployment", "QTYPS", 1, 3)
    set_one(doc, "Unit", "DESCR", "One-aircraft teaching unit", "Three-aircraft random-time teaching unit")
    columns, rows = one(doc, "OperationProfile")
    if len(rows) != 3:
        raise ValueError("expected three A02 scheduled waves")
    profile = [dict(zip(columns, row, strict=True)) for row in rows]
    if [p["STIM"] for p in profile] != [8.0, 20.0, 32.0] or any(p["ITYPE"] != "SCHEDULED" for p in profile):
        raise ValueError("unexpected A02 profile")
    if any(p["IQTY"] != 1 or p["IPER"] != 0 or p["DTIM"] != 1/3 for p in profile):
        raise ValueError("unexpected A02 initiation fields")
    p = profile[0]
    p.update(ITYPE="RANDOM", IQTY=3, IQTYD=None, IPER=12.0, IDISP="RANDOM")
    rows[:] = [[p[c] for c in columns]]
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
