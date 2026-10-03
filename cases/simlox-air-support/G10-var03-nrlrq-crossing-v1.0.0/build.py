"""Derive a fixed-seed NRLRQ crossing probe from accepted G10.var01 ACTIVE links."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G10-var01-active-single-link-v1.0.0" / "native-input.json"
PARENT_SHA = "7e990242656119f9424fcf390ae8c46eb23e4751dbe6fb44bd80b3bb4cf307d1"
OUTPUT = HERE / "native-input.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(model: dict, name: str) -> dict:
    matches = [t for t in model["tables"] if t["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"one {name} table required")
    return matches[0]


def rows(model: dict, name: str) -> tuple[list[str], list[list]]:
    t = table(model, name)
    if len(t["instances"]) != 1:
        raise ValueError(f"one {name} instance required")
    return [c["name"] for c in t["columns"]], t["instances"][0]["rows"]


def build() -> dict:
    raw = PARENT.read_bytes()
    if sha(raw) != PARENT_SHA:
        raise ValueError("accepted G10.var01 parent changed")
    doc = copy.deepcopy(json.loads(raw))
    model = doc["model"]
    cols, values = rows(model, "ProblemDescription")
    if len(values) != 1:
        raise ValueError("one description required")
    values[0][cols.index("PDESC")] = "G10.var03 ACTIVE NRLRQ first crossing FRT 900000"
    cols, values = rows(model, "Item")
    by_id = {r[cols.index("IID")]: r for r in values}
    if set(by_id) != {"TEACH-LRU-01", "TEACH-SRU-01"}:
        raise ValueError("unexpected item roster")
    for iid in ("TEACH-LRU-01", "TEACH-SRU-01"):
        row = by_id[iid]
        if row[cols.index("FRT")] != 300000 or row[cols.index("OPID")] != "OPHOURS":
            raise ValueError(f"unexpected parent failure input: {iid}")
        row[cols.index("FRT")] = 900000
    scols, svalues = rows(model, "System")
    if len(svalues) != 1 or svalues[0][scols.index("SID")] != "TEACH-AIR-01" or svalues[0][scols.index("FRT")] != 600000 or svalues[0][scols.index("OPID")] != "OPHOURS":
        raise ValueError("unexpected parent system failure input")
    # Two installed LRUs at 900000 each must not exceed the mother FRT.
    svalues[0][scols.index("FRT")] = 1800000
    rcols, rvalues = rows(model, "Redundancy")
    if len(rvalues) != 1 or rvalues[0][rcols.index("ACPA")] != "ACTIVE" or rvalues[0][rcols.index("NRL")] != 2 or rvalues[0][rcols.index("NRLRQ")] != 1 or rvalues[0][rcols.index("TSWOV")] != 0:
        raise ValueError("unexpected accepted parent redundancy")
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
        raise ValueError("frozen input differs from builder")
    print(json.dumps({"parent_sha256": PARENT_SHA, "input_sha256": sha(raw), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
