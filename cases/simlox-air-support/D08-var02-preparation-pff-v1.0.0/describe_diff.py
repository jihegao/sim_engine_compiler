"""Verify the exact parent and paired PFF deltas."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "D08-var01-mff-contrast-v1.0.0/native-input-default.json"
OUT = HERE / "exact-diff.json"


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def keyed(doc: dict) -> dict:
    tables = doc["model"]["tables"]
    result = {t["name"]: t for t in tables}
    assert len(result) == len(tables)
    return result


def rows(table: dict) -> list[dict]:
    fields = [c["name"] for c in table["columns"]]
    return [dict(zip(fields, row)) for instance in table["instances"] for row in instance["rows"]]


def main() -> None:
    parent = keyed(read(PARENT))
    arms = {a: keyed(read(HERE / f"native-input-{a}.json")) for a in ("zero", "positive")}
    assert set(arms["zero"]) == set(arms["positive"]) == set(parent) | {"MissionReliability"}
    assert len(parent) == 31
    changes = {}
    for arm, child in arms.items():
        changed = []
        for name in parent:
            if parent[name] != child[name]:
                changed.append(name)
        assert set(changed) == {"ProblemDescription", "MissionPreparation"}
        assert rows(parent["MissionPreparation"]) == []
        assert rows(child["MissionPreparation"]) == [
            {"MTID": "RISK-MISSION", "SID": "TEACH-AIR-01", "STID": "BASE-01", "DURN": 1.0, "TID": None, "DURND": None, "NOTE": None}
        ]
        assert rows(child["MissionReliability"]) == [
            {"MTID": "RISK-MISSION", "SID": "TEACH-AIR-01", "IID": "<SYSTEM>", "MFF": None, "PFF": 0.0 if arm == "zero" else 10.0, "NOTE": None}
        ]
        changes[arm] = {"changed_parent_tables": changed, "added_table": "MissionReliability", "risk_preparation_hours": 1.0, "pff": 0.0 if arm == "zero" else 10.0}
    assert all(arms["zero"][n] == arms["positive"][n] for n in arms["zero"] if n not in ("ProblemDescription", "MissionReliability"))
    result = {
        "schema": "simlox-d08-var02-pff-exact-diff/v1",
        "parent_sha256": sha(PARENT),
        "input_sha256": {a: sha(HERE / f"native-input-{a}.json") for a in arms},
        "changes_from_parent": changes,
        "pairwise_business_difference": {"table": "MissionReliability", "key": ["RISK-MISSION", "TEACH-AIR-01", "<SYSTEM>"], "field": "PFF", "zero": 0.0, "positive": 10.0},
    }
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
