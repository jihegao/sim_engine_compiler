"""Read-only author replay of C10 operational versus calendar failure clocks."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
PARENT_PACKAGE = HERE.parent / "C10-resource-failure-v1.0.0"
PARENT = PARENT_PACKAGE / "oper-no-spare-input.json"
CHILD = HERE / "calendar-two-crew-input.json"
PARENT_RUN = PARENT_PACKAGE / "runs" / "c10-oper-no-spare-20260930-01"
CHILD_RUN = HERE / "runs" / "c10-calendar-two-crew-20260930-01"
PARENT_SHA = "c334c1d6c0efa89f9ff70151a45180cac53b9ae05bf1a783219b566f41dbd62b"
CHILD_SHA = "f05e8b157671eb95f96ed95f360d3e4dbcbc097e3508ba08511c0ab3799f13f7"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tables(doc: dict, section: str) -> dict:
    return {t["name"]: t for t in doc[section]["tables"]}


def rows(table: dict) -> list[list]:
    return [row for instance in table["instances"] for row in instance["rows"]]


def column(table: dict, name: str) -> list:
    index = [c["name"] for c in table["columns"]].index(name)
    return [row[index] for row in rows(table)]


def failure_events(log: str) -> list[tuple[float, int]]:
    result = []
    for line in log.splitlines():
        match = re.fullmatch(r"Time: ([0-9.]+) <P-CREW at <BASE-01,0>> (Failed|Repaired)\s*", line)
        if match:
            result.append((float(match.group(1)), 1 if match.group(2) == "Failed" else -1))
    return result


def failed_bin_averages(events: list[tuple[float, int]]) -> tuple[list[float], int]:
    averages = []
    current = 0
    pos = 0
    for bin_number in range(72):
        start, end = bin_number / 2, (bin_number + 1) / 2
        time = start
        area = 0.0
        while pos < len(events) and events[pos][0] < end:
            event_time, delta = events[pos]
            assert event_time >= time
            area += (event_time - time) * current
            current += delta
            assert 0 <= current <= 2
            time = event_time
            pos += 1
        area += (end - time) * current
        averages.append(area / 0.5)
    assert pos == len(events)
    return averages, current


def check() -> dict:
    issues: list[str] = []

    def require(ok: bool, label: str) -> None:
        if not ok:
            issues.append(label)

    contract = read(HERE / "contract.json")
    diff = read(HERE / "exact-diff.json")
    index = read(HERE.parent / "publication-index-v1.json")
    accepted = {e["publication_id"] for e in index["entries"]}
    parent_id = "C10.var02.operational_crew_failure_spare.1.0.0"
    require(parent_id in accepted and contract["parent_publication_id"] == diff["parent_publication_id"] == parent_id, "accepted parent publication")
    require(sha(PARENT) == PARENT_SHA == contract["parent_input_sha256"] == diff["parent_input_sha256"], "parent source hash")
    require(sha(CHILD) == CHILD_SHA == contract["child_input_sha256"] == diff["child_input_sha256"], "calendar source hash")
    before = tables(parse_native(PARENT), "model")
    after = tables(parse_native(CHILD), "model")
    require(len(before) == len(after) == 32 and before.keys() == after.keys() and sorted(n for n in before if before[n] != after[n]) == ["ProblemDescription", "ResourceStationData"], "32-table exact delta")
    old = rows(before["ResourceStationData"])
    new = rows(after["ResourceStationData"])
    require(old == [["P-CREW", "BASE-01", None, None, None, 0.5, "OPERATION", 0.25, None, None, None]] and new == [["P-CREW", "BASE-01", None, None, None, 0.5, "CALENDAR", 0.25, None, None, None]], "one RFTT field delta")
    require(rows(before["ResourceAllocation"]) == rows(after["ResourceAllocation"]) == [["AIR_BASIC", "P-CREW", "BASE-01", 2, None]], "same two-crew allocation")

    pclose = read(PARENT_RUN / "closure.json")
    pindex = read(PARENT_PACKAGE / "evidence-index.json")
    pent = next(e for e in pindex["runs"] if e["run_id"] == PARENT_RUN.name)
    require(pclose["source_hashes_before"] == pclose["source_hashes_after"] and pclose["source_hashes_before"]["input"] == PARENT_SHA and pent["closure_sha256"] == sha(PARENT_RUN / "closure.json"), "accepted operation run seal")
    for name, item in pclose["raw"].items():
        file = PARENT_RUN / name
        require(file.is_file() and file.stat().st_size == item["bytes"] and sha(file) == item["sha256"], f"operation raw {name}")

    inv = read(CHILD_RUN / "invocation.json")
    close = read(CHILD_RUN / "closure.json")
    steps = read(CHILD_RUN / "steps.json")
    require(inv["case_id"] == "C10" and inv["variant"] == "calendar-two-crew" and inv["run_id"] == close["run_id"] == CHILD_RUN.name and inv["input_sha256"] == CHILD_SHA and inv["parent_sha256"] == PARENT_SHA, "calendar run identity")
    require(inv["session_id"] == 0 and inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "calendar SSH and mutex")
    require(inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, "preserved GUI identity")
    require(close["error"] is None and close["source_hashes_before"] == close["source_hashes_after"] and close["invocation_sha256"] == sha(CHILD_RUN / "invocation.json"), "calendar source and invocation seals")
    for key, file in {"input": CHILD, "parent": PARENT, "contract": HERE / "contract.json", "builder": HERE / "build.py", "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1"}.items():
        require(close["source_hashes_before"][key] == sha(file), f"calendar source {key}")
    require(close["source_hashes_before"]["simlox_exe"] == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0", "native executable hash")
    require([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps), "five guarded steps")
    for name, item in close["raw"].items():
        file = CHILD_RUN / name
        require(file.is_file() and file.stat().st_size == item["bytes"] and sha(file) == item["sha256"], f"calendar raw {name}")
    require(read(CHILD_RUN / "roundtrip-validation.json")["passed"], "native roundtrip checker")
    source_rows = populated(parse_native(CHILD_RUN / "input.json"))
    export_rows = populated(parse_native(CHILD_RUN / "roundtrip-raw.json"))
    require(len(source_rows) == 21 and all(export_rows.get(n) == t for n, t in source_rows.items()), "21 row-containing tables exact roundtrip")
    calc = (CHILD_RUN / "run.log").read_text(encoding="utf-8-sig")
    require("Errors: 0, Warnings: 2, Notes: 0" in calc and set(re.findall(r"warning\s+#(\d+)", calc, re.I)) == {"108", "126"}, "zero-error conversion")
    require((CHILD_RUN / "model.sxo").stat().st_size > 4 and (CHILD_RUN / "report-raw.json").stat().st_size > 4, "nonempty native output")

    log_op = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig")
    log_cal = (CHILD_RUN / "model.log").read_text(encoding="utf-8-sig")
    events_op, events_cal = failure_events(log_op), failure_events(log_cal)
    require(events_op == [(7.73494, 1), (7.98494, -1)] and all(time >= 7.5 for time, _ in events_op), "operation clock only active failure")
    require(len(events_cal) == 165 and sum(delta == 1 for _, delta in events_cal) == 83 and sum(delta == -1 for _, delta in events_cal) == 82, "calendar event totals")
    require(sum(time < 7.5 and delta == 1 for time, delta in events_cal) == 15 and sum(time < 7.5 and delta == -1 for time, delta in events_cal) == 15 and events_cal[:2] == [(0.234939, 1), (0.484939, -1)], "calendar idle failures and repairs")
    require(log_cal.count("is stopped due to a resource failure") == 3 and "Time: 7.57305  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> is stopped due to a resource failure, time left= 0.426955" in log_cal and "Time: 7.78534  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> is stopped due to a resource failure, time left= 0.21466" in log_cal and "Time: 8.02239  subtask 1 seqno 1 within system preparation task 1 on <TEACH-AIR-01,1> is stopped due to a resource failure, time left= 0.0153197" in log_cal, "calendar active-task interruptions")
    require("Time: 8.47761 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting" in log_cal and "Time: 9.47761 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success" in log_cal and "Time: 8.25 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting" in log_op and "Time: 9.25 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success" in log_op, "both successful mission timelines")
    require("Time: 36  resource shift 0 ended" in log_cal, "calendar horizon marker")

    metrics = {}
    for tag, run, events in (("operation", PARENT_RUN, events_op), ("calendar", CHILD_RUN, events_cal)):
        report = tables(parse_native(run / "report-raw.json"), "report")
        require(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"}, f"{tag} report tables")
        summary = report["ResultSummary"]
        require(len(rows(summary)) == 1 and all(column(summary, n) == [1] for n in ("NREP", "MTMF", "MSTF", "MSUF", "STMF")), f"{tag} successful mission summary")
        resource = report["ResourceResults"]
        require(len(rows(resource)) == 72 and column(resource, "STINT") == [i / 2 for i in range(72)] and column(resource, "ETINT") == [(i + 1) / 2 for i in range(72)] and all(n == 2 for n in column(resource, "NR")), f"{tag} 72-bin resource horizon")
        expected_failed, terminal_failed = failed_bin_averages(events)
        require(all(abs(a - b) < 2e-4 for a, b in zip(expected_failed, column(resource, "NRF"))), f"{tag} every failed-resource bin reconciles to event trace")
        work = sum(column(resource, "NRUM")) / 2
        waiting = sum(column(resource, "NRW")) / 2
        failed = sum(column(resource, "NRF")) / 2
        total = report["ResourceResultsTotal"]
        require(len(rows(total)) == 1 and column(total, "NR") == [2] and all(math.isclose(column(total, field)[0] * 36, amount, abs_tol=3e-4) for field, amount in (("NRUM", work), ("NRW", waiting), ("NRF", failed))), f"{tag} interval and total resource ledger")
        require(math.isclose(work, 1, abs_tol=1e-5), f"{tag} one crew-hour productive preparation")
        system = report["SystemResults"]
        require(len(rows(system)) == 72 and column(system, "NSYRY")[-1] == 2 and all(v == 0 for v in column(system, "NFAIL")), f"{tag} two ready aircraft, no aircraft failure")
        stock = report["StockTotalResults"]
        require(len(rows(stock)) == 72 and all(v == 0 for field in ("NDF", "NDD", "NDR", "NDP", "NLD", "NWT") for v in column(stock, field)), f"{tag} zero stock movement")
        metrics[tag] = {"resource_failures": sum(delta == 1 for _, delta in events), "repairs": sum(delta == -1 for _, delta in events), "terminal_failed_resource_count": terminal_failed, "work_resource_hours": work, "failed_resource_hours": failed, "waiting_resource_hours": waiting}
    require(metrics["operation"]["terminal_failed_resource_count"] == 0 and metrics["calendar"]["terminal_failed_resource_count"] == 1 and metrics["calendar"]["failed_resource_hours"] > metrics["operation"]["failed_resource_hours"] and metrics["calendar"]["waiting_resource_hours"] > metrics["operation"]["waiting_resource_hours"], "clock contrast and terminal failed crew")

    return {"schema": "simlox-c10-clock-comparison-author-validation/v1", "passed": not issues, "issues": issues, "metrics": metrics,
            "runs": [{"variant": "operation-parent", "run_id": PARENT_RUN.name, "closure_sha256": sha(PARENT_RUN / "closure.json"), "model_log_sha256": sha(PARENT_RUN / "model.log"), "report_raw_sha256": sha(PARENT_RUN / "report-raw.json")},
                     {"variant": "calendar-child", "run_id": CHILD_RUN.name, "closure_sha256": sha(CHILD_RUN / "closure.json"), "model_log_sha256": sha(CHILD_RUN / "model.log"), "report_raw_sha256": sha(CHILD_RUN / "report-raw.json")}],
            "scope": "one fixed-seed RFTT clock contrast: calendar idle failures versus operation-only active failure, with calendar active interruptions, successful delayed formation, and one calendar resource still failed at horizon"}


if __name__ == "__main__":
    result = check()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if result["passed"] else 1)
