"""Freeze the exact G05 ONLM=Y to G06 ONLM=N source delta."""
from __future__ import annotations

import argparse
import hashlib
import json

from build import HERE, PARENT, PARENT_SHA256, SOURCE, build


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
    parent_raw, child_raw = PARENT.read_bytes(), SOURCE.read_bytes()
    assert sha(parent_raw) == PARENT_SHA256
    parent, child = json.loads(parent_raw), json.loads(child_raw)
    assert child == build()
    a, b = tables(parent), tables(child)
    assert a.keys() == b.keys()
    changes = {name: {"before": a[name]["instances"][0]["rows"],
                      "after": b[name]["instances"][0]["rows"]}
               for name in sorted(a) if a[name] != b[name]}
    assert set(changes) == {"ProblemDescription", "RBDParallel"}
    assert changes["ProblemDescription"]["before"] == [
        ["G05 unavailable preferred branch under online maintenance"]]
    assert changes["ProblemDescription"]["after"] == [
        ["G06 continuous passive direct CM deferred ONLM N"]]
    columns = [column["name"] for column in a["RBDParallel"]["columns"]]
    before, after = changes["RBDParallel"]["before"], changes["RBDParallel"]["after"]
    assert len(before) == len(after) == 1
    onlm = columns.index("ONLM")
    assert before[0][onlm] == "Y" and after[0][onlm] == "N"
    assert all(before[0][i] == after[0][i] for i in range(len(columns)) if i != onlm)
    result = {"schema": "simlox-g06-online-direct-cm-exact-diff/v1",
              "parent_sha256": PARENT_SHA256, "source_sha256": sha(child_raw),
              "parent_to_deferred": changes}
    data = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    output = HERE / "exact-diff.json"
    if args.write:
        if output.exists():
            raise FileExistsError(output)
        output.write_bytes(data)
    elif output.read_bytes() != data:
        raise ValueError("frozen G06 exact diff differs")
    print(json.dumps({"changed_tables": sorted(changes), "sha256": sha(data)}))


if __name__ == "__main__":
    main()
