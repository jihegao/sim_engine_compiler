"""Verify only RISK MissionType.SYACF and description differ."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D08-var01-mff-contrast-v1.0.0/native-input-default.json"
OUT = HERE / "exact-diff.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def keyed(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    result = {t["name"]: t for t in doc["model"]["tables"]}
    assert len(result) == len(doc["model"]["tables"])
    return result


def fields(table: dict) -> list[dict]:
    cols = [c["name"] for c in table["columns"]]
    return [dict(zip(cols, row)) for inst in table["instances"] for row in inst["rows"]]


def main() -> None:
    parent = keyed(PARENT)
    arms = {a: keyed(HERE / f"native-input-{a}.json") for a in ("yes", "no")}
    assert len(parent) == 31 and all(set(child) == set(parent) for child in arms.values())
    changes = {}
    for arm, child in arms.items():
        change = []
        for name in parent:
            before, after = fields(parent[name]), fields(child[name])
            assert len(before) == len(after)
            for row_index, (old, new) in enumerate(zip(before, after)):
                for field in old:
                    if old[field] != new[field]:
                        change.append({"table": name, "row": row_index, "field": field, "before": old[field], "after": new[field]})
        assert len(change) == 2
        assert {(c["table"], c["field"]) for c in change} == {("ProblemDescription", "PDESC"), ("MissionType", "SYACF")}
        syacf = next(c for c in change if c["table"] == "MissionType")
        assert syacf["row"] == 1 and syacf["before"] is None and syacf["after"] == ("Y" if arm == "yes" else "N")
        changes[arm] = change
    assert all(arms["yes"][n] == arms["no"][n] for n in parent if n not in ("ProblemDescription", "MissionType"))
    result = {"schema": "simlox-d08-var04-syacf-exact-diff/v1", "parent_sha256": sha(PARENT), "source_sha256": {a: sha(HERE / f"native-input-{a}.json") for a in arms}, "changes_from_parent": changes, "unchanged_tables": 29, "pairwise_business_difference": {"table": "MissionType", "row": 1, "field": "SYACF", "yes": "Y", "no": "N"}}
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if len(sys.argv) == 2 and sys.argv[1] == "--write":
        if OUT.exists():
            raise FileExistsError(OUT)
        OUT.write_bytes(raw)
    else:
        assert len(sys.argv) == 1 and OUT.read_bytes() == raw
    print(json.dumps(result))


if __name__ == "__main__":
    main()
