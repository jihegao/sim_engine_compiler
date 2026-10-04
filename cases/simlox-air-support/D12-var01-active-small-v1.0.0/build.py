"""Freeze two D12.var01 inputs with the small PM working at the larger PM due."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

case = Path(__file__).resolve().parent
parent = case.parent / "D12-var01-pm-relation-v1.0.1"
parent_hashes = {
    "unlinked": "0ab5e27ea0756fe7de2acdfdaba664d5d66441e170d494c4ac9d0209c3f11567",
    "linked": "db0544d6fcaba2b5357f6fd0b9d462991f2982432ae20d5b061eff908dad9041",
}


def edit(table: dict, key: str, old, new) -> None:
    columns = [column["name"] for column in table["columns"]]
    index = columns.index(key)
    rows = [row for instance in table["instances"] for row in instance["rows"]]
    matches = [row for row in rows if row[index] == old]
    assert len(matches) == 1, (table["name"], key, old, len(matches))
    matches[0][index] = new


for arm in ("unlinked", "linked"):
    source = parent / f"{arm}-input.json"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == parent_hashes[arm]
    document = json.loads(source.read_text(encoding="utf-8"))
    tables = {table["name"]: table for table in document["model"]["tables"]}
    assert len(tables) == len(document["model"]["tables"]) == 31
    description = tables["ProblemDescription"]["instances"][0]["rows"][0]
    assert description[0] == f"D12.var01 {arm} large/small PM relation"
    description[0] = f"D12.var01 {arm} active-small PM boundary"
    edit(tables["MaterielPM"], "PMID", "BIG47", "BIG48P5")
    edit(tables["MaterielPM"], "DESCR", "47-hour larger service", "48.5-hour larger service")
    edit(tables["MaterielPM"], "PMINT", 47.0, 48.5)
    edit(tables["PMLocation"], "PMID", "BIG47", "BIG48P5")
    edit(tables["PMLocation"], "TID", "PM-BIG47", "PM-BIG48P5")
    edit(tables["Tasks"], "TID", "PM-BIG47", "PM-BIG48P5")
    edit(tables["TaskBreakDown"], "TID", "PM-BIG47", "PM-BIG48P5")
    edit(tables["SubTaskResource"], "TID", "PM-BIG47", "PM-BIG48P5")
    output = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    target = case / f"{arm}-input.json"
    if target.exists():
        assert target.read_bytes() == output, f"frozen {arm} source differs"
    else:
        target.write_bytes(output)
    print(arm, hashlib.sha256(output).hexdigest())
