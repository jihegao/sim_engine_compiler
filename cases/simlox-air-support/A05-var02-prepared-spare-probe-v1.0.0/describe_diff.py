"""Record and replay the exact B01 preparation addition to the A05 parent."""
from __future__ import annotations

import argparse
import json

from build import HERE, OUT as INPUT, PARENT, PARENT_SHA, PREP_SOURCE, PREP_SOURCE_SHA, build, sha

OUT = HERE / "exact-diff.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if sha(PARENT.read_bytes()) != PARENT_SHA or sha(PREP_SOURCE.read_bytes()) != PREP_SOURCE_SHA:
        raise ValueError("accepted source fingerprint differs")
    parent = json.loads(PARENT.read_text(encoding="utf-8"))
    child = json.loads(INPUT.read_text(encoding="utf-8"))
    if child != build():
        raise ValueError("frozen input differs")
    before = {t["name"]: t for t in parent["model"]["tables"]}
    after = {t["name"]: t for t in child["model"]["tables"]}
    if set(before) != set(after):
        raise ValueError("table set differs")
    changed = {name: {"before": before[name], "after": after[name]}
               for name in before if before[name] != after[name]}
    if set(changed) != {"ProblemDescription", "MissionPreparation", "Tasks"}:
        raise ValueError("unexpected table delta")
    result = {"schema": "simlox-a05-var02-prepared-spare-exact-diff/v1",
              "parent_sha256": PARENT_SHA, "preparation_source_sha256": PREP_SOURCE_SHA,
              "child_sha256": sha(INPUT.read_bytes()), "changed_tables_only": list(changed),
              "unchanged_table_count": len(before) - len(changed),
              "changed_tables": changed, "publication_state": "not_published"}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if args.write:
        if OUT.exists():
            raise FileExistsError(OUT)
        OUT.write_bytes(raw)
    elif OUT.read_bytes() != raw:
        raise ValueError("frozen diff differs")
    print(json.dumps({"diff_sha256": sha(raw), "changed_tables": list(changed)}))


if __name__ == "__main__":
    main()
