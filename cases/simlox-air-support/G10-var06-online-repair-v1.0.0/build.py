"""Derive one continuous on-mission redundancy-repair probe from accepted G10.var03."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G10-var03-nrlrq-crossing-v1.0.0/native-input.json"
PARENT_SHA = "df9966f1bee58561b1bd54d05ced353abefc37efcd7559c47af5c63683aaa718"
DONOR = HERE.parent / "G05-unavailable-standby-v1.0.3/unavailable-input.json"
DONOR_SHA = "b0d79caeb71dbf991291b9122dff3139bc52c27e2c014b5bf624632539101f0d"
OUTPUT = HERE / "native-input.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(doc: dict, name: str) -> tuple[list[str], list[list]]:
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"one {name} table/instance required")
    return [c["name"] for c in matches[0]["columns"]], matches[0]["instances"][0]["rows"]


def build() -> dict:
    parent_raw, donor_raw = PARENT.read_bytes(), DONOR.read_bytes()
    if sha(parent_raw) != PARENT_SHA or sha(donor_raw) != DONOR_SHA:
        raise ValueError("accepted parent or mission donor changed")
    doc = copy.deepcopy(json.loads(parent_raw))
    donor = json.loads(donor_raw)
    dcols, drows = table(donor, "MissionType")
    if len(drows) != 1 or tuple(drows[0][dcols.index(k)] for k in ("DURN", "TFOUT", "TFRET", "MPAT")) != (26.0, None, None, "CONTINUOUS"):
        raise ValueError("accepted continuous donor shape changed")
    dcols, drows = table(donor, "OperationProfile")
    if len(drows) != 1 or drows[0][dcols.index("STIM")] != 8.0:
        raise ValueError("accepted continuous donor schedule changed")

    cols, rows = table(doc, "ProblemDescription")
    if len(rows) != 1:
        raise ValueError("one description required")
    rows[0][cols.index("PDESC")] = "G10.var06 continuous on-mission redundancy repair"

    cols, rows = table(doc, "MissionType")
    if len(rows) != 1 or rows[0][cols.index("DURN")] != 2.0:
        raise ValueError("unexpected parent mission")
    mission = rows[0]
    mission[cols.index("DESCR")] = "26-hour continuous redundancy-repair mission"
    # Explicitly bind the donor's accepted continuous mission recipe.
    dmc, dmr = table(donor, "MissionType")
    for name in ("DURN", "TFOUT", "TFRET", "MPAT"):
        mission[cols.index(name)] = dmr[0][dmc.index(name)]

    cols, rows = table(doc, "OperationProfile")
    if [r[cols.index("STIM")] for r in rows] != [8.0, 20.0, 32.0]:
        raise ValueError("unexpected parent schedule")
    del rows[1:]
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
    print(json.dumps({"parent_sha256": PARENT_SHA, "donor_sha256": DONOR_SHA, "input_sha256": sha(raw), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
