"""Freeze a three-arm personnel transfer experiment from accepted C03 staffing-2."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C03-shared-crew-formation-v1.0.2" / "inputs" / "staffing-2.json"
PARENT_SHA = "83b454bd145621f36571a87cdf8abcbccc184f07ab8f9ad5f3111651c78881e0"
assert hashlib.sha256(PARENT.read_bytes()).hexdigest() == PARENT_SHA


def rows(table: dict) -> list:
    assert len(table["instances"]) == 1
    return table["instances"][0]["rows"]


def make(arm: str) -> str:
    assert arm in ("control", "out", "out_in")
    doc = json.loads(PARENT.read_text(encoding="utf-8-sig"))
    tables = doc["model"]["tables"]
    by_name = {table["name"]: table for table in tables}
    assert len(by_name) == len(tables)
    assert [col["name"] for col in by_name["OperationProfile"]["columns"]] == [
        "PRID", "SPRID", "STIM", "ITYPE", "IQTY", "IQTYD", "IPER", "IDISP", "DTIM", "XCOORD", "YCOORD", "NOTE"
    ]
    profile = rows(by_name["OperationProfile"])
    assert profile == [["BASIC-SCHEDULE", "BASIC-MISSION", 8.0, "SCHEDULED", 1, None, 0, None, 1.0, None, None, None]]
    second = profile[0].copy()
    second[2] = 20.0
    profile.append(second)
    assert rows(by_name["ResourceAllocation"]) == [["AIR_BASIC", "P-CREW", "BASE-01", 2, None]]
    assert rows(by_name["ProblemDescription"]) == [["C03 two-aircraft shared-crew formation; no J35/F35 equivalence"]]
    rows(by_name["ProblemDescription"])[0][0] = f"I03.var01 {arm}: second formation at h20; crew transfer comparison"
    transfer = {
        "name": "ResourceTransfer",
        "columns": [
            {"name": name, "datatype": dtype, **({"key": True} if name in ("STFID", "STTID", "RID", "TFTIME") else {})}
            for name, dtype in (
                ("STFID", "string"), ("STTID", "string"), ("RID", "string"),
                ("TFTIME", "double"), ("TFQTY", "integer"), ("TFDT", "double"), ("NOTE", "string")
            )
        ],
        "instances": [{"instance_name": "", "rows": {
            "control": [[None] * 7],
            "out": [["BASE-01", "<OUTSIDE>", "P-CREW", 7.75, 1, 0.0, None]],
            "out_in": [
                ["BASE-01", "<OUTSIDE>", "P-CREW", 7.75, 1, 0.0, None],
                ["<OUTSIDE>", "BASE-01", "P-CREW", 10.0, 1, 0.5, None],
            ],
        }[arm]}],
    }
    tables.insert(tables.index(by_name["ResourceAllocation"]) + 1, transfer)
    out = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    target = HERE / f"{arm}-input.json"
    if target.exists():
        assert target.read_bytes() == out, f"frozen {arm} source differs"
    else:
        target.write_bytes(out)
    return hashlib.sha256(out).hexdigest()


if __name__ == "__main__":
    for arm in ("control", "out", "out_in"):
        print(arm, make(arm))
