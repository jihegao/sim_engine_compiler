"""Derive a six-mission zero-deferment control from accepted D11.var01."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D11-var01-atim-control-v1.0.0" / "native-input.json"
PARENT_SHA = "94c0addbaff610b656b25dd328949ea9710ab9a593cafebe488f7bfca665ead8"
OUTPUT = HERE / "native-input.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(found) != 1 or len(found[0]["instances"]) != 1:
        raise ValueError(f"one {name} table and instance required")
    return found[0]


def put(t: dict, **changes: object) -> None:
    names = [x["name"] for x in t["columns"]]
    rows = t["instances"][0]["rows"]
    if len(rows) != 1:
        raise ValueError(f"one {t['name']} row required")
    for name, value in changes.items():
        rows[0][names.index(name)] = value


def build() -> dict:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA:
        raise ValueError("accepted D11 parent differs")
    doc = copy.deepcopy(json.loads(raw))
    put(table(doc, "ProblemDescription"), PDESC="D11 six-mission zero-DTIM control with back-to-back requests")
    op = table(doc, "OperationProfile")
    cols = [c["name"] for c in op["columns"]]
    rows = op["instances"][0]["rows"]
    if len(rows) != 5 or [r[cols.index("STIM")] for r in rows] != [8, 16, 20, 48, 52]:
        raise ValueError("accepted five-wave schedule differs")
    rows[-2][cols.index("STIM")] = 24.0
    rows[-1][cols.index("STIM")] = 25.25
    sixth = copy.deepcopy(rows[-1])
    sixth[cols.index("STIM")] = 26.5
    rows.append(sixth)
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
        raise ValueError("frozen control input differs")
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": sha(raw), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
