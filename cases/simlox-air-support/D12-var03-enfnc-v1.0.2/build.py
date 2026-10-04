"""Freeze the D12.var03 explicit noncritical repair versus noncritical PM pair."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

case = Path(__file__).resolve().parent
parent = case.parent / "D08-var03-criticality-v1.0.0/native-input-failure-mode.json"
assert hashlib.sha256(parent.read_bytes()).hexdigest() == "36d20f6be3bcb877ff925542aa2a3f95324a7e1562ed57f18c1561fba27fe59e"
base = json.loads(parent.read_text(encoding="utf-8"))
tables = {table["name"]: table for table in base["model"]["tables"]}
assert len(tables) == len(base["model"]["tables"]) == 35


def append_row(name: str, values: dict) -> None:
    table = tables[name]
    columns = [column["name"] for column in table["columns"]]
    assert set(values) <= set(columns)
    assert len(table["instances"]) == 1 and table["instances"][0]["instance_name"] == ""
    table["instances"][0]["rows"].append([values.get(column) for column in columns])


def set_cell(name: str, row_index: int, column: str, old: object, new: object) -> None:
    table = tables[name]
    index = [item["name"] for item in table["columns"]].index(column)
    row = table["instances"][0]["rows"][row_index]
    assert row[index] == old, (name, row_index, column, row[index])
    row[index] = new


# The accepted D08.var03 explicit failure-mode child already produces one
# noncritical FM-POS-A failure during the first mission. Create an overlapping
# noncritical calendar PM while the aircraft is still on that mission.
set_cell("Control", 0, "ENPM", "N", "Y")
set_cell("Control", 0, "SIMPE", 36.0, 14.0)
set_cell("Control", 0, "RCEND", 36.0, 14.0)
set_cell("ResultCollection", 0, "RCEND", 36.0, 14.0)
set_cell("ResultCollection", 1, "RCEND", 36.0, 14.0)
# v1.0.1 had no native failure during the single retained mission. Raise the
# explicit mode's rate equally in both arms to create the required competition.
set_cell("FailureMode", 0, "FRQ", 300000.0, 3000000.0)
# The native converter rejects scheduled missions beyond a shortened horizon.
profile_rows = tables["OperationProfile"]["instances"][0]["rows"]
assert len(profile_rows) == 3 and [row[2] for row in profile_rows] == [8.0, 20.0, 32.0]
del profile_rows[1:]
set_cell("CMLocation", 0, "TID", None, "CM-NC")

append_row("Resource", {"RID": "P-MAINT", "DESCR": "One shared maintenance worker", "TYPE": "SPECIAL"})
append_row("ResourceAllocation", {"POINT": "AIR_BASIC", "RID": "P-MAINT", "STID": "BASE-01", "RQTY": 1})
append_row("SubTaskType", {"SUTID": "INSPECT", "DESCR": "Inspection"})
append_row("Tasks", {"TID": "CM-NC", "DESCR": "Half-hour noncritical direct repair"})
append_row("Tasks", {"TID": "PM9P9", "DESCR": "One-hour noncritical calendar service"})
append_row("TaskBreakDown", {"TID": "CM-NC", "SEQ": 1, "SUTID": "<REPAIR>", "DURN": 0.5})
append_row("TaskBreakDown", {"TID": "PM9P9", "SEQ": 1, "SUTID": "INSPECT", "DURN": 1.0})
append_row("SubTaskResource", {"TID": "CM-NC", "SEQ": 1, "RID": "P-MAINT", "QTY": 1, "RPROB": 1.0})
append_row("SubTaskResource", {"TID": "PM9P9", "SEQ": 1, "RID": "P-MAINT", "QTY": 1, "RPROB": 1.0})
append_row("MaterielPM", {
    "PMID": "PM9P9", "DESCR": "9.9-hour noncritical calendar service", "MID": "TEACH-AIR-01",
    "PMINT": 9.9, "OPID": "CALHOURS", "ATIM": 0.0, "DTIM": 0.5, "MNOCC": 1,
})
append_row("PMLocation", {"PMID": "PM9P9", "ID": "TEACH-AIR-01", "STID": "BASE-01", "PMT": 1.0, "TID": "PM9P9"})

for arm in ("n", "y"):
    document = copy.deepcopy(base)
    mapping = {table["name"]: table for table in document["model"]["tables"]}
    mapping["ProblemDescription"]["instances"][0]["rows"][0][0] = f"D12.var03 ENFNC={arm.upper()} noncritical CM versus PM"
    table = mapping["MaterielPM"]
    columns = [column["name"] for column in table["columns"]]
    row = table["instances"][0]["rows"][0]
    assert row[columns.index("PMID")] == "PM9P9"
    assert row[columns.index("ENFNC")] is None
    row[columns.index("ENFNC")] = arm.upper()
    output = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    target = case / f"{arm}-input.json"
    if target.exists():
        assert target.read_bytes() == output, f"frozen {arm} source differs"
    else:
        target.write_bytes(output)
    print(arm, hashlib.sha256(output).hexdigest())
