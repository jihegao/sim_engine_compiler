"""Derive the D05.var01 two-worker capacity control from accepted D05."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D05-maintenance-competition-v1.0.0" / "native-input.json"
PARENT_SHA256 = "4443d057ade36010a84186aa0f9ac8279886563db190ed80699b7fe48ad2baad"
OUTPUT = HERE / "native-input.json"


def one(model: dict, name: str, **values: object) -> None:
    found = [t for t in model["tables"] if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"unexpected {name} table shape")
    table = found[0]
    columns = [c["name"] for c in table["columns"]]
    rows = table["instances"][0]["rows"]
    if len(rows) != 1 or set(values) - set(columns):
        raise ValueError(f"unexpected {name} row/columns")
    for field, value in values.items():
        rows[0][columns.index(field)] = value


def build() -> dict:
    raw = PARENT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SHA256:
        raise ValueError("accepted D05 parent fingerprint differs")
    doc = copy.deepcopy(json.loads(raw))
    model = doc["model"]
    one(model, "ProblemDescription", PDESC="D05.var01 two-worker capacity control for repair and PM")
    one(model, "Resource", DESCR="Two shared maintenance workers")
    one(model, "ResourceAllocation", RQTY=2)
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
        raise ValueError("frozen D05.var01 input differs")
    print(json.dumps({"case_id": "D05", "variant_id": "D05.var01", "parent_sha256":
                      PARENT_SHA256, "input_sha256": hashlib.sha256(raw).hexdigest(),
                      "bytes": len(raw)}))


if __name__ == "__main__":
    main()
