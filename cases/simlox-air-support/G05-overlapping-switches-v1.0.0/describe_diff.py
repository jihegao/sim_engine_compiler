"""Freeze the parent-to-four-branch and short-to-long G05 deltas."""
from __future__ import annotations

import argparse
import hashlib
import json

from build import ARMS, HERE, PARENT, PARENT_SHA256, build


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tables(document: dict) -> dict:
    found = {item["name"]: item for item in document["model"]["tables"]}
    assert len(found) == len(document["model"]["tables"])
    return found


def difference(before: dict, after: dict) -> dict:
    a, b = tables(before), tables(after)
    assert a.keys() == b.keys()
    return {name: {"before": a[name]["instances"][0]["rows"],
                   "after": b[name]["instances"][0]["rows"]}
            for name in sorted(a) if a[name] != b[name]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    raw = PARENT.read_bytes()
    assert sha(raw) == PARENT_SHA256
    parent = json.loads(raw)
    arms = {}
    for arm in ARMS:
        source = (HERE / f"{arm}-input.json").read_bytes()
        assert json.loads(source) == build(arm)
        arms[arm] = {"document": json.loads(source), "sha256": sha(source)}
    parent_to_short = difference(parent, arms["short"]["document"])
    assert set(parent_to_short) == {"ProblemDescription", "MaterielPosition", "MaterielStructure",
                                    "MaterielOperationalModes", "RBDParallel", "RBDParallelStructure"}
    short_to_long = difference(arms["short"]["document"], arms["long"]["document"])
    assert set(short_to_long) == {"ProblemDescription", "RBDParallel"}
    b, a = short_to_long["RBDParallel"]["before"][0], short_to_long["RBDParallel"]["after"][0]
    assert b[:4] == a[:4] and b[4] == 0.5 and a[4] == 4.0 and b[5:] == a[5:]
    result = {"schema": "simlox-g05-overlapping-switches-exact-diff/v1",
              "parent_sha256": PARENT_SHA256,
              "short_sha256": arms["short"]["sha256"], "long_sha256": arms["long"]["sha256"],
              "parent_to_short": parent_to_short, "short_to_long": short_to_long}
    data = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    output = HERE / "exact-diff.json"
    if args.write:
        if output.exists():
            raise FileExistsError(output)
        output.write_bytes(data)
    elif output.read_bytes() != data:
        raise ValueError("frozen exact diff differs")
    print(json.dumps({"parent_to_short": sorted(parent_to_short),
                      "short_to_long": sorted(short_to_long), "sha256": sha(data)}))


if __name__ == "__main__":
    main()
