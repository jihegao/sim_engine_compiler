"""Verify SIMLOX's native round trip of the pinned F35 workflow candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def table_rows(document: dict, name: str, *, report: bool = False) -> list[dict]:
    root = document["report"] if report else document["model"]
    tables = [table for table in root["tables"] if table["name"] == name]
    if len(tables) != 1:
        raise ValueError(f"expected one {name} table, got {len(tables)}")
    table = tables[0]
    columns = [column["name"] for column in table["columns"]]
    return [
        dict(zip(columns, row, strict=True))
        for instance in table["instances"]
        for row in instance["rows"]
        if any(value is not None for value in row)
    ]


def assert_roundtrip(candidate: dict, native: dict, mapping: dict) -> dict:
    specs = {
        "System": ("SID",),
        "Item": ("IID",),
        "Tasks": ("TID",),
        "SubTaskType": ("SUTID",),
        "TaskBreakDown": ("TID", "SEQ"),
        "SubTaskResource": ("TID", "SEQ", "RID"),
        "Resource": ("RID",),
        "ResourceAllocation": ("POINT", "RID", "STID"),
        "MissionPreparation": ("MTID", "SID", "STID"),
        "ItemRepair": ("IID", "STID"),
        "SystemRepair": ("SID", "STID"),
        "ItemReplacement": ("MID", "IID", "STID"),
        "MaterielPM": ("PMID",),
        "PMLocation": ("PMID", "ID", "STID"),
    }
    checked_fields = {
        "System": ("SID", "FRT", "OPID", "NOTE"),
        "Item": ("IID", "FRT", "OPID", "NOTE"),
        "Tasks": ("TID", "DESCR", "NOTE"),
        "SubTaskType": ("SUTID", "DESCR", "NOTE"),
        "TaskBreakDown": ("TID", "SEQ", "SUTID", "DURN", "NOTE"),
        "SubTaskResource": ("TID", "SEQ", "RID", "QTY", "RPROB", "NOTE"),
        "Resource": ("RID", "TYPE", "NOTE"),
        "ResourceAllocation": ("POINT", "RID", "STID", "RQTY"),
        "MissionPreparation": ("MTID", "SID", "STID", "DURN", "TID", "NOTE"),
        "ItemRepair": ("IID", "STID", "DIRPT", "DIRPTID", "DIRPF", "SURPF", "NOTE"),
        "SystemRepair": ("SID", "STID", "DIRPT", "SURPT", "DIRPF", "SURPF", "SURPTID", "NOTE"),
        "ItemReplacement": ("MID", "IID", "STID", "SURPT", "SURPF", "SURPTID", "NOTE"),
        "MaterielPM": ("PMID", "MID", "PMINT", "OPID"),
        "PMLocation": ("PMID", "ID", "STID", "PMT", "TID"),
    }
    identifier_fields = {"TID", "SUTID", "RID", "POINT", "MTID", "SID", "STID", "IID", "PMID", "MID", "ID", "OPID", "DIRPTID", "SURPTID"}
    counts = {}
    for name, key_fields in specs.items():
        source_rows = table_rows(candidate, name)
        native_rows = table_rows(native, name)

        def indexed(rows: list[dict]) -> dict:
            result = {}
            for row in rows:
                key = tuple(str(row[field]).upper() for field in key_fields)
                if key in result:
                    raise ValueError(f"duplicate {name} key {key}")
                result[key] = row
            return result

        source_index = indexed(source_rows)
        native_index = indexed(native_rows)
        if source_index.keys() != native_index.keys():
            raise ValueError(f"{name} keys differ on native round trip")
        for key, source in source_index.items():
            actual = native_index[key]
            for field in checked_fields[name]:
                expected_value, actual_value = source.get(field), actual.get(field)
                if isinstance(expected_value, (int, float)) and not isinstance(expected_value, bool):
                    if actual_value is None or abs(expected_value - actual_value) > 1e-9:
                        raise ValueError(f"{name}{key}.{field}: {actual_value} != {expected_value}")
                elif field in identifier_fields:
                    if str(expected_value).upper() != str(actual_value).upper():
                        raise ValueError(f"{name}{key}.{field}: {actual_value!r} != {expected_value!r}")
                elif field == "NOTE" and isinstance(expected_value, str) and isinstance(actual_value, str):
                    if expected_value.strip() != actual_value.strip():
                        raise ValueError(f"{name}{key}.{field}: {actual_value!r} != {expected_value!r}")
                elif expected_value != actual_value:
                    raise ValueError(f"{name}{key}.{field}: {actual_value!r} != {expected_value!r}")
        counts[name] = len(source_rows)
    expected = mapping["counts"]
    for name, value in (
        ("SubTaskType", expected["subtask_types"]),
        ("TaskBreakDown", expected["task_breakdown"]),
        ("SubTaskResource", expected["subtask_resources"]),
        ("ItemRepair", expected["item_repair"]),
        ("ItemReplacement", expected["item_replacement"]),
        ("SystemRepair", expected["system_repair"]),
    ):
        if counts[name] != value:
            raise ValueError(f"unexpected {name} count: {counts[name]} != {value}")
    if counts["Resource"] != 2:
        raise ValueError("resource type rows must be limited to the two accepted pooled capacities")
    # Native floating point serialization may differ at the last bit.
    actual = sum(
        row["DURN"]
        for row in table_rows(native, "TaskBreakDown")
        if row["TID"] == "MISSION_PREP"
    )
    if abs(actual - 142 / 60) > 1e-9:
        raise ValueError(f"preflight duration is {actual}, expected 142/60 hours")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("candidate", "mapping", "native_export", "native_model", "result", "report", "run_log", "output"):
        parser.add_argument("--" + name.replace("_", "-"), required=True, type=Path)
    args = parser.parse_args()
    mapping = load(args.mapping)
    if digest(args.candidate) != mapping["inputs"]["output_json_sha256"]:
        raise ValueError("candidate JSON hash differs from builder ledger")
    candidate, native = load(args.candidate), load(args.native_export)
    counts = assert_roundtrip(candidate, native, mapping)
    log = args.run_log.read_text(encoding="utf-8-sig")
    if "Input conversion completed. Errors: 0, Warnings: 0, Notes: 0" not in log or re.search(r"\(warning #", log, re.I):
        raise ValueError("SIMLOX run log is not warning-free")
    if str(args.native_model.name) not in log or str(args.result.name) not in log:
        raise ValueError("run log does not associate the model and result paths")
    raw_report = args.report.read_text(encoding="utf-8-sig")
    parsed_report = json.loads(re.sub(r",(?=\s*[}\]])", "", raw_report))
    summary = table_rows(parsed_report, "ResultSummary", report=True)
    if len(summary) != 1 or summary[0]["NREP"] != 1 or summary[0]["RTILW"] != 0 or summary[0]["RTIUP"] != 1032:
        raise ValueError("result summary does not match one 1032-hour replication")
    systems = table_rows(parsed_report, "SystemResults", report=True)
    resources = table_rows(parsed_report, "ResourceResults", report=True)
    if not any(row.get("NFAIL", 0) > 0 for row in systems):
        raise ValueError("no failure was exercised; check FRT units")
    if not any(row.get("NSYRP", 0) > 0 for row in systems):
        raise ValueError("no corrective repair was exercised")
    outcome = {
        "status": "native-roundtrip-and-run-verified",
        "counts": counts,
        "report": {
            "replications": summary[0]["NREP"],
            "start_hour": summary[0]["RTILW"],
            "end_hour": summary[0]["RTIUP"],
            "system_rows": len(systems),
            "resource_rows": len(resources),
            "system_failure_rows_nonzero": sum(row.get("NFAIL", 0) != 0 for row in systems),
            "system_pm_rows_nonzero": sum(row.get("NSYPM", 0) != 0 for row in systems),
            "system_repair_rows_nonzero": sum(row.get("NSYRP", 0) != 0 for row in systems),
            "system_waiting_resource_rows_nonzero": sum(row.get("NSYWR", 0) != 0 for row in systems),
            "resource_wait_rows_nonzero": sum(row.get("NRW", 0) != 0 for row in resources),
        },
        "sha256": {
            "candidate_json": digest(args.candidate),
            "native_model": digest(args.native_model),
            "native_export": digest(args.native_export),
            "result": digest(args.result),
            "raw_report": digest(args.report),
            "run_log": digest(args.run_log),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(outcome, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": outcome["status"], "counts": counts, "report": outcome["report"]}))


if __name__ == "__main__":
    main()
