"""Frozen D05-derived paired PM relation inputs for D12.var01."""
import copy
import hashlib
import json
from pathlib import Path

case = Path(__file__).resolve().parent
parent = case.parent / "D05-maintenance-competition-v1.0.0/native-input.json"
assert hashlib.sha256(parent.read_bytes()).hexdigest() == "4443d057ade36010a84186aa0f9ac8279886563db190ed80699b7fe48ad2baad"
base = json.loads(parent.read_text(encoding="utf-8"))
tables = {t["name"]: t for t in base["model"]["tables"]}


def edit_cell(table, row_index, field, expected, replacement):
    tab = tables[table]
    index = [c["name"] for c in tab["columns"]].index(field)
    row = tab["instances"][0]["rows"][row_index]
    assert row[index] == expected, (table, field, row[index], expected)
    row[index] = replacement


def append_row(table, values):
    tab = tables[table]
    columns = [c["name"] for c in tab["columns"]]
    assert set(values) <= set(columns)
    assert len(tab["instances"]) == 1 and tab["instances"][0]["instance_name"] == ""
    tab["instances"][0]["rows"].append([values.get(c) for c in columns])


edit_cell("Control", 0, "SIMPE", 36.0, 60.0)
edit_cell("Control", 0, "RCEND", 36.0, 60.0)
edit_cell("ResultCollection", 0, "RCEND", 36.0, 60.0)
edit_cell("ResultCollection", 1, "RCEND", 36.0, 60.0)
edit_cell("MaterielPM", 0, "ENREG", None, "Y")
append_row("MaterielPM", {
    "PMID": "BIG47", "DESCR": "47-hour larger service", "MID": "TEACH-AIR-01",
    "PMINT": 47.0, "OPID": "CALHOURS", "ATIM": 0.0, "DTIM": 0.0,
})
append_row("PMLocation", {
    "PMID": "BIG47", "ID": "TEACH-AIR-01", "STID": "BASE-01", "PMT": 1.0, "TID": "PM-BIG47",
})
append_row("Tasks", {"TID": "PM-BIG47", "DESCR": "One-hour larger service"})
append_row("TaskBreakDown", {"TID": "PM-BIG47", "SEQ": 1, "SUTID": "INSPECT", "DURN": 1.0})
append_row("SubTaskResource", {"TID": "PM-BIG47", "SEQ": 1, "RID": "P-MAINT", "QTY": 1, "RPROB": 1.0})

for arm in ("unlinked", "linked"):
    document = copy.deepcopy(base)
    mapping = {t["name"]: t for t in document["model"]["tables"]}
    description = mapping["ProblemDescription"]["instances"][0]["rows"][0]
    description[0] = f"D12.var01 {arm} large/small PM relation"
    large = mapping["MaterielPM"]["instances"][0]["rows"][1]
    pmrid = [c["name"] for c in mapping["MaterielPM"]["columns"]].index("PMRID")
    assert large[pmrid] is None
    if arm == "linked":
        large[pmrid] = "CAL24"
    data = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path = case / f"{arm}-input.json"
    if path.exists():
        assert path.read_bytes() == data, f"frozen {arm} source differs"
    else:
        path.write_bytes(data)
    print(arm, hashlib.sha256(data).hexdigest())
