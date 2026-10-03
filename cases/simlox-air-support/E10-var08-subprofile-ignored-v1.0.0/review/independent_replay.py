"""Independent standard-library read-only E10.var08 raw evidence replay."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
ROOT = CASE.parent
RUN_ID = "e10-var08-ignored-v100-ssh-20261003-01"
RUN = CASE / "runs" / RUN_ID
OUT = Path(__file__).with_name("independent-verdict.json")
checks = []


def check(name, good):
    checks.append({"name": name, "passed": bool(good)})


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path, native=False):
    value = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",(?=\s*[}\]])", "", value) if native else value)


def tables(doc, root="model"):
    return {table["name"]: table for table in doc[root]["tables"]}


def rows(table):
    return [row for instance in table["instances"] for row in instance["rows"]]


def field(table, row, name):
    return row[[column["name"] for column in table["columns"]].index(name)]


def at(log, hour, fragment):
    return any(line.startswith(f"Time: {hour} ") and fragment in line for line in log.splitlines())


def near(a, b, tolerance=0.0001):
    return math.isclose(float(a), float(b), rel_tol=0, abs_tol=tolerance)


def main():
    contract = read(CASE / "contract.json")
    diff = read(CASE / "exact-diff.json")
    source_path = CASE / "native-input.json"
    parent_pkg = ROOT / contract["accepted_parent"]["package"]
    parent_source = parent_pkg / "native-input.json"
    parent_run = parent_pkg / "runs" / contract["accepted_parent"]["run_id"]
    parent_closure = parent_run / "closure.json"
    parent_index = parent_pkg / "evidence-index.json"
    check("accepted parent input/closure/index SHA", sha(parent_source) == contract["accepted_parent"]["input_sha256"] and
          sha(parent_closure) == contract["accepted_parent"]["native_closure_sha256"] and
          sha(parent_index) == contract["accepted_parent"]["evidence_index_sha256"])
    check("child input/diff SHA and source lineage", sha(source_path) == contract["native_input_sha256"] ==
          diff["source_sha256"] and sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"] and
          diff["parent_sha256"] == sha(parent_source))
    parent = tables(read(parent_source))
    child = tables(read(source_path))
    changed = {name for name in parent.keys() | child.keys() if parent.get(name) != child.get(name)}
    check("exact two changed source tables", changed == set(diff["changed_tables"]) ==
          {"ProblemDescription", "TransportPolicyProfile"} and
          diff["unchanged_parent_tables"] == len(parent) - len(changed))
    for name in sorted(parent.keys() - changed):
        check(f"unchanged source table {name}", child[name] == parent[name])
    check("description exact before/after", rows(parent["ProblemDescription"]) == [[diff["description_before"]]] and
          rows(child["ProblemDescription"]) == [[diff["description_after"]]])
    original = parent["TransportPolicyProfile"]
    modified = child["TransportPolicyProfile"]
    check("profile schema and two authored rows", original["columns"] == modified["columns"] and
          len(rows(original)) == len(rows(modified)) == 2)
    prow, crow = rows(original)[0], rows(modified)[0]
    names = [col["name"] for col in original["columns"]]
    altered = {name for i, name in enumerate(names) if prow[i] != crow[i]}
    check("wrapper subprofile and ignored fields exact", prow[:5] ==
          ["DOWN-POLICY", "REPEAT-FIXED", 8, 2, 3] and altered ==
          set(diff["wrapper_field_changes"]) == {"MINBS", "TPTIM", "TPTIMD"} and
          all([prow[names.index(name)], crow[names.index(name)]] == values
              for name, values in diff["wrapper_field_changes"].items()))
    check("basic FIXED child unchanged TPTIM2", rows(original)[1] == rows(modified)[1] ==
          diff["unchanged_child_basic_row"] and field(modified, rows(modified)[1], "TPTIM") == 2)
    check("no authored resource rows", all(not rows(child[name]) for name in
          ("Resource", "ResourceAllocation", "TaskResource")))

    invocation = read(RUN / "invocation.json")
    closure = read(RUN / "closure.json")
    check("run identity and invocation SHA", invocation["run_id"] == closure["run_id"] == RUN_ID and
          closure["invocation_sha256"] == sha(RUN / "invocation.json"))
    check("native input bound to frozen source", invocation["input_sha256"] == sha(source_path) == sha(RUN / "input.json"))
    pins = closure["source_hashes_before"]
    check("frozen source hashes across native run", pins == closure["source_hashes_after"] ==
          invocation["source_hashes_before"])
    source_paths = {
        "input": source_path, "parent": parent_source, "parent_closure": parent_closure,
        "parent_index": parent_index, "contract": CASE / "contract.json",
        "exact_diff": CASE / "exact-diff.json", "builder": CASE / "build.py",
        "diff_builder": CASE / "describe_diff.py", "checker": CASE / "check_roundtrip.py",
        "runner_script": CASE / "run_native_ssh.ps1",
    }
    for name, path in sorted(source_paths.items()):
        check(f"sealed source {name}", pins[name] == sha(path))
    check("installed manual/exe/dictionary fingerprints", all(
          pins[name] == contract["source"][key] for name, key in
          (("simlox_exe", "simlox_exe_sha256"), ("manual", "manual_pdf_sha256"),
           ("dictionary", "dictionary_sha256"))))
    check("manual PDF physically inspected SHA", sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")) ==
          contract["source"]["manual_pdf_sha256"])
    check("SSH0/mutex and preserved GUI", invocation["execution_mode"] == "ssh_cli_v1" and
          invocation["session_id"] == 0 and invocation["ssh_connection_present"] and
          "sshd.exe" in invocation["ssh_ancestor_names"] and
          invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and
          invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
    steps = read(RUN / "steps.json")
    check("five guarded successful steps", [step["name"] for step in steps] ==
          ["import", "export", "calc", "jsonreport", "check_import_export"] and
          all(step["exit_code"] == 0 and step["gui_preserved"] for step in steps))
    check("twelve sealed raw files", len(closure["raw"]) == 12)
    for name, seal in sorted(closure["raw"].items()):
        path = RUN / name
        check(f"raw SHA {name}", path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
    exported = tables(read(RUN / "roundtrip-raw.json", native=True))
    count = 0
    for name, authored in sorted(child.items()):
        if not rows(authored):
            continue
        count += 1
        target = exported.get(name)
        same = target is not None
        if same:
            width = len(authored["columns"])
            same = ([col["name"] for col in authored["columns"]] ==
                    [col["name"] for col in target["columns"][:width]] and
                    [inst["rows"] for inst in authored["instances"]] ==
                    [[row[:width] for row in inst["rows"]] for inst in target["instances"]])
        check(f"exact authored roundtrip {name}", same)
    check("22 row-containing authored tables", count == 22)
    converter = (RUN / "run.log").read_text(encoding="utf-8-sig")
    check("converter Errors0 Warnings2 Notes0", bool(re.search(
          r"Errors:\s*0, Warnings:\s*2, Notes:\s*0", converter)))
    check("warning108 and exact row-specific ignored-field warning152", re.findall(
          r"warning #(\d+)", converter) == ["108", "152"] and
          "Form: TransportPolicyProfile\nrec 1: (warning #152) MINBS, TPTIM and TPTIMD are only valid for FIXED and ONDEM profiles. Data Ignored." in
          converter.replace("\r\n", "\n"))
    check("valid SXO/event/report", all((RUN / name).stat().st_size > 1000 for name in
          ("model.sxo", "model.log", "report-raw.json")))

    log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    parent_log = (parent_run / "model.log").read_text(encoding="utf-8-sig")
    check("entire event log byte-identical to accepted parent", sha(RUN / "model.log") == sha(parent_run / "model.log"))
    events = [
        ("0", "scheduled transport task 0 created from <DEPOT-01,0> to <BASE-01,0>, scheduled to start at 8"),
        ("8", "scheduled transport task 1 created from <DEPOT-01,0> to <BASE-01,0>, scheduled to start at 11"),
        ("8", "scheduled transport task 0 cancelled with 0 items/systems"),
        ("9.8829", "critical random failure added"), ("9.8829", "mission aborted"),
        ("10", "Take replacement item <TEACH-LRU-01,0,0> from stock"),
        ("10", "transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> attached to  scheduled transport task 1"),
        ("10.1667", "transport task 2 starts with 1 items/systems, transport time: 2"),
        ("11", "scheduled transport task 1 starts with 1 items/systems, transport time: 2"),
        ("12.1667", "transport task 2 arrives with 1 items/systems"),
        ("12.1667", "Start repair of item <TEACH-LRU-01,0,1>"),
        ("13", "scheduled transport task 1 arrives with 1 items/systems"),
        ("13", "Replacement item arrives <TEACH-LRU-01,0,0>"),
        ("13", "Backorder removed, waiting time was 3"),
        ("13.1667", "Finished repair of item <TEACH-LRU-01,0,1>"),
        ("13.1667", "Put back replacement item <TEACH-LRU-01,0,1> to stock"),
        ("13.3333", "System ready <TEACH-AIR-01,0>"),
        ("20", "BASIC-MISSION,TEACH-UNIT,0,0,1> mission starting"),
        ("22", "BASIC-MISSION,TEACH-UNIT,0,0,1> mission success"),
        ("32", "BASIC-MISSION,TEACH-UNIT,0,0,2> mission starting"),
        ("34", "BASIC-MISSION,TEACH-UNIT,0,0,2> mission success"),
    ]
    for hour, fragment in events:
        check(f"native event {hour} {fragment}", at(log, hour, fragment))
    check("no 9h/stochastic transport used", not any("transport time: 9" in line for line in log.splitlines()) and
          sum("starts with 1 items/systems" in line for line in log.splitlines()) ==
          sum("arrives with 1 items/systems" in line for line in log.splitlines()) == 2)
    check("physical terminal ID1 stock, no resource booking", "Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 1 Items:<TEACH-LRU-01,0,1>," in log and
          "books resources" not in log)
    check("parent and child same individual source-bound event sequence", log == parent_log)

    report = tables(read(RUN / "report-raw.json", native=True), "report")
    parent_report = tables(read(parent_run / "report-raw.json", native=True), "report")
    check("expected selected report tables", set(report) ==
          {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
        check(f"entire {name} table identical parent", report[name] == parent_report[name])
    system, stock, summary = (report[name] for name in ("SystemResults", "StockTotalResults", "ResultSummary"))
    sy, st = rows(system), rows(stock)
    parent_sy, parent_st = rows(parent_report["SystemResults"]), rows(parent_report["StockTotalResults"])
    check("72 System and Stock half-hour bins", len(sy) == len(st) == 72)
    for index, (srow, trow) in enumerate(zip(sy, st)):
        start, end = index / 2, (index + 1) / 2
        check(f"System interval {index}", near(field(system, srow, "STINT"), start, 1e-6) and
              near(field(system, srow, "ETINT"), end, 1e-6))
        check(f"Stock interval {index}", near(field(stock, trow, "STINT"), start, 1e-6) and
              near(field(stock, trow, "ETINT"), end, 1e-6))
        check(f"whole System bin equals parent {index}", srow == parent_sy[index])
        check(f"whole Stock bin equals parent {index}", trow == parent_st[index])
        check(f"event-derived NBO bin {index}", (field(stock, trow, "NBO") or 0) ==
              (1 if 10 <= start < 13 else 0))
        check(f"stock demand bin {index}", (field(stock, trow, "NDF") or 0) ==
              (1 if start == 10 else 0))
    check("stock waiting three hours", near(sum((field(stock, row, "WT") or 0) for row in st), 3))
    check("one failure and repair", sum((field(system, row, "NFAIL") or 0) for row in sy) == 1 and
          sum((field(system, row, "NREPT") or 0) for row in sy) == 1)
    result_row = rows(summary)[0]
    check("one repetition; two of three missions succeed", field(summary, result_row, "NREP") == 1 and
          field(summary, result_row, "RTIUP") == 36 and near(field(summary, result_row, "MSUF"), 2 / 3))
    check("terminal ready1/backorder0", near(field(system, sy[-1], "NSYRY"), 1) and
          (field(stock, st[-1], "NBO") or 0) == 0)

    failures = [entry["name"] for entry in checks if not entry["passed"]]
    result = {
        "schema": "simlox-e10-var08-independent-readonly/v1", "passed": not failures,
        "verdict": "GO_bounded_ignored_subprofile_wrapper_fields" if not failures else "NO_GO",
        "checks_passed": len(checks) - len(failures), "checks_total": len(checks),
        "failures": failures, "checks": checks,
        "hashes": {"input": sha(source_path), "contract": sha(CASE / "contract.json"),
                   "exact_diff": sha(CASE / "exact-diff.json"), "parent_input": sha(parent_source),
                   "parent_closure": sha(parent_closure), "closure": sha(RUN / "closure.json"),
                   "model_log": sha(RUN / "model.log"), "report": sha(RUN / "report-raw.json")},
        "manual_inspection": "Installed manual printed p336 (PDF index335) states MINBS, TPTIM and TPTIMD apply only when STPRID is basic FIXED/ONDEM; values on subprofile rows are ignored. Native warning #152 matches this field-level reading.",
        "scope": "The child changes only MINBS null→7, TPTIM null→9 and TPTIMD null→<EXP> on a DOWN-POLICY→REPEAT-FIXED wrapper. Native export retains those authored cells, converter warns #152 Data Ignored, and the complete event log and all non-description report tables equal accepted E10.var05. Effective repeated child FIXED departures remain h8/h11; h8 cancels empty and h11 carries physical spare ID0 for two hours.",
        "limits": ["One wrapper, one repeated FIXED child, one demand, one seed and one general link.",
                   "No deeper nesting, ONDEM child, overlapping windows, multiple demands, mixed batches, GUI-only or cross-engine inference.",
                   "No authored resources or ResourceResults; no resource-capacity claim."],
    }
    OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks_passed": result["checks_passed"],
                      "checks_total": result["checks_total"], "failures": failures}))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
