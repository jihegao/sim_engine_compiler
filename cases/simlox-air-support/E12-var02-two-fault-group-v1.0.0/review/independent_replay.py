"""Independent, read-only SIMLOX E12.var02 raw replay; writes only its review verdict.

Uses Python's standard library and never imports the package builder or validators.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE = HERE.parent
CASES = CASE.parent
RUN_ID = "e12-var02-two-fault-group-v100-ssh-20261003-01"
RUN = CASE / "runs" / RUN_ID
PARENT = CASES / "E12-var02-group-system-repair-v1.0.0"
CONTROL = CASES / "E12-var02-two-fault-control-v1.0.0"
CONTROL_RUN = CONTROL / "runs" / "e12-var02-two-fault-control-v100-ssh-20261003-01"
PARENT_RUN = PARENT / "runs" / "e12-var02-group-repair-v100-ssh-20261003-01"
OUT = HERE / "independent-replay-2026-10-03.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strict(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_json(path: Path):
    # SIMLOX's native -jsonreport/-jexport includes trailing commas.
    raw = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", raw))


def tables(doc, member):
    return {t["name"]: t for t in doc[member]["tables"]}


def rows(table):
    return [row for instance in table["instances"] for row in instance["rows"]]


class Audit:
    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failures = []

    def check(self, condition, label):
        self.total += 1
        if condition:
            self.passed += 1
        else:
            self.failures.append(label)


def main():
    a = Audit()
    contract = strict(CASE / "contract.json")
    diff = strict(CASE / "exact-diff.json")
    closure = strict(RUN / "closure.json")
    invocation = strict(RUN / "invocation.json")
    steps = strict(RUN / "steps.json")
    source = strict(CASE / "native-input.json")
    input_doc = strict(RUN / "input.json")
    exported = native_json(RUN / "roundtrip-raw.json")
    group_parent = strict(PARENT / "native-input.json")
    control = strict(CONTROL / "native-input.json")
    report = tables(native_json(RUN / "report-raw.json"), "report")
    control_report = tables(native_json(CONTROL_RUN / "report-raw.json"), "report")

    expected = {
        "input": CASE / "native-input.json",
        "parent": PARENT / "native-input.json",
        "parent_closure": PARENT_RUN / "closure.json",
        "parent_index": PARENT / "evidence-index.json",
        "individual_control": CONTROL / "native-input.json",
        "individual_control_closure": CONTROL_RUN / "closure.json",
        "contract": CASE / "contract.json",
        "exact_diff": CASE / "exact-diff.json",
        "builder": CASE / "build.py",
        "diff_builder": CASE / "describe_diff.py",
        "checker": CASE / "check_roundtrip.py",
        "runner_script": CASE / "run_native_ssh.ps1",
        "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
        "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    }
    for key, path in expected.items():
        actual = sha(path)
        a.check(closure["source_hashes_before"].get(key) == actual, f"before source SHA: {key}")
        a.check(closure["source_hashes_after"].get(key) == actual, f"after source SHA: {key}")
        a.check(invocation["source_hashes_before"].get(key) == actual, f"invocation source SHA: {key}")
    for key in ("python",):
        a.check(closure["source_hashes_before"].get(key) == closure["source_hashes_after"].get(key), "Python runtime stable")
        a.check(invocation["source_hashes_before"].get(key) == closure["source_hashes_before"].get(key), "Python runtime invocation seal")
    a.check(closure["error"] is None, "closure error null")
    a.check(closure["run_id"] == RUN_ID == invocation["run_id"], "run identity")
    a.check(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation SHA")
    a.check(invocation["session_id"] == 0 and invocation["ssh_connection_present"], "SSH session zero")
    a.check("sshd.exe" in invocation["ssh_ancestor_names"], "sshd ancestor")
    a.check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "host mutex")
    a.check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] > 0, "GUI identity")
    a.check([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], "five ordered steps")
    for step in steps:
        a.check(step["exit_code"] == 0 and step["status"] == "completed" and step["error"] is None, f"step success: {step['name']}")
        a.check(step["gui_preserved"] is True, f"step GUI preserved: {step['name']}")
    a.check(len(closure["raw"]) == 12, "12 sealed raw files")
    for name, record in closure["raw"].items():
        p = RUN / name
        a.check(p.is_file() and p.stat().st_size == record["bytes"], f"raw bytes: {name}")
        a.check(sha(p) == record["sha256"], f"raw SHA: {name}")
    a.check(sha(RUN / "input.json") == contract["native_input_sha256"] == diff["source_sha256"], "input source pin")
    a.check(sha(PARENT / "native-input.json") == contract["accepted_parent"]["input_sha256"] == diff["parent_sha256"], "group parent pin")
    a.check(sha(CONTROL / "native-input.json") == contract["individual_control"]["input_sha256"], "individual control pin")
    a.check(sha(CONTROL_RUN / "closure.json") == contract["individual_control"]["native_closure_sha256"], "individual control closure pin")
    a.check(sha(PARENT_RUN / "closure.json") == contract["accepted_parent"]["native_closure_sha256"], "group parent closure pin")
    a.check(sha(PARENT / "evidence-index.json") == contract["accepted_parent"]["evidence_index_sha256"], "group parent index pin")
    a.check(sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"], "exact diff pin")
    a.check(source == input_doc, "copied input matches frozen source")

    st, pt, ct, et = [tables(x, "model") for x in (source, group_parent, control, exported)]
    a.check(len(st) == len(pt) == len(ct) == 32, "32 model tables")
    authored = {n for n, t in st.items() if rows(t)}
    a.check(len(authored) == 22, "authored roundtrip table names")
    for name in set(st) - authored:
        a.check(all(all(v is None for v in row) for row in rows(et[name])), f"native all-null placeholder: {name}")
    a.check(sum(bool(rows(t)) for t in st.values()) == 22, "22 authored populated tables")
    for name in st:
        if rows(st[name]):
            a.check(st[name] == et[name], f"exact native roundtrip: {name}")
        if name not in ("MissionType", "ProblemDescription"):
            a.check(st[name] == pt[name], f"group parent fixed table: {name}")
        if name not in ("Station", "SystemRepair", "ProblemDescription"):
            a.check(st[name] == ct[name], f"individual control fixed table: {name}")
    a.check(sorted(diff["changed_tables"]) == ["MissionType", "ProblemDescription"] and diff["unchanged_parent_tables"] == 30, "frozen two-table delta")
    mission_names = [c["name"] for c in st["MissionType"]["columns"]]
    durn_idx = mission_names.index("DURN")
    a.check(rows(pt["MissionType"])[0][durn_idx] == 2 and rows(st["MissionType"])[0][durn_idx] == rows(ct["MissionType"])[0][durn_idx] == 3.5, "matched mission duration")
    station_names = [c["name"] for c in st["Station"]["columns"]]
    sidx, gidx = station_names.index("STID"), station_names.index("GSTID")
    station_groups = {r[sidx]: r[gidx] for r in rows(st["Station"])}
    a.check(station_groups.get("BASE-01") == station_groups.get("BASE-02") == "BASE-GRP" and station_groups.get("DEPOT-01") is None, "two-base group membership")
    repair_names = [c["name"] for c in st["SystemRepair"]["columns"]]
    ridx, surpt_idx = repair_names.index("STID"), repair_names.index("SURPT")
    a.check(len(rows(st["SystemRepair"])) == 1 and rows(st["SystemRepair"])[0][ridx] == "BASE-GRP" and rows(st["SystemRepair"])[0][surpt_idx] == 0.5, "one half-hour group repair row")
    a.check(sorted(r[ridx] for r in rows(ct["SystemRepair"])) == ["BASE-01", "BASE-02"], "control individual repair rows")

    rt = strict(RUN / "roundtrip-validation.json")
    a.check(rt["passed"] is True and not rt["differences"], "native roundtrip certificate")
    calc = (RUN / "run.log").read_text(encoding="utf-8-sig")
    a.check("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in calc, "zero converter errors, reviewed warning")
    a.check("(warning #108)" in calc and len(re.findall(r"warning #\d+", calc)) == 1, "only warning #108")
    a.check((RUN / "model.sxo").stat().st_size > 1000, "nonempty native result")

    glog = (RUN / "model.log").read_bytes()
    clog = (CONTROL_RUN / "model.log").read_bytes()
    a.check(glog == clog, "byte-identical group/control event log")
    log = glog.decode("utf-8-sig")
    physical_markers = [
        "Time: 9.8829 <TEACH-AIR-01,0> critical random failure added",
        "Time: 11.1325 <TEACH-AIR-01,1> critical random failure added",
        "Time: 10.7579  system SURP task 0 on <TEACH-AIR-01,0> started",
        "Time: 11.2579  system SURP task 0 on <TEACH-AIR-01,0> completed",
        "Time: 11.5  system SURP task 1 on <TEACH-AIR-01,1> started",
        "Time: 12  system SURP task 1 on <TEACH-AIR-01,1> completed",
        "Time: 10.7579 <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,1> from stock",
        "Time: 11.5 <TEACH-LRU-01,0,BASE-02,0> Take replacement item <TEACH-LRU-01,0,2> from stock",
        "Time: 11.5 <TEACH-LRU-01,0,DEPOT-01,0> Backorder added",
        "Time: 14.9246 <TEACH-LRU-01,0,DEPOT-01,0> Backorder removed",
        "Time: 36  system SURP task 6 on <TEACH-AIR-01,0> completed",
        "Time: 36 <TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>",
    ]
    for marker in physical_markers:
        a.check(marker in log, f"physical event: {marker[:75]}")
    a.check(len(re.findall(r"mission aborted:", log)) == 4, "four mission aborts")
    a.check(len(re.findall(r"mission success:", log)) == 2, "two mission successes")
    a.check("<TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,1>" in log, "BASE-01 initial physical spare")
    a.check("<TEACH-LRU-01,0,BASE-02,0> Level: 1 Items:<TEACH-LRU-01,0,2>" in log, "BASE-02 initial physical spare")
    a.check("<TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,0>" in log, "BASE-01 depot replenishment")
    a.check("<TEACH-LRU-01,0,BASE-02,0> Level: 1 Items:<TEACH-LRU-01,0,3>" in log, "BASE-02 repaired replenishment")
    a.check("<TEACH-LRU-01,0,DEPOT-01,0> Nbr: 0" in log, "depot backorder cleared")

    a.check(set(report) == set(control_report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "report table set")
    report_cells = 0
    for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
        x, y = report[name], control_report[name]
        a.check(x["columns"] == y["columns"], f"report columns: {name}")
        xr, yr = rows(x), rows(y)
        expected_rows = 1 if name == "ResultSummary" else 72
        a.check(len(xr) == len(yr) == expected_rows, f"report row count: {name}")
        for i, (xrow, yrow) in enumerate(zip(xr, yr)):
            a.check(len(xrow) == len(yrow) == len(x["columns"]), f"report row width: {name} {i}")
            for j, (v, w) in enumerate(zip(xrow, yrow)):
                a.check(v == w, f"report cell: {name} row{i} col{j}")
                report_cells += 1
        if name != "ResultSummary":
            names = [c["name"] for c in x["columns"]]
            si, ei = names.index("STINT"), names.index("ETINT")
            for i, row in enumerate(xr):
                a.check(row[si] == i * 0.5 and row[ei] == (i + 1) * 0.5, f"aligned h0-36 interval: {name} {i}")
    a.check(rows(report["ProblemDescription"]) != rows(control_report["ProblemDescription"]), "only description may differ")

    result = {
        "schema": "simlox-e12-var02-two-fault-group-independent-raw-replay/v1",
        "run_id": RUN_ID,
        "passed": not a.failures,
        "verdict": "GO" if not a.failures else "NO-GO",
        "checks_passed": a.passed,
        "checks_total": a.total,
        "failures": a.failures,
        "report_cells_compared": report_cells,
        "report_rows": {name: len(rows(report[name])) for name in ("ResultSummary", "SystemResults", "StockTotalResults")},
        "event_log_sha256": sha(RUN / "model.log"),
        "control_event_log_sha256": sha(CONTROL_RUN / "model.log"),
        "closure_sha256": sha(RUN / "closure.json"),
        "input_sha256": sha(CASE / "native-input.json"),
        "limits": ["one seed and 36-hour horizon", "no individual-over-group override tested", "no GUI visual or cross-engine parity claim"],
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("verdict", "checks_passed", "checks_total", "report_cells_compared", "failures")}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
