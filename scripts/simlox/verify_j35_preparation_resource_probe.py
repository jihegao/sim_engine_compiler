"""Verify isolated SIMLOX J35 preparation-resource and deferment probes."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


FILES = {
    "baseline_model": ("j35-page-candidate.json", "db9d658f2fe2581613a1a4d1538902623a7823266dd62ae8ee2e6ee3dbc81057"),
    "baseline_roundtrip": ("j35-page-roundtrip.json", "1f72431cc01120b369bfd0d6e96eb56f21f0e9c8642029ad225caf35c51aa603"),
    "baseline_report": ("j35-page-result-raw.json", "8485b98ce8f13edb6cd7cefaa3168e64991be7d07263b08af87dd8d20ff76e1e"),
    "arm1_model": ("j35-p-arm1-dtim20-probe.json", "5493bad0310778788353027582a4342a163c7e18feaf0e4e63a76043a6d8d904"),
    "arm1_roundtrip": ("j35-p-arm1-dtim20-roundtrip.json", "f7a2568afabf215026a364ccce61d1ac9f880189ad4b6483807c91330258a9f8"),
    "arm1_report": ("j35-p-arm1-dtim20-result-raw.json", "b8b4736bb5a01977f1c35745add193efcdd170fe587eb37070525e5a35957e9f"),
    "arm1_no_defer_model": ("j35-p-arm1-probe.json", "457b1c8b4a3071bfb3db6ff1158fcf5855356784622e86171d78c5dcc8ae1385"),
    "arm1_no_defer_roundtrip": ("j35-p-arm1-roundtrip.json", "5b592db1e897b402fefb82cdef53cfdf99b9ab2405eb9a8c9eb2b6ffe33cb65d"),
    "arm1_no_defer_report": ("j35-p-arm1-result-raw.json", "41257e6be572354bef8a8f4e425acf396a4488b137b2d266d03d7e8743973121"),
}


def rows(payload: dict, container: str, name: str) -> list[dict]:
    table, = [item for item in payload[container]["tables"] if item["name"] == name]
    columns = [item["name"] for item in table["columns"]]
    return [dict(zip(columns, row, strict=True)) for row in table["instances"][0]["rows"]]


def model_differences(a: dict, b: dict) -> list[dict]:
    differences = []
    a_tables = {table["name"]: table for table in a["model"]["tables"]}
    b_tables = {table["name"]: table for table in b["model"]["tables"]}
    assert a_tables.keys() == b_tables.keys()
    for name, table in a_tables.items():
        peer = b_tables[name]
        assert table["columns"] == peer["columns"]
        columns = [column["name"] for column in table["columns"]]
        left = table["instances"][0]["rows"]
        right = peer["instances"][0]["rows"]
        assert len(left) == len(right)
        for index, (old, new) in enumerate(zip(left, right, strict=True)):
            differences.extend({"table": name, "row": index, "column": column, "from": before, "to": after}
                               for column, before, after in zip(columns, old, new, strict=True) if before != after)
    return differences


def report_counts(payload: dict) -> dict:
    summary, = rows(payload, "report", "ResultSummary")
    resource_rows = rows(payload, "report", "ResourceResults")
    assert (summary["NREP"], summary["RTILW"], summary["RTIUP"], len(resource_rows)) == (1, 0, 1032, 2064)
    started = round(summary["MSTF"] * 104)
    successful = round(summary["MSUF"] * 104)
    assert abs(summary["MSTF"] - started / 104) < 1e-6
    assert abs(summary["MSUF"] - successful / 104) < 1e-6
    return {"planned": 104, "started": started, "successful": successful,
            "intervals_with_resource_queue": sum(row["NRW"] > 0 for row in resource_rows),
            "resource_queue_item_hours": sum(row["NRW"] * (row["ETINT"] - row["STINT"])
                                             for row in resource_rows)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payloads = {}
    fingerprints = {}
    for label, (name, expected) in FILES.items():
        raw = (args.directory / name).read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        if actual != expected:
            raise ValueError(f"{name} SHA-256 changed: {actual}")
        fingerprints[label] = actual
        decoded = raw.decode("utf-8-sig")
        if label.endswith("report"):
            # SIMLOX 2017 exports trailing commas; leave the raw evidence untouched.
            decoded = re.sub(r",\s*([}\]])", r"\1", decoded)
        payloads[label] = json.loads(decoded)

    for prefix in ("baseline", "arm1", "arm1_no_defer"):
        if model_differences(payloads[f"{prefix}_model"], payloads[f"{prefix}_roundtrip"]):
            raise ValueError(f"{prefix} changed during native roundtrip")
    baseline = payloads["baseline_model"]
    arm1 = payloads["arm1_model"]
    no_defer = payloads["arm1_no_defer_model"]
    changes = model_differences(baseline, arm1)
    assert len(changes) == 2
    assert {(change["table"], change["column"]) for change in changes} == {
        ("ResourceAllocation", "RQTY"), ("ResourceAllocation", "NOTE")}
    allocation = [change for change in changes if change["column"] == "RQTY"]
    assert len(allocation) == 1 and (allocation[0]["from"], allocation[0]["to"]) == (10, 1)
    assert rows(baseline, "model", "ResourceAllocation")[allocation[0]["row"]]["RID"] == "P_ARM"
    assert {row["TID"] for row in rows(baseline, "model", "SubTaskResource") if row["RID"] == "P_ARM"} == {"MISSION_PREP"}
    assert not [row for row in rows(baseline, "model", "TaskResource") if row["RID"] == "P_ARM"]
    defer_changes = model_differences(no_defer, arm1)
    assert len(defer_changes) == 104
    assert {(change["table"], change["column"], change["from"], change["to"])
            for change in defer_changes} == {("OperationProfile", "DTIM", None, 20 / 60)}

    results = {prefix: report_counts(payloads[f"{prefix}_report"])
               for prefix in ("baseline", "arm1", "arm1_no_defer")}
    assert [(results[prefix]["started"], results[prefix]["successful"],
             results[prefix]["intervals_with_resource_queue"])
            for prefix in ("baseline", "arm1", "arm1_no_defer")] == [
                (92, 79, 0), (26, 25, 310), (12, 12, 312)]
    output = {"fingerprints": fingerprints,
              "isolated_changes": {"resource": "P_ARM capacity 10 -> 1, plus explanatory NOTE",
                                   "deferment": "104 OperationProfile.DTIM values NULL -> 20/60 hours"},
              "resource_use_scope": "P_ARM only in MISSION_PREP SubTaskResource",
              "native_roundtrip_rows_equal": True, "results": results,
              "limit": "aggregate queues and fixed-mission fractions; no per-mission delay or cross-engine event parity"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False))


if __name__ == "__main__":
    main()
