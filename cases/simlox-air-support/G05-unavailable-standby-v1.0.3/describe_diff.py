"""Freeze the exact unavailable-standby input delta from accepted G05."""
from __future__ import annotations

import argparse
import hashlib
import json

from build import HERE, PARENT, PARENT_SHA256, SOURCE, build


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_tables(document: dict) -> dict:
    tables = document["model"]["tables"]
    assert len({t["name"] for t in tables}) == len(tables)
    return {t["name"]: t for t in tables}


def difference(before: dict, after: dict) -> dict:
    a, b = canonical_tables(before), canonical_tables(after)
    assert a.keys() == b.keys()
    return {name: {"before": a[name]["instances"][0]["rows"],
                   "after": b[name]["instances"][0]["rows"]}
            for name in sorted(a) if a[name] != b[name]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    parent_raw = PARENT.read_bytes()
    assert sha(parent_raw) == PARENT_SHA256
    child_raw = SOURCE.read_bytes()
    assert json.loads(child_raw) == build()
    changes = difference(json.loads(parent_raw), json.loads(child_raw))
    assert set(changes) == {"ProblemDescription", "CMLocation", "RBDParallel", "MissionType"}
    cm_before, cm_after = changes["CMLocation"]["before"], changes["CMLocation"]["after"]
    assert len(cm_before) == len(cm_after) == 2
    assert cm_before[0] == cm_after[0]
    assert cm_before[1][0] == cm_after[1][0] == "FM-POS-B"
    assert cm_before[1][:3] == cm_after[1][:3] and cm_before[1][3] == 0.5 and cm_after[1][3] == 40.0 and cm_before[1][4:] == cm_after[1][4:]
    rbd_before, rbd_after = changes["RBDParallel"]["before"], changes["RBDParallel"]["after"]
    assert len(rbd_before) == len(rbd_after) == 1
    columns = [c["name"] for c in canonical_tables(json.loads(parent_raw))["RBDParallel"]["columns"]]
    onlm = columns.index("ONLM")
    assert rbd_before[0][onlm] == "N" and rbd_after[0][onlm] == "Y"
    assert all(rbd_before[0][i] == rbd_after[0][i] for i in range(len(columns)) if i != onlm)
    mission_before, mission_after = changes["MissionType"]["before"], changes["MissionType"]["after"]
    assert len(mission_before) == len(mission_after) == 1
    columns = [c["name"] for c in canonical_tables(json.loads(parent_raw))["MissionType"]["columns"]]
    mpat = columns.index("MPAT")
    assert mission_before[0][mpat] is None and mission_after[0][mpat] == "CONTINUOUS"
    descr = columns.index("DESCR")
    assert mission_before[0][descr] == "26-hour fixed teaching mission"
    assert mission_after[0][descr] == "26-hour continuous standby-selection diagnostic mission"
    tfout, tfret = columns.index("TFOUT"), columns.index("TFRET")
    assert mission_before[0][tfout] == mission_before[0][tfret] == 0.25
    assert mission_after[0][tfout] is mission_after[0][tfret] is None
    assert all(mission_before[0][i] == mission_after[0][i] for i in range(len(columns)) if i not in {mpat, descr, tfout, tfret})
    result = {"schema": "simlox-g05-unavailable-standby-exact-diff/v1",
              "parent_sha256": PARENT_SHA256, "source_sha256": sha(child_raw), "parent_to_unavailable": changes}
    data = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    output = HERE / "exact-diff.json"
    if args.write:
        if output.exists():
            raise FileExistsError(output)
        output.write_bytes(data)
    elif output.read_bytes() != data:
        raise ValueError("frozen exact diff differs")
    print(json.dumps({"changed_tables": sorted(changes), "sha256": sha(data)}))


if __name__ == "__main__":
    main()
