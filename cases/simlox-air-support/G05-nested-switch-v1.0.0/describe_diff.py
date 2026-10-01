"""Freeze the exact parent-to-nested G05 topology delta."""
from __future__ import annotations

import argparse
import hashlib
import json

from build import HERE, PARENT, PARENT_SHA256, SOURCE, TEMPLATE, TEMPLATE_SHA256, build


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tables(document: dict) -> dict:
    found = {item["name"]: item for item in document["model"]["tables"]}
    assert len(found) == len(document["model"]["tables"])
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    parent_raw, template_raw, source_raw = PARENT.read_bytes(), TEMPLATE.read_bytes(), SOURCE.read_bytes()
    assert sha(parent_raw) == PARENT_SHA256 and sha(template_raw) == TEMPLATE_SHA256
    parent, child = json.loads(parent_raw), json.loads(source_raw)
    assert child == build()
    before, after = tables(parent), tables(child)
    assert set(after) - set(before) == {"RBDSeries", "RBDSeriesStructure"}
    assert not (set(before) - set(after))
    changed = {name: {"before": before[name]["instances"][0]["rows"],
                      "after": after[name]["instances"][0]["rows"]}
               for name in sorted(before) if before[name] != after[name]}
    assert set(changed) == {"ProblemDescription", "MaterielOperationalModes", "RBDParallel", "RBDParallelStructure"}
    assert changed["RBDParallelStructure"]["after"] == changed["RBDParallelStructure"]["before"][:2]
    assert changed["MaterielOperationalModes"]["after"][1:] == changed["MaterielOperationalModes"]["before"][1:]
    added = {name: after[name] for name in sorted(set(after) - set(before))}
    result = {"schema": "simlox-g05-nested-switch-exact-diff/v1",
              "parent_sha256": PARENT_SHA256, "template_sha256": TEMPLATE_SHA256,
              "source_sha256": sha(source_raw), "changed_tables": changed, "added_tables": added}
    data = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    output = HERE / "exact-diff.json"
    if args.write:
        if output.exists():
            raise FileExistsError(output)
        output.write_bytes(data)
    elif output.read_bytes() != data:
        raise ValueError("frozen exact diff differs")
    print(json.dumps({"changed_tables": sorted(changed), "added_tables": sorted(added),
                      "sha256": sha(data)}))


if __name__ == "__main__":
    main()
