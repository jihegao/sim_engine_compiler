"""Freeze and replay A05 parent/control/shortage table deltas."""
from __future__ import annotations

import argparse
import json

from build import HERE, PARENT, PARENT_SHA, NAMES, build, sha

OUT = HERE / "exact-diffs.json"
PAIRS = [
    ("A03_to_fixed", "parent", "fixed", {"ProblemDescription", "Unit", "MissionType", "Control", "ResultCollection"}),
    ("fixed_to_continuous", "fixed", "continuous", {"ProblemDescription", "MissionType"}),
    ("continuous_to_shortage", "continuous", "shortage", {"ProblemDescription", "Unit", "SystemDeployment"}),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    docs = {"parent": json.loads(PARENT.read_text(encoding="utf-8"))}
    docs.update({key: json.loads((HERE / name).read_text(encoding="utf-8")) for key, name in NAMES.items()})
    if sha(PARENT.read_bytes()) != PARENT_SHA or {k: docs[k] for k in NAMES} != build():
        raise ValueError("frozen A05 source differs")
    deltas = {}
    for label, left, right, expected in PAIRS:
        before = {t["name"]: t for t in docs[left]["model"]["tables"]}
        after = {t["name"]: t for t in docs[right]["model"]["tables"]}
        changed = {name: {"before": before[name], "after": after[name]}
                   for name in before if before[name] != after.get(name)}
        if set(before) != set(after) or set(changed) != expected:
            raise ValueError(f"unexpected {label} delta: {list(changed)}")
        deltas[label] = {"before_sha256": sha(PARENT.read_bytes()) if left == "parent" else sha((HERE / NAMES[left]).read_bytes()),
                         "after_sha256": sha((HERE / NAMES[right]).read_bytes()),
                         "changed_tables_only": list(changed), "unchanged_table_count": len(before) - len(changed),
                         "changed_tables": changed}
    result = {"schema": "simlox-a05-v101-exact-diffs/v1", "case_id": "A05",
              "version": "1.0.1-candidate", "deltas": deltas, "publication_state": "not_published"}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUT.exists():
            raise FileExistsError(OUT)
        OUT.write_bytes(raw)
    elif OUT.read_bytes() != raw:
        raise ValueError("frozen exact diff differs")
    print(json.dumps({"diff_sha256": sha(raw),
                      "changed_tables": {k: v["changed_tables_only"] for k, v in deltas.items()}}))


if __name__ == "__main__":
    main()
