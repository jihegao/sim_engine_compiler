"""Verify the pinned J35 candidate against a SIMLOX 2017 native roundtrip/run."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


EXPECTED = {
    "candidate": "db9d658f2fe2581613a1a4d1538902623a7823266dd62ae8ee2e6ee3dbc81057",
    "native": "1a8ab2f76171df4ca51a59879d06cd61ee8bd5aa9298a8761f6525a7308a9716",
    "roundtrip": "1f72431cc01120b369bfd0d6e96eb56f21f0e9c8642029ad225caf35c51aa603",
    "result": "8485b98ce8f13edb6cd7cefaa3168e64991be7d07263b08af87dd8d20ff76e1e",
}


def records(model: dict, name: str) -> list[dict]:
    table, = [t for t in model["model"]["tables"] if t["name"] == name]
    columns = [column["name"] for column in table["columns"]]
    return [dict(zip(columns, row, strict=True)) for row in table["instances"][0]["rows"]]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    args = parser.parse_args()
    files = {
        "candidate": args.directory / "j35-page-candidate.json",
        "native": args.directory / "j35-page-candidate.sxi",
        "roundtrip": args.directory / "j35-page-roundtrip.json",
        "result": args.directory / "j35-page-result-raw.json",
    }
    for name, path in files.items():
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != EXPECTED[name]:
            raise ValueError(f"{name} SHA-256 changed: {actual}")
    candidate = json.loads(files["candidate"].read_text(encoding="utf-8-sig"))
    roundtrip = json.loads(files["roundtrip"].read_text(encoding="utf-8-sig"))
    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
    a = {t["name"]: t for t in candidate["model"]["tables"]}
    b = {t["name"]: t for t in roundtrip["model"]["tables"]}
    if a.keys() != b.keys() or any(a[name]["instances"] != b[name]["instances"] for name in a):
        raise ValueError("SIMLOX native roundtrip changed at least one table row")
    assert candidate["model"]["database_version"] == 20160627
    assert len(records(candidate, "Item")) == 423
    assert records(candidate, "SystemDeployment")[0]["QTYPS"] == 8
    assert len(records(candidate, "OperationProfile")) == 104
    assert {row["DTIM"] for row in records(candidate, "OperationProfile")} == {20 / 60}
    assert len(records(candidate, "TaskBreakDown")) == 30
    assert len(records(candidate, "StockAllocation")) == 806
    assert sum(row["STSIZ"] for row in records(candidate, "StockAllocation")) == 501
    assert mapping["omitted_page_requirements"] == [{
        "activity_id": "j35-service-0103", "code": "J35-USE-003",
        "kind": "equipment", "label": "充氧车", "quantity": 1,
        "reason": "No matching source supportResource; excluded from SIMLOX constraints",
    }]
    assert "充氧车" not in {row["DESCR"] for row in records(candidate, "Resource")}
    oxygen_step, = [step for step in mapping["steps"] if step["code"] == "J35-USE-003"]
    oxygen_needs = [row for row in records(candidate, "SubTaskResource")
                    if row["TID"] == oxygen_step["task_id"] and row["SEQ"] == oxygen_step["seq"]]
    assert {row["RID"] for row in oxygen_needs} == {"PERSONNEL", "DEVICE", "P_MECH"}
    assert {row["RID"]: row["QTY"] for row in oxygen_needs} == {"PERSONNEL": 1, "DEVICE": 1, "P_MECH": 1}
    raw = files["result"].read_text(encoding="utf-8-sig")
    # SIMLOX 2017 emits commas before closing arrays. Repair only in memory.
    report = json.loads(re.sub(r",\s*([}\]])", r"\1", raw))
    summary, = records({"model": report["report"]}, "ResultSummary")
    if (summary["NREP"], summary["RTILW"], summary["RTIUP"]) != (1, 0, 1032):
        raise ValueError("unexpected SIMLOX result horizon or repetition count")
    print(json.dumps({
        "table_count": len(a), "native_roundtrip_rows_equal": True,
        "oxygen_step_resource_ids": [row["RID"] for row in oxygen_needs],
        "result_nrep": summary["NREP"], "result_period_hours": [summary["RTILW"], summary["RTIUP"]],
        "result_mtmf": summary["MTMF"], "result_mstf": summary["MSTF"],
        "result_msuf": summary["MSUF"], "result_stmf": summary["STMF"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
