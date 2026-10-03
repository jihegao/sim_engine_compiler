"""Independent standard-library replay of sealed E10.var03 native evidence.

Reads authored sources and native raw files; never calls SIMLOX or author code.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
ROOT = CASE.parent
RUN_ID = "e10-var03-gap-v100-ssh-20261003-01"
RUN = CASE / "runs" / RUN_ID
OUT = Path(__file__).with_name("independent-verdict.json")
checks = []


def check(name, condition):
    checks.append({"name": name, "passed": bool(condition)})


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path, native=False):
    value = path.read_text(encoding="utf-8-sig")
    if native:
        value = re.sub(r",(?=\s*[}\]])", "", value)
    return json.loads(value)


def tables(document, root="model"):
    return {table["name"]: table for table in document[root]["tables"]}


def rows(table):
    return [row for instance in table["instances"] for row in instance["rows"]]


def field(table, row, name):
    index = [column["name"] for column in table["columns"]].index(name)
    return row[index]


def at(log, hour, phrase):
    return any(line.startswith(f"Time: {hour} ") and phrase in line
               for line in log.splitlines())


def near(actual, expected, tolerance=0.0001):
    return math.isclose(float(actual), float(expected), abs_tol=tolerance, rel_tol=0)


def main():
    contract = read(CASE / "contract.json")
    diff = read(CASE / "exact-diff.json")
    prior = ROOT / contract["accepted_parent"]["package"]
    parent_source = prior / "native-input-ondem.json"
    parent_run = prior / "runs" / contract["accepted_parent"]["run_id"]
    fixed_source = prior / "native-input-fixed.json"
    fixed_run = prior / "runs" / contract["accepted_comparator"]["run_id"]
    parent_closure = parent_run / "closure.json"
    fixed_closure = fixed_run / "closure.json"
    parent_index = prior / "evidence-index.json"
    source_path = CASE / "native-input.json"
    check("accepted ONDEM parent source SHA", sha(parent_source) == contract["accepted_parent"]["input_sha256"])
    check("accepted ONDEM parent closure SHA", sha(parent_closure) == contract["accepted_parent"]["native_closure_sha256"])
    check("accepted parent index SHA", sha(parent_index) == contract["accepted_parent"]["evidence_index_sha256"])
    check("accepted FIXED comparator source SHA", sha(fixed_source) == contract["accepted_comparator"]["input_sha256"])
    check("accepted FIXED comparator closure SHA", sha(fixed_closure) == contract["accepted_comparator"]["native_closure_sha256"])
    check("child source and diff SHA", sha(source_path) == contract["native_input_sha256"] and
          sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"])
    check("exact diff source identities", diff["parent_sha256"] == sha(parent_source) and
          diff["source_sha256"] == sha(source_path))
    parent = tables(read(parent_source))
    child = tables(read(source_path))
    changed = {name for name in parent.keys() | child.keys() if parent.get(name) != child.get(name)}
    check("only two changed source tables", changed == {"ProblemDescription", "TransportPolicyProfile"} and
          diff["changed_tables"] == ["ProblemDescription", "TransportPolicyProfile"] and
          len(parent) - len(changed) == diff["unchanged_parent_tables"])
    for name in sorted(parent.keys() - changed):
        check(f"source unchanged table {name}", child[name] == parent[name])
    check("description exact before and after", rows(parent["ProblemDescription"])[0][0] == diff["description_before"] and
          rows(child["ProblemDescription"])[0][0] == diff["description_after"])
    check("policy column schema unchanged", parent["TransportPolicyProfile"]["columns"] ==
          child["TransportPolicyProfile"]["columns"])
    check("policy exact ONDEM rows and windows", rows(parent["TransportPolicyProfile"]) ==
          [diff["old_profile_row"]] and rows(child["TransportPolicyProfile"]) ==
          diff["new_profile_rows"] and [[row[2], row[5]] for row in diff["new_profile_rows"]] == [[0, 9], [11, 25]])

    invocation = read(RUN / "invocation.json")
    closure = read(RUN / "closure.json")
    check("child closure SHA and identity", sha(RUN / "closure.json") ==
          "a179aa56096ce3d813505a8ee98c261cd6f57d5a2a4e2331bea2fdbefb9595ac" and
          invocation["run_id"] == closure["run_id"] == RUN_ID)
    check("invocation and source input bind", closure["invocation_sha256"] == sha(RUN / "invocation.json") and
          invocation["input_sha256"] == sha(source_path) == sha(RUN / "input.json"))
    pins = closure["source_hashes_before"]
    check("stable frozen source hashes", pins == closure["source_hashes_after"] == invocation["source_hashes_before"])
    source_files = {
        "input": source_path, "parent": parent_source, "parent_closure": parent_closure,
        "parent_index": parent_index, "comparator": fixed_source,
        "comparator_closure": fixed_closure, "contract": CASE / "contract.json",
        "exact_diff": CASE / "exact-diff.json", "builder": CASE / "build.py",
        "diff_builder": CASE / "describe_diff.py", "checker": CASE / "check_roundtrip.py",
        "runner_script": CASE / "run_native_ssh.ps1",
    }
    for name, path in sorted(source_files.items()):
        check(f"sealed source {name}", pins[name] == sha(path))
    check("installed runtime/manual/dictionary fingerprints", all(
          pins[name] == contract["source"][key] for name, key in
          (("simlox_exe", "simlox_exe_sha256"), ("manual", "manual_pdf_sha256"),
           ("dictionary", "dictionary_sha256"))))
    check("SSH session0 and queue guard", invocation["execution_mode"] == "ssh_cli_v1" and
          invocation["session_id"] == 0 and invocation["ssh_connection_present"] and
          "sshd.exe" in invocation["ssh_ancestor_names"] and
          invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
    check("GUI preserved identity", invocation["gui"]["pid"] == 13340 and
          invocation["gui"]["session_id"] == 1)
    steps = read(RUN / "steps.json")
    check("five native/check steps", [step["name"] for step in steps] ==
          ["import", "export", "calc", "jsonreport", "check_import_export"] and
          all(step["exit_code"] == 0 and step["gui_preserved"] for step in steps))
    check("twelve sealed raw files", len(closure["raw"]) == 12)
    for name, seal in sorted(closure["raw"].items()):
        path = RUN / name
        check(f"sealed raw {name}", path.stat().st_size == seal["bytes"] and
              sha(path) == seal["sha256"])
    exported = tables(read(RUN / "roundtrip-raw.json", native=True))
    count = 0
    for name, authored in sorted(child.items()):
        if not rows(authored):
            continue
        count += 1
        native = exported.get(name)
        equal = native is not None
        if equal:
            width = len(authored["columns"])
            equal = ([col["name"] for col in authored["columns"]] ==
                     [col["name"] for col in native["columns"][:width]] and
                     [instance["rows"] for instance in authored["instances"]] ==
                     [[row[:width] for row in instance["rows"]] for instance in native["instances"]])
        check(f"exact source roundtrip {name}", equal)
    check("22 source row-containing tables", count == 22)
    convert = (RUN / "run.log").read_text(encoding="utf-8-sig")
    check("converter zero errors warning108 notes0", bool(re.search(
          r"Errors:\s*0, Warnings:\s*1, Notes:\s*0", convert)) and
          re.findall(r"warning #(\d+)", convert) == ["108"])
    check("valid result files", all((RUN / name).stat().st_size > 1000 for name in
          ("model.sxo", "model.log", "report-raw.json")))

    log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    parent_log = (parent_run / "model.log").read_text(encoding="utf-8-sig")
    fixed_log = (fixed_run / "model.log").read_text(encoding="utf-8-sig")
    events = [
        ("0", "Stock initiated"), ("0", "scheduled transport task 0 created from <DEPOT-01,0> to <BASE-01,0>, scheduled to start at 11"),
        ("8", "mission starting, duration: 2"), ("9.8829", "critical random failure added"),
        ("9.8829", "mission aborted"), ("10", "Item demand arrives from pos <TEACH-AIR-01"),
        ("10", "Backorder added"), ("10", "Take replacement item <TEACH-LRU-01,0,0> from stock"),
        ("10", "transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> attached to  scheduled transport task 0"),
        ("10.1667", "transport task 1 starts with 1 items/systems, transport time: 2"),
        ("11", "scheduled transport task 0 starts with 1 items/systems, transport time: 2"),
        ("11", "transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> started"),
        ("12.1667", "transport task 1 arrives with 1 items/systems"),
        ("12.1667", "Start repair of item <TEACH-LRU-01,0,1>"),
        ("13", "scheduled transport task 0 arrives with 1 items/systems"),
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
    for hour, phrase in events:
        check(f"native event {hour} {phrase}", at(log, hour, phrase))
    check("demand remains queued through gap; no h10 dispatch", not at(log, "10", "scheduled transport task 0 starts") and
          not at(log, "10", "transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> started") and
          not any("transport task 0 cancelled" in line for line in log.splitlines()))
    check("two item demands only at h10", sum("Item demand arrives" in line for line in log.splitlines()) == 2 and
          all(line.startswith("Time: 10 ") for line in log.splitlines() if "Item demand arrives" in line))
    check("all physical shipments arrived by horizon", sum("starts with 1 items/systems" in line for line in log.splitlines()) ==
          sum("arrives with 1 items/systems" in line for line in log.splitlines()) == 2)
    check("parent ONDEM earlier dispatch/arrival", at(parent_log, "10", "transport task 1 starts with 1 items/systems") and
          at(parent_log, "12", "transport task 1 arrives with 1 items/systems") and
          at(parent_log, "12", "Backorder removed, waiting time was 2"))
    check("fixed comparator same spare dispatch/arrival", at(fixed_log, "11", "scheduled transport task 0 starts with 1 items/systems") and
          at(fixed_log, "13", "scheduled transport task 0 arrives with 1 items/systems") and
          at(fixed_log, "13", "Backorder removed, waiting time was 3"))
    check("no later failure or inventory demand", sum("critical random failure added" in line for line in log.splitlines()) == 1 and
          sum("Backorder added" in line for line in log.splitlines()) == 1)

    report = tables(read(RUN / "report-raw.json", native=True), "report")
    fixed_report = tables(read(fixed_run / "report-raw.json", native=True), "report")
    parent_report = tables(read(parent_run / "report-raw.json", native=True), "report")
    check("report table set", set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
        check(f"{name} exact match to accepted FIXED", report[name] == fixed_report[name])
    check("earlier ONDEM differs only in time ledgers", report["ResultSummary"] == parent_report["ResultSummary"] and
          report["SystemResults"] != parent_report["SystemResults"] and
          report["StockTotalResults"] != parent_report["StockTotalResults"])
    system = report["SystemResults"]
    stock = report["StockTotalResults"]
    summary = report["ResultSummary"]
    sr, st = rows(system), rows(stock)
    check("72 half-hour System and Stock bins", len(sr) == len(st) == 72)
    for index, (srow, trow) in enumerate(zip(sr, st)):
        start = index / 2
        end = start + .5
        check(f"system interval {index}", near(field(system, srow, "STINT"), start, 1e-6) and
              near(field(system, srow, "ETINT"), end, 1e-6))
        check(f"stock interval {index}", near(field(stock, trow, "STINT"), start, 1e-6) and
              near(field(stock, trow, "ETINT"), end, 1e-6))
        check(f"stock backorder {index}", (field(stock, trow, "NBO") or 0) == (1 if 10 <= start < 13 else 0))
        check(f"stock demand {index}", (field(stock, trow, "NDF") or 0) == (1 if start == 10 else 0))
        check(f"system bin matches FIXED {index}", srow == rows(fixed_report["SystemResults"])[index])
        check(f"stock bin matches FIXED {index}", trow == rows(fixed_report["StockTotalResults"])[index])
    check("three stock waiting hours", near(sum((field(stock, row, "WT") or 0) for row in st), 3))
    check("one system failure/repair", near(sum((field(system, row, "NFAIL") or 0) for row in sr), 1) and
          near(sum((field(system, row, "NREPT") or 0) for row in sr), 1))
    check("h13 partial readiness and terminal ready", near(field(system, sr[26], "NSYRY"), 1 / 3) and
          near(field(system, sr[-1], "NSYRY"), 1) and (field(stock, st[-1], "NBO") or 0) == 0)
    result_row = rows(summary)[0]
    check("36h repetition; two of three missions succeed", field(summary, result_row, "NREP") == 1 and
          field(summary, result_row, "RTIUP") == 36 and near(field(summary, result_row, "MSUF"), 2 / 3))

    failed = [entry["name"] for entry in checks if not entry["passed"]]
    result = {
        "schema": "simlox-e10-var03-independent-readonly/v1", "passed": not failed,
        "verdict": "GO_bounded_ONDEM_gap_queue_and_resume" if not failed else "NO_GO",
        "checks_passed": len(checks) - len(failed), "checks_total": len(checks),
        "failures": failed, "checks": checks,
        "hashes": {"input": sha(source_path), "contract": sha(CASE / "contract.json"),
                   "exact_diff": sha(CASE / "exact-diff.json"), "parent_input": sha(parent_source),
                   "parent_closure": sha(parent_closure), "fixed_input": sha(fixed_source),
                   "fixed_closure": sha(fixed_closure), "closure": sha(RUN / "closure.json"),
                   "model_log": sha(RUN / "model.log"), "report": sha(RUN / "report-raw.json")},
        "scope": "At fixed seed1, an h10 item demand during the h9-11 ONDEM policy gap reserves physical depot spare ID0 and attaches its request to an h11 scheduled task; the same request starts h11, arrives h13, clears the three-hour local backorder, and restores aircraft readiness h13.3333. Failed ID1 travels upward, is repaired, and returns to depot stock. The selected 72-bin System and Stock results equal accepted FIXED and differ in time bins from continuous ONDEM.",
        "limits": ["One demand in one two-hour gap with one reopening, one seed and one downward link.",
                   "No multiple demands, exact-boundary request, no-reopening case, batching, other station mode, GUI-only behavior, or cross-engine inference.",
                   "ResourceResults is absent because no resource rows are authored; no resource capacity claim."],
    }
    OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks_passed": result["checks_passed"],
                      "checks_total": result["checks_total"], "failures": failed}))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
