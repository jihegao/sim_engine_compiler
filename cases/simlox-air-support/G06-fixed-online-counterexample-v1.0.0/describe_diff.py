"""Freeze the continuous-to-fixed ONLM=Y mission-pattern delta."""
from __future__ import annotations

import argparse
import hashlib
import json

from build import HERE, PARENT, PARENT_SHA256, SOURCE, DEFERRED, build, build_deferred


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tables(document: dict) -> dict:
    result = {table["name"]: table for table in document["model"]["tables"]}
    assert len(result) == len(document["model"]["tables"])
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    parent_raw, child_raw, deferred_raw = PARENT.read_bytes(), SOURCE.read_bytes(), DEFERRED.read_bytes()
    assert sha(parent_raw) == PARENT_SHA256
    parent, child, deferred = json.loads(parent_raw), json.loads(child_raw), json.loads(deferred_raw)
    assert child == build() and deferred == build_deferred()
    a, b = tables(parent), tables(child)
    assert a.keys() == b.keys()
    changes = {name: {"before": a[name]["instances"][0]["rows"],
                      "after": b[name]["instances"][0]["rows"]}
               for name in sorted(a) if a[name] != b[name]}
    assert set(changes) == {"ProblemDescription", "MissionType"}
    assert changes["ProblemDescription"]["before"] == [
        ["G05 unavailable preferred branch under online maintenance"]]
    assert changes["ProblemDescription"]["after"] == [
        ["G06 fixed mission ONLM Y direct CM counterexample"]]
    columns = [column["name"] for column in a["MissionType"]["columns"]]
    before, after = changes["MissionType"]["before"], changes["MissionType"]["after"]
    assert len(before) == len(after) == 1
    mpat, descr = columns.index("MPAT"), columns.index("DESCR")
    tfout, tfret = columns.index("TFOUT"), columns.index("TFRET")
    assert before[0][mpat] == "CONTINUOUS" and after[0][mpat] is None
    assert before[0][tfout] is before[0][tfret] is None
    assert after[0][tfout] == after[0][tfret] == 0.25
    assert before[0][descr] == "26-hour continuous standby-selection diagnostic mission"
    assert after[0][descr] == "26-hour fixed online direct CM counterexample mission"
    assert all(before[0][i] == after[0][i] for i in range(len(columns)) if i not in {mpat, descr, tfout, tfret})
    c, d = tables(child), tables(deferred)
    assert c.keys() == d.keys()
    pair = {name: {"before": c[name]["instances"][0]["rows"],
                   "after": d[name]["instances"][0]["rows"]}
            for name in sorted(c) if c[name] != d[name]}
    assert set(pair) == {"ProblemDescription", "RBDParallel"}
    assert pair["ProblemDescription"]["before"] == [["G06 fixed mission ONLM Y direct CM counterexample"]]
    assert pair["ProblemDescription"]["after"] == [["G06 fixed mission ONLM N direct CM control"]]
    rcols = [column["name"] for column in c["RBDParallel"]["columns"]]
    rbefore, rafter = pair["RBDParallel"]["before"], pair["RBDParallel"]["after"]
    assert len(rbefore) == len(rafter) == 1
    onlm = rcols.index("ONLM")
    assert rbefore[0][onlm] == "Y" and rafter[0][onlm] == "N"
    assert all(rbefore[0][i] == rafter[0][i] for i in range(len(rcols)) if i != onlm)
    result = {"schema": "simlox-g06-fixed-online-counterexample-exact-diff/v1",
              "parent_sha256": PARENT_SHA256, "source_sha256": sha(child_raw),
              "deferred_sha256": sha(deferred_raw),
              "parent_to_fixed": changes, "fixed_y_to_n": pair}
    data = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    output = HERE / "exact-diff.json"
    if args.write:
        if output.exists():
            raise FileExistsError(output)
        output.write_bytes(data)
    elif output.read_bytes() != data:
        raise ValueError("frozen G06 fixed exact diff differs")
    print(json.dumps({"changed_tables": sorted(changes), "sha256": sha(data)}))


if __name__ == "__main__":
    main()
