"""Freeze matched crew-present/absent return-boundary candidates from G10.var06."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G10-var06-online-repair-v1.0.0/native-input.json"
PARENT_SHA = "501924dfde54c81528ccb06cee5320111b2338db59f852f0e26be59d2f77ff35"
DONOR = HERE.parent / "D09-var04-shortage-at-escalation-v1.0.0/native-input-supplied.json"
DONOR_SHA = "79fdfb9fb1c4901368b24a33da49ab15b77a2cafa421446350e51e6f0457ff8e"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def table(doc: dict, name: str) -> tuple[list[str], list[list]]:
    matches = [t for t in doc["model"]["tables"] if t["name"] == name]
    if len(matches) != 1 or len(matches[0]["instances"]) != 1:
        raise ValueError(f"one {name} table/instance required")
    return [c["name"] for c in matches[0]["columns"]], matches[0]["instances"][0]["rows"]


def copy_donor_rows(target: dict, donor: dict, name: str) -> tuple[list[str], list[list]]:
    columns, rows = table(target, name)
    donor_columns, donor_rows = table(donor, name)
    if columns != donor_columns or rows:
        raise ValueError(f"unexpected empty {name} target schema")
    rows[:] = copy.deepcopy(donor_rows)
    return columns, rows


def build() -> dict[str, dict]:
    parent_raw, donor_raw = PARENT.read_bytes(), DONOR.read_bytes()
    if sha(parent_raw) != PARENT_SHA or sha(donor_raw) != DONOR_SHA:
        raise ValueError("accepted parent or crew-task donor changed")
    doc = copy.deepcopy(json.loads(parent_raw))
    donor = json.loads(donor_raw)
    cols, rows = table(doc, "MissionType")
    if len(rows) != 1 or rows[0][cols.index("DURN")] != 26 or rows[0][cols.index("MPAT")] != "CONTINUOUS":
        raise ValueError("unexpected accepted continuous mission")
    rows[0][cols.index("DURN")] = 1.0
    rows[0][cols.index("DESCR")] = "One-hour continuous return-boundary mission"
    cols, rows = table(doc, "OperationProfile")
    if len(rows) != 1 or rows[0][cols.index("STIM")] != 8.0:
        raise ValueError("unexpected accepted operation profile")
    second = copy.deepcopy(rows[0])
    second[cols.index("STIM")] = 10.5
    rows.append(second)
    cols, rows = table(doc, "SystemRepair")
    if len(rows) != 1 or rows[0][cols.index("SURPT")] != .5 or rows[0][cols.index("SURPTID")] != "E01-SURP":
        raise ValueError("unexpected accepted system replacement")
    rows[0][cols.index("SURPT")] = 3.0
    cols, rows = table(doc, "TaskBreakDown")
    if len(rows) != 2 or [r[cols.index("SEQ")] for r in rows] != [1, 2] or [r[cols.index("DURN")] for r in rows] != [1/6, 1/3]:
        raise ValueError("unexpected accepted two-subtask repair")
    rows[1][cols.index("DURN")] = 17/6
    for name in ("Resource", "ResourceAllocation", "SubTaskResource"):
        columns, rows = copy_donor_rows(doc, donor, name)
        if len(rows) != 1:
            raise ValueError(f"one {name} donor row required")
        if name == "ResourceAllocation":
            if rows[0][columns.index("RID")] != "P-CREW" or rows[0][columns.index("STID")] != "BASE-01" or rows[0][columns.index("RQTY")] != 1:
                raise ValueError("unexpected donor crew allocation")
        if name == "SubTaskResource":
            if rows[0][columns.index("SEQ")] != 1 or rows[0][columns.index("RID")] != "P-CREW" or rows[0][columns.index("QTY")] != 1:
                raise ValueError("unexpected donor removal demand")
            rows[0][columns.index("TID")] = "E01-SURP"
    cols, rows = table(doc, "ProblemDescription")
    if len(rows) != 1:
        raise ValueError("one description required")
    rows[0][cols.index("PDESC")] = "G10.var07 crew1 first subtask started before return"
    present = doc
    absent = copy.deepcopy(present)
    cols, rows = table(absent, "ResourceAllocation")
    rows[0][cols.index("RQTY")] = 0
    cols, rows = table(absent, "ProblemDescription")
    rows[0][cols.index("PDESC")] = "G10.var07 crew0 first subtask not started before return"
    return {"crew-present": present, "crew-absent": absent}


def main() -> None:
    for name, doc in build().items():
        path = HERE / f"native-input-{name}.json"
        raw = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if path.exists():
            if path.read_bytes() != raw:
                raise ValueError(f"frozen input differs: {name}")
        else:
            path.write_bytes(raw)
        print(json.dumps({"arm": name, "sha256": sha(raw), "bytes": len(raw)}))


if __name__ == "__main__":
    main()
