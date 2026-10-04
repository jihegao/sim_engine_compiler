"""Freeze D12.var02 two-link versus three-level PM relation inputs."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

case = Path(__file__).resolve().parent
parent = case.parent / "D12-var01-active-small-v1.0.0/linked-input.json"
assert hashlib.sha256(parent.read_bytes()).hexdigest() == "cddf59ab7d557f6c643138ce8241fa43d7d5a569396538a6934bf7de00b3ffd1"
base = json.loads(parent.read_text(encoding="utf-8"))
tables = {table["name"]: table for table in base["model"]["tables"]}
assert len(tables) == len(base["model"]["tables"]) == 31


def append_row(name: str, values: dict) -> None:
    table = tables[name]
    columns = [column["name"] for column in table["columns"]]
    assert set(values) <= set(columns)
    assert len(table["instances"]) == 1 and table["instances"][0]["instance_name"] == ""
    table["instances"][0]["rows"].append([values.get(column) for column in columns])


append_row("MaterielPM", {
    "PMID": "TOP49", "DESCR": "49-hour top-level service", "MID": "TEACH-AIR-01",
    "PMINT": 49.0, "OPID": "CALHOURS", "ATIM": 0.0, "DTIM": 0.0,
})
append_row("PMLocation", {
    "PMID": "TOP49", "ID": "TEACH-AIR-01", "STID": "BASE-01", "PMT": 1.0, "TID": "PM-TOP49",
})
append_row("Tasks", {"TID": "PM-TOP49", "DESCR": "One-hour top-level service"})
append_row("TaskBreakDown", {"TID": "PM-TOP49", "SEQ": 1, "SUTID": "INSPECT", "DURN": 1.0})
append_row("SubTaskResource", {"TID": "PM-TOP49", "SEQ": 1, "RID": "P-MAINT", "QTY": 1, "RPROB": 1.0})

for arm in ("unlinked", "linked"):
    document = copy.deepcopy(base)
    mapping = {table["name"]: table for table in document["model"]["tables"]}
    description = mapping["ProblemDescription"]["instances"][0]["rows"][0]
    assert description[0] == "D12.var01 linked active-small PM boundary"
    description[0] = f"D12.var02 {arm} TOP49-to-BIG48P5 relation"
    top = mapping["MaterielPM"]["instances"][0]["rows"][-1]
    columns = [column["name"] for column in mapping["MaterielPM"]["columns"]]
    assert top[columns.index("PMID")] == "TOP49"
    assert top[columns.index("PMRID")] is None
    if arm == "linked":
        top[columns.index("PMRID")] = "BIG48P5"
    output = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    target = case / f"{arm}-input.json"
    if target.exists():
        assert target.read_bytes() == output, f"frozen {arm} source differs"
    else:
        target.write_bytes(output)
    print(arm, hashlib.sha256(output).hexdigest())
