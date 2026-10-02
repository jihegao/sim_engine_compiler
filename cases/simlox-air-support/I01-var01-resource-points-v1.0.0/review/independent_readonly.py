"""Standalone read-only replay of I01.var01 ResourceAllocation POINT evidence.

Reads authored sources and sealed native artifacts directly. No author code is
imported or executed and SIMLOX is never invoked.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
OUTPUT = Path(__file__).with_name("independent-readonly-2026-10-02.json")
IDS = {
    "selected": "i01-var01-resource-selected-v100-ssh-20261002-01",
    "zero": "i01-var01-resource-zero-v100-ssh-20261002-01",
}
count = 0
failures: list[str] = []


def test(ok: bool, label: str) -> None:
    global count
    count += 1
    if not ok:
        failures.append(label)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path, native: bool = False):
    raw = path.read_text(encoding="utf-8-sig")
    if native:
        raw = re.sub(r",\s*([}\]])", r"\1", raw)
    return json.loads(raw)


def table_map(document: dict, section: str) -> dict:
    return {table["name"]: table for table in document[section]["tables"]}


def rows(table: dict) -> list[list]:
    return [row for instance in table["instances"] for row in instance["rows"]]


def records(table: dict) -> list[dict]:
    columns = [column["name"] for column in table["columns"]]
    return [dict(zip(columns, row)) for row in rows(table)]


def near(actual, expected, tolerance=1e-6) -> bool:
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return abs(actual - expected) <= tolerance
    return actual == expected


def source_checks(contract: dict) -> dict:
    parent = (CASE / contract["direct_parent"]["source"]).resolve()
    evidence = (CASE / contract["direct_parent"]["accepted_evidence"]).resolve()
    test(digest(parent) == contract["direct_parent"]["sha256"], "accepted C01 parent hash")
    test(evidence.is_file() and "native_behavior_accepted" in evidence.read_text(encoding="utf-8"),
         "accepted C01 evidence")
    for name in IDS:
        test(digest(CASE / f"{name}-input.json") == contract["sources_sha256"][name],
             f"{name} input hash")
    test(digest(CASE / "exact-diff.json") == contract["sources_sha256"]["exact_diff"],
         "frozen exact diff hash")
    test(contract["publication_state"] == "not_published", "original candidate status")
    baseline = read_json(parent)
    sources = {name: read_json(CASE / f"{name}-input.json") for name in IDS}
    ptab = table_map(baseline, "model")
    a, b = [table_map(sources[name], "model") for name in IDS]
    test(set(ptab) == set(a) == set(b), "same model table set")
    test({name for name in ptab if ptab[name] != a[name]} ==
         {"ProblemDescription", "ResourceAllocation"}, "parent to selected exact table delta")
    for name in set(ptab) - {"ProblemDescription", "ResourceAllocation"}:
        test(ptab[name] == a[name], f"parent unchanged {name}")
    prior = rows(ptab["ResourceAllocation"])
    selected = rows(a["ResourceAllocation"])
    test(selected[:len(prior)] == prior, "accepted AIR_BASIC allocation rows retained")
    test(selected[len(prior):] == [
        ["AIR_ZERO", "P-CREW", "BASE-01", 0, None],
        ["AIR_ZERO", "P-OTHER", "BASE-01", 0, None],
    ], "exact two zero-point rows")
    test({name for name in a if a[name] != b[name]} == {"ProblemDescription", "Control"},
         "selected versus zero only APID and description tables")
    for name in set(a) - {"ProblemDescription", "Control"}:
        test(a[name] == b[name], f"paired unchanged {name}")
    ac, bc = records(a["Control"])[0], records(b["Control"])[0]
    test({key for key in ac if ac[key] != bc[key]} == {"APID"}, "sole Control APID delta")
    test((ac["APID"], bc["APID"]) == ("AIR_BASIC", "AIR_ZERO"), "selected POINT identities")
    test(records(a["SubTaskResource"]) == [{"TID": "PREP-FIXED", "SEQ": 1,
         "RID": "P-CREW", "QTY": 2, "RPROB": 1, "ARID": None, "ARTF": None,
         "ENRMS": None, "NOTE": None}], "fixed two-person INSPECT demand")
    test(not rows(a["StockAllocation"]), "no stock POINT rows")
    test("MaintenanceAllocation" not in a or not rows(a["MaintenanceAllocation"]),
         "no maintenance POINT rows")
    return sources


def expected_system(name: str, hour: float) -> dict:
    selected = name == "selected"
    if selected:
        allocated = float(7 <= hour < 10)
        prep = float(hour == 7)
        flight = float(8 <= hour < 10)
        request = float(hour == 7.5)
        success = float(hour == 7.5)
    else:
        allocated = 1 if hour == 7 else (1/6 if hour == 7.5 else 0)
        prep, flight, request, success = allocated, 0, 0, 0
    return {"NSYRY": 1 - allocated, "NSYMA": allocated, "NSYMO": flight,
            "NSYMP": prep, "NSYMR": request, "NSYA": 1, "FTMO": flight,
            "STACC": flight, "NPSTA": int(hour == 7), "NPSUC": success}


def expected_resource(name: str, hour: float) -> dict:
    selected = name == "selected"
    capacity = 2 if selected else 0
    utilization = 2/3 if selected and hour == 7 else 0
    waiting = 0 if selected else (2 if hour == 7 else (1/3 if hour == 7.5 else 0))
    return {"NR": capacity, "NRUM": utilization, "NRW": waiting,
            "NRA": capacity, "NRN": capacity}


def report_checks(name: str, report: dict) -> None:
    summary = records(report["ResultSummary"])[0]
    success = int(name == "selected")
    for field, wanted in (("NREP", 1), ("RTIUP", 36), ("MTMF", success),
                          ("MSTF", success), ("MSUF", success), ("STMF", success)):
        test(near(summary[field], wanted), f"{name} summary {field}")
    system = records(report["SystemResults"])
    resource = records(report["ResourceResults"])
    stock = records(report["StockTotalResults"])
    test(len(system) == len(resource) == len(stock) == 72, f"{name} three 72-bin ledgers")
    system_dimensions = {"UNID", "SID", "STINT", "ETINT"}
    resource_dimensions = {"RID", "STID", "STINT", "ETINT"}
    stock_dimensions = {"STINT", "ETINT"}
    for index, (s, r, t) in enumerate(zip(system, resource, stock)):
        hour = index / 2
        for row, ledger in ((s, "system"), (r, "resource"), (t, "stock")):
            test(row["STINT"] == hour and row["ETINT"] == hour + .5,
                 f"{name} {ledger} bin {index} interval")
        sx = expected_system(name, hour)
        for field, value in s.items():
            if field in system_dimensions:
                continue
            wanted = sx.get(field, None if field == "SYDT" else 0)
            test(near(value, wanted), f"{name} system {index} {field}")
        rx = expected_resource(name, hour)
        for field, value in r.items():
            if field in resource_dimensions:
                continue
            test(near(value, rx.get(field, 0)), f"{name} resource {index} {field}")
        for field, value in t.items():
            if field in stock_dimensions:
                continue
            wanted = 1 if field == "PNB" else (None if field in
                     {"NBOU", "ROS", "ROST", "WT", "WTT", "WTS"} else 0)
            test(near(value, wanted), f"{name} stock {index} {field}")
    resource_total = records(report["ResourceResultsTotal"])[0]
    cap = 2 if name == "selected" else 0
    for field, wanted in (("NR", cap), ("NRA", cap), ("NRN", cap),
                          ("NRUM", (1/3)/36 if cap else 0),
                          ("NRW", 0 if cap else (7/6)/36)):
        test(near(resource_total[field], wanted), f"{name} resource total {field}")
    test(near(sum(row["NSYMO"] for row in system) * .5, 2 if cap else 0),
         f"{name} flight-hour integral")
    test(system[-1]["NSYRY"] == 1 and system[-1]["NSYMA"] == 0,
         f"{name} terminal aircraft ready")


def event_checks(name: str, event_log: str) -> None:
    common = [
        "Time: 7 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission created",
        "Time: 7 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission allocates system: <TEACH-AIR-01,0>",
        "Time: 7 <TEACH-AIR-01,0> preparation started",
        "Time: 7  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> requests resources",
    ]
    for phrase in common:
        test(phrase in event_log, f"{name} common event {phrase}")
    if name == "selected":
        ordered = [
            "request for: 2 OK",
            "Time: 7  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> books resources",
            "Time: 7  <P-CREW at <BASE-01,0>> allocated to maintenance task: 2  available now: 0",
            "Time: 7  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> starts performing",
            "Time: 7.16667  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> completed",
            "Time: 7.16667  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> frees resources",
            "Time: 7.16667  <P-CREW at <BASE-01,0>> deallocated from  maintenance task: 2  available now: 2",
            "Time: 7.5  system preparation task 0 on <TEACH-AIR-01,0> completed",
            "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 2 : <TEACH-AIR-01,0>",
            "Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success",
            "Time: 10 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission completed",
        ]
        positions = [event_log.find(phrase) for phrase in ordered]
        test(all(position >= 0 for position in positions), "selected full crew/work/mission lifecycle")
        test(positions == sorted(positions) and len(set(positions)) == len(positions),
             "selected crew lease precedes work and release")
        test("mission cancelled" not in event_log, "selected no cancellation")
    else:
        ordered = [
            "request for: 2 failed",
            "Time: 7.58333 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission cancelled",
            "Time: 7.58333  subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> resource waiting stopped",
            "Time: 7.58333  system preparation task 0 on <TEACH-AIR-01,0> stopped",
            "Time: 7.58333 <TEACH-UNIT at <BASE-01,0>> systems ready: 1",
        ]
        positions = [event_log.find(phrase) for phrase in ordered]
        test(all(position >= 0 for position in positions), "zero failure/cancellation/cleanup lifecycle")
        test(positions == sorted(positions) and len(set(positions)) == len(positions),
             "zero waiting precedes cancellation and cleanup")
        test("books resources" not in event_log and "allocated to maintenance task: 2" not in event_log,
             "zero no crew lease")
        test("starts performing" not in event_log and "mission starting" not in event_log,
             "zero no positive work or flight")


def run_checks(name: str, source: dict, contract: dict) -> None:
    folder = CASE / "runs" / IDS[name]
    invocation = read_json(folder / "invocation.json")
    closure = read_json(folder / "closure.json")
    steps = read_json(folder / "steps.json")
    test(invocation["run_id"] == closure["run_id"] == IDS[name], f"{name} identity")
    test(closure["invocation_sha256"] == digest(folder / "invocation.json"), f"{name} invocation seal")
    test(invocation["input_sha256"] == contract["sources_sha256"][name], f"{name} source binding")
    test(invocation["parent_sha256"] == contract["direct_parent"]["sha256"], f"{name} parent binding")
    test(invocation["contract_sha256"] == digest(CASE / "contract.json"), f"{name} contract binding")
    for field, filename in (("builder", "build.py"), ("diff_checker", "describe_diff.py"),
                            ("exact_diff", "exact-diff.json"), ("checker", "check_roundtrip.py"),
                            ("runner_script", "run_native_ssh.ps1")):
        test(invocation["source_hashes_before"][field] == digest(CASE / filename),
             f"{name} {field} source seal")
    for field, key in (("manual", "manual_pdf"), ("dictionary", "table_dictionary"),
                       ("simlox_exe", "simlox_exe")):
        test(invocation["source_hashes_before"][field] == contract["installed_source_sha256"][key],
             f"{name} installed {field} seal")
    test(closure["source_hashes_before"] == closure["source_hashes_after"] ==
         invocation["source_hashes_before"], f"{name} stable frozen sources")
    test(invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and
         invocation["ssh_connection_present"] is True and
         "sshd.exe" in invocation["ssh_ancestor_names"], f"{name} session-zero SSH")
    test(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", f"{name} mutex")
    test(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1,
         f"{name} preserved GUI identity")
    test(closure["error"] is None, f"{name} closure error absent")
    test([step["name"] for step in steps] ==
         ["import", "export", "calc", "jsonreport", "check_import_export"], f"{name} five steps")
    for step in steps:
        test(step["exit_code"] == 0 and step["gui_preserved"] is True and step["error"] is None,
             f"{name} step {step['name']} exit/GUI")
    test(steps[2]["status"] == "calc_observed" and
         all(step["status"] == "completed" for step in steps[:2] + steps[3:]),
         f"{name} step status")
    test(len(closure["raw"]) == 12, f"{name} twelve raw seals")
    for filename, meta in sorted(closure["raw"].items()):
        path = folder / filename
        test(path.is_file() and path.stat().st_size == meta["bytes"] and digest(path) == meta["sha256"],
             f"{name} raw seal {filename}")
    test(digest(folder / "input.json") == contract["sources_sha256"][name] and
         read_json(folder / "input.json") == source, f"{name} copied input exact")
    original, exported = table_map(source, "model"), table_map(read_json(folder / "roundtrip-raw.json", True), "model")
    populated = {table for table in original if rows(original[table])}
    test(len(populated) == 20, f"{name} twenty row-containing tables")
    test(sum(all(value is None for value in row) for table in populated for row in rows(original[table])) == 3,
         f"{name} three all-null placeholders")
    for table in sorted(populated):
        a, b = original[table], exported.get(table)
        test(b is not None and [c["name"] for c in a["columns"]] == [c["name"] for c in b["columns"]]
             and len(rows(a)) == len(rows(b)) and
             all(len(x) == len(y) and all(near(v, w) for v, w in zip(x, y))
                 for x, y in zip(rows(a), rows(b))), f"{name} {table} exact roundtrip")
    conversion = (folder / "run.log").read_text(encoding="utf-8-sig")
    test("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in conversion,
         f"{name} conversion zero errors")
    test("warning #108" in conversion and "warning #126" in conversion,
         f"{name} expected warnings")
    test((folder / "model.sxo").stat().st_size > 4, f"{name} valid SXO")
    event_log = (folder / "model.log").read_text(encoding="utf-8-sig")
    event_checks(name, event_log)
    report = table_map(read_json(folder / "report-raw.json", True), "report")
    test({"ResultSummary", "SystemResults", "ResourceResults", "ResourceResultsTotal",
          "StockTotalResults"} <= set(report), f"{name} report tables")
    report_checks(name, report)


def main() -> int:
    try:
        contract = read_json(CASE / "contract.json")
        sources = source_checks(contract)
        for name in IDS:
            run_checks(name, sources[name], contract)
    except Exception as exc:
        failures.append(f"replay exception: {type(exc).__name__}: {exc}")
    passed = not failures
    verdict = {
        "schema": "i01-var01-resource-points-independent-review/v1",
        "package": CASE.name,
        "passed": passed,
        "checks_passed": count - len(failures),
        "checks_total": count,
        "failures": failures,
        "verdict": "GO_BOUNDED_RESOURCE_APID_SELECTION" if passed else "NO_GO_REPLAY_FAILURE",
        "supported_scope": "For one C01-derived preparation demand, APID selects AIR_BASIC capacity two or AIR_ZERO capacity zero from ResourceAllocation rows held in the same model. The sealed event order and 72-bin resource, system, and stock ledgers support the observed work, mission, waiting, and terminal contrast.",
        "limits": ["No authored StockAllocation or MaintenanceAllocation rows: combined three-table APID selection is untested.",
                   "No E01 LRU replacement, maintenance routing, StationVariant, GUI visual, cross-engine, or general-capacity claim.",
                   "One station, seed, mission, resource specialty and demand quantity."],
        "runs": {name: {"id": run_id,
                        "closure_sha256": digest(CASE / "runs" / run_id / "closure.json"),
                        "report_sha256": digest(CASE / "runs" / run_id / "report-raw.json")}
                 for name, run_id in IDS.items()},
    }
    OUTPUT.write_bytes((json.dumps(verdict, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": passed, "checks_passed": verdict["checks_passed"],
                      "checks_total": count, "failures": failures, "verdict": verdict["verdict"]}))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
