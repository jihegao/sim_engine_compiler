"""Author replay of F04.var03 first-cycle System-only collection window."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import statistics

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN = HERE / "runs" / "f04-var03-system-window-v101-ssh-20261004-01"
PARENT_RUN = ROOT / "F04-var02-stochastic-43day-v1.0.0" / "runs" / "f04-var02-stochastic-v100-repeat-a-ssh-20261004-01"
EXCLUDED_RUN = ROOT / "F04-var03-first-cycle-window-v1.0.0" / "runs" / "f04-var03-first-cycle-v100-ssh-20261004-01"
RAW = {
    "input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log",
    "model.sxo", "run.log", "model.log", "report-raw.json", "report-export.log",
    "replication-report-raw.json", "replication-report-export.log",
    "steps.json", "roundtrip-validation.json",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_json(path: Path) -> tuple[dict, bool]:
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw), False
    except json.JSONDecodeError:
        out: list[str] = []
        quoted = escaped = False
        n = len(raw)
        for i, char in enumerate(raw):
            if quoted:
                out.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
                out.append(char)
            elif char == ",":
                j = i + 1
                while j < n and raw[j].isspace():
                    j += 1
                if j >= n or raw[j] not in "]}":
                    out.append(char)
            else:
                out.append(char)
        return json.loads("".join(out)), True


def rows(report: dict, name: str) -> list[dict]:
    found = [t for t in report["report"]["tables"] if t["name"] == name]
    assert len(found) == 1, name
    table = found[0]
    names = [column["name"] for column in table["columns"]]
    return [dict(zip(names, record))
            for instance in table["instances"] for record in instance["rows"]]


def tables(report: dict) -> dict:
    result = {table["name"]: table for table in report["report"]["tables"]}
    assert len(result) == len(report["report"]["tables"])
    return result


def close(a: float, b: float, tol: float = 2e-5) -> bool:
    return math.isclose(a, b, rel_tol=tol, abs_tol=tol)


def integral(data: list[dict], name: str) -> float:
    return sum((row["ETINT"] - row["STINT"]) * row[name] for row in data)


def main() -> None:
    contract = read(HERE / "contract.json")
    assert contract["version"] == "1.0.1-candidate"
    assert sha(PARENT_RUN / "closure.json") == contract["accepted_parent"]["closure_sha256"]
    assert sha(PARENT_RUN / "report-raw.json") == contract["accepted_parent"]["default_report_sha256"]
    assert sha(PARENT_RUN / "replication-report-raw.json") == contract["accepted_parent"]["replication_report_sha256"]
    assert sha(EXCLUDED_RUN / "closure.json") == contract["excluded_diagnostic"]["closure_sha256"]
    closure, invocation = read(RUN / "closure.json"), read(RUN / "invocation.json")
    assert closure["error"] is None and closure["publication_state"] == "not_published"
    assert closure["invocation_sha256"] == sha(RUN / "invocation.json")
    sources = closure["source_hashes_before"]
    assert sources == closure["source_hashes_after"] == invocation["source_hashes_before"]
    assert sources["native_input"] == contract["input_sha256"] == sha(HERE / "native-input.json")
    assert sources["contract"] == sha(HERE / "contract.json")
    assert sources["exact_diff"] == contract["exact_diff_sha256"] == sha(HERE / "exact-diff.json")
    assert sources["accepted_parent"] == contract["accepted_parent"]["input_sha256"]
    assert sources["accepted_parent_report"] == contract["accepted_parent"]["default_report_sha256"]
    assert sources["excluded_diagnostic_closure"] == contract["excluded_diagnostic"]["closure_sha256"]
    assert sources["report_settings"] == contract["report_settings"]["one_byte_outpr_enabled_sha256"]
    for name in ("build.py", "describe_diff.py", "make_report_settings.py",
                 "check_roundtrip.py", "run_native_ssh.ps1"):
        assert sources[name] == sha(HERE / name), name
    assert invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"]
    assert invocation["gui"]["pid"] == 13340
    assert invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue"
    assert set(closure["raw"]) == RAW
    for name, info in closure["raw"].items():
        path = RUN / name
        assert (path.stat().st_size, sha(path)) == (info["bytes"], info["sha256"]), name
    assert sha(RUN / "input.json") == contract["input_sha256"]
    steps = read(RUN / "steps.json")
    assert [step["name"] for step in steps] == [
        "import", "export", "calc", "jsonreport", "replication_report",
        "check_import_export"]
    assert all(step["status"] == "completed" and step["exit_code"] == 0 for step in steps)
    assert all(step.get("gui_preserved") for step in steps[:5])
    roundtrip = read(RUN / "roundtrip-validation.json")
    assert roundtrip["passed"] and len(roundtrip["populated_tables"]) == 31
    assert roundtrip["source_sha256"] == contract["input_sha256"]
    runlog = (RUN / "run.log").read_text(errors="replace")
    assert re.search(r"Input conversion completed\. Errors: 0, Warnings: 1, Notes: 0", runlog)
    assert re.findall(r"\(warning #(\d+)\)", runlog) == ["108"]
    assert sha(RUN / "model.log") == sha(PARENT_RUN / "model.log")

    parent_default, parent_fixed = native_json(PARENT_RUN / "report-raw.json")
    child_default, child_fixed = native_json(RUN / "report-raw.json")
    assert parent_fixed and child_fixed
    parent_replication = read(PARENT_RUN / "replication-report-raw.json")
    child_replication = read(RUN / "replication-report-raw.json")
    parent_tables, child_tables = tables(parent_default), tables(child_default)
    assert set(parent_tables) == set(child_tables)
    assert {name for name in parent_tables if parent_tables[name] != child_tables[name]} == {
        "ProblemDescription", "SystemResults"}
    parent_system = rows(parent_default, "SystemResults")
    child_system = rows(child_default, "SystemResults")
    assert len(parent_system) == 2064 and len(child_system) == 96
    assert child_system == parent_system[:96]
    assert child_system[0]["STINT"] == 0 and child_system[-1]["ETINT"] == 48
    for name in ("StockTotalResults", "ResourceResults"):
        assert len(rows(child_default, name)) == 2064
        assert rows(child_default, name) == rows(parent_default, name)
    assert rows(child_default, "ResultSummary") == rows(parent_default, "ResultSummary")
    assert rows(child_default, "ResourceResultsTotal") == rows(parent_default, "ResourceResultsTotal")
    assert child_system[-1]["NSYRY"] == 8 and child_system[-1]["NSYUA"] == 0

    parent_rt, child_rt = tables(parent_replication), tables(child_replication)
    assert set(parent_rt) == set(child_rt)
    assert {name for name in parent_rt if parent_rt[name] != child_rt[name]} == {
        "ProblemDescription", "SystemResults",
        "SystemResultsReplicationTotal", "SystemResultsReplication"}
    parent_reps = rows(parent_replication, "Replications")
    child_reps = rows(child_replication, "Replications")
    assert len(child_reps) == 128 and child_reps == parent_reps
    assert [r["REPNO"] for r in child_reps] == list(range(1, 129))
    assert len({r["RSEED"] for r in child_reps}) == 128
    totals = rows(child_replication, "SystemResultsReplicationTotal")
    horizon = rows(child_replication, "SystemResultsReplication")
    assert len(totals) == len(horizon) == 256
    units = ("TEACH-UNIT", "TEACH-UNIT-2")
    by_key = {(row["REPLID"], row["UNID"]): row for row in totals}
    assert len(by_key) == 256
    assert set(by_key) == {(rep, unit) for rep in range(1, 129) for unit in units}
    for row in horizon:
        assert (row["STINT"], row["ETINT"]) == (0, 48)
        total = by_key[(row["REPLID"], row["UNID"])]
        assert close(row["STACC"], total["STACC"]) and row["NFAIL"] == total["NFAIL"]
    per_rep_flight = [48 * sum(by_key[(rep, unit)]["STACC"] for unit in units)
                      for rep in range(1, 129)]
    per_rep_fail = [sum(by_key[(rep, unit)]["NFAIL"] for unit in units)
                    for rep in range(1, 129)]
    assert close(statistics.mean(per_rep_flight), integral(child_system, "STACC"))
    assert close(statistics.mean(per_rep_fail), sum(row["NFAIL"] for row in child_system))

    descriptive = {
        "system_aircraft_operating_hours_0_48": integral(child_system, "STACC"),
        "stock_backorder_item_hours_0_48": integral(rows(child_default, "StockTotalResults")[:96], "NBO"),
        "resource_booked_hours_0_48": integral(rows(child_default, "ResourceResults")[:96], "NRUM"),
        "resource_queued_hours_0_48": integral(rows(child_default, "ResourceResults")[:96], "NRW"),
    }
    assert close(descriptive["system_aircraft_operating_hours_0_48"],
                 integral(parent_system[:96], "STACC"))
    assert close(descriptive["stock_backorder_item_hours_0_48"],
                 integral(rows(parent_default, "StockTotalResults")[:96], "NBO"))
    result = {
        "schema": "simlox-f04-system-window-author-validation/v1",
        "decision": "GO_BOUNDED",
        "run_id": RUN.name,
        "closure_sha256": sha(RUN / "closure.json"),
        "excluded_diagnostic_closure_sha256": sha(EXCLUDED_RUN / "closure.json"),
        "accepted_raw_files_verified": len(closure["raw"]),
        "parent_log_byte_identical": True,
        "full_horizon_summary_and_128_replications_identical": True,
        "system_bins": {"parent": 2064, "child": 96, "exact_prefix_match": True},
        "stock_resource_bins_unchanged": 2064,
        "system_replication_total_rows": len(totals),
        "system_replication_interval_hours": [0, 48],
        "per_replication_flight_mean": statistics.mean(per_rep_flight),
        "per_replication_failure_mean": statistics.mean(per_rep_fail),
        "short_window_descriptive": descriptive,
        "default_report_native_trailing_comma_corrected_for_parse": child_fixed,
        "scope_limit": contract["limitations"],
    }
    path = HERE / "author-native-validation-2026-10-04.json"
    raw = (json.dumps(result, indent=2) + "\n").encode()
    if path.exists():
        assert path.read_bytes() == raw
    else:
        path.write_bytes(raw)
    print(json.dumps({"decision": result["decision"],
                      "validation_sha256": hashlib.sha256(raw).hexdigest(),
                      "descriptive": descriptive}, indent=2))


if __name__ == "__main__":
    main()
