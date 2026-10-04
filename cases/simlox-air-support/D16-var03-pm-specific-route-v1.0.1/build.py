"""Freeze a paired PM-specific transport link from accepted D12 remote PM."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

CASE = Path(__file__).resolve().parent
PARENT = CASE.parent / "D12-var04-remote-critical-v1.0.1" / "remote-input.json"
PARENT_SHA = "455161e25213ad009e21b488a745d6d17af828d8c1a4e44f42b75c980a6a3634"
assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA


def rows(table: dict) -> list:
    assert len(table["instances"]) == 1
    return table["instances"][0]["rows"]


def make(arm: str) -> str:
    assert arm in ("default", "pm_specific")
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    tables = doc["model"]["tables"]
    by_name = {table["name"]: table for table in tables}
    assert len(by_name) == len(tables) == 31
    station = by_name["StationStructure"]
    assert rows(station) == [["BASE-01", "BASE-02", 0.25, 0.25, None, None, 1, "SLOW", None, None, None]]
    pm = by_name["PMLocation"]
    pm_cols = [column["name"] for column in pm["columns"]]
    assert any(row[pm_cols.index("PMID")] == "CAL24" and row[pm_cols.index("STID")] == "BASE-02" for row in rows(pm))
    assert [column["name"] for column in by_name["ProblemDescription"]["columns"]] == ["PDESC"]
    rows(by_name["ProblemDescription"])[0][0] = f"D16.var03 {arm} remote CAL24 PM route"

    route = {
        "name": "PMStationStructure",
        "columns": [
            {"name": name, "datatype": datatype, **({"key": True} if name in ("PMID", "ID", "STID", "MSTID") else {})}
            for name, datatype in (
                ("PMID", "string"), ("ID", "string"), ("STID", "string"), ("MSTID", "string"),
                ("TFRMS", "double"), ("TTOMS", "double"), ("CFRMS", "double"),
                ("CTOMS", "double"), ("DFRAC", "double"),
                ("OPOL", "string"), ("PFRMS", "string"), ("PTOMS", "string"), ("NOTE", "string"),
            )
        ],
        "instances": [{"instance_name": "", "rows": []}],
    }
    if arm == "default":
        rows(route).append([None] * 13)
    else:
        rows(route).append(["CAL24", "TEACH-AIR-01", "BASE-01", "BASE-02", 1.0, 1.0,
                            None, None, 1.0, "SLOW", None, None, None])
    insert_at = tables.index(station) + 1
    tables.insert(insert_at, route)
    out = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    target = CASE / f"{arm}-input.json"
    if target.exists():
        assert target.read_bytes() == out, f"frozen {arm} source differs"
    else:
        target.write_bytes(out)
    return hashlib.sha256(out).hexdigest()


if __name__ == "__main__":
    for arm in ("default", "pm_specific"):
        print(arm, make(arm))
