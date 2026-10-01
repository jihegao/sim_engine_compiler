"""Freeze the exact long-switchover input delta from accepted G05."""
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
    assert set(changes) == {"ProblemDescription", "RBDParallel"}
    before, after = changes["RBDParallel"]["before"][0], changes["RBDParallel"]["after"][0]
    assert before[:4] == after[:4] and before[4] == 0.5 and after[4] == 8.3 and before[5:] == after[5:]
    result = {"schema": "simlox-g05-activation-clock-exact-diff/v1",
              "parent_sha256": PARENT_SHA256, "source_sha256": sha(child_raw), "parent_to_long": changes}
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
