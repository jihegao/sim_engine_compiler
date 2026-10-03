"""Independent read-only standard-library replay of E10.var05 native evidence."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
ROOT = CASE.parent
RUN_ID = "e10-var05-nested-v100-ssh-20261003-01"
RUN = CASE / "runs" / RUN_ID
OUT = Path(__file__).with_name("independent-verdict.json")
checks = []


def check(name, condition):
    checks.append({"name": name, "passed": bool(condition)})


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path, native=False):
    value = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",(?=\s*[}\]])", "", value) if native else value)


def tables(document, root="model"):
    return {table["name"]: table for table in document[root]["tables"]}


def rows(table):
    return [row for instance in table["instances"] for row in instance["rows"]]


def field(table, row, name):
    return row[[column["name"] for column in table["columns"]].index(name)]


def at(log, hour, fragment):
    return any(line.startswith(f"Time: {hour} ") and fragment in line for line in log.splitlines())


def near(a, b, tol=0.0001):
    return math.isclose(float(a), float(b), abs_tol=tol, rel_tol=0)


def main():
    contract = read(CASE / "contract.json")
    diff = read(CASE / "exact-diff.json")
    source_path = CASE / "native-input.json"
    parent_pkg = ROOT / contract["accepted_parent"]["package"]
    parent_source = parent_pkg / "native-input.json"
    parent_run = parent_pkg / "runs" / contract["accepted_parent"]["run_id"]
    parent_closure = parent_run / "closure.json"
    parent_index = parent_pkg / "evidence-index.json"
    check("accepted parent input SHA", sha(parent_source) == contract["accepted_parent"]["input_sha256"])
    check("accepted parent closure SHA", sha(parent_closure) == contract["accepted_parent"]["native_closure_sha256"])
    check("accepted parent evidence index SHA", sha(parent_index) == contract["accepted_parent"]["evidence_index_sha256"])
    check("child source/diff SHA", sha(source_path) == contract["native_input_sha256"] and
          sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"])
    check("diff parent/child binding", diff["parent_sha256"] == sha(parent_source) and
          diff["source_sha256"] == sha(source_path))
    parent = tables(read(parent_source))
    child = tables(read(source_path))
    changed = {name for name in parent.keys() | child.keys() if parent.get(name) != child.get(name)}
    check("only description and profile changed", changed == {"ProblemDescription", "TransportPolicyProfile"} and
          diff["changed_tables"] == ["ProblemDescription", "TransportPolicyProfile"] and
          diff["unchanged_parent_tables"] == len(parent) - 2)
    for name in sorted(parent.keys() - changed):
        check(f"unchanged source {name}", child[name] == parent[name])
    check("description before/after exact", rows(parent["ProblemDescription"]) == [[diff["description_before"]]] and
          rows(child["ProblemDescription"]) == [[diff["description_after"]]])
    check("native profile schema stable", parent["TransportPolicyProfile"]["columns"] ==
          child["TransportPolicyProfile"]["columns"])
    check("flat parent and nested child rows exact", rows(parent["TransportPolicyProfile"]) ==
          diff["parent_flat_rows"] and rows(child["TransportPolicyProfile"]) == diff["child_nested_rows"])
    wrapper, leaf = rows(child["TransportPolicyProfile"])
    check("source-bound two h8/h11 repeated FIXED points", wrapper[:5] ==
          ["DOWN-POLICY", "REPEAT-FIXED", 8, 2, 3] and leaf[:5] ==
          ["REPEAT-FIXED", "FIXED", 0, 1, 0] and leaf[7] == 2 and
          [wrapper[2] + n * wrapper[4] + leaf[2] for n in range(wrapper[3])] == [8, 11])
    check("no resource source rows", all(not rows(child[name]) for name in
          ("Resource", "ResourceAllocation", "TaskResource")))

    invocation = read(RUN / "invocation.json")
    closure = read(RUN / "closure.json")
    check("run identity", invocation["run_id"] == closure["run_id"] == RUN_ID)
    check("invocation/input SHA bind", closure["invocation_sha256"] == sha(RUN / "invocation.json") and
          invocation["input_sha256"] == sha(RUN / "input.json") == sha(source_path))
    pins = closure["source_hashes_before"]
    check("source hashes frozen across run", pins == closure["source_hashes_after"] ==
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
    check("installed runtime/manual/dictionary fingerprints", all(
          pins[name] == contract["source"][key] for name, key in
          (("simlox_exe", "simlox_exe_sha256"), ("manual", "manual_pdf_sha256"),
           ("dictionary", "dictionary_sha256"))))
    check("SSH0 and queue", invocation["execution_mode"] == "ssh_cli_v1" and
          invocation["session_id"] == 0 and invocation["ssh_connection_present"] and
          "sshd.exe" in invocation["ssh_ancestor_names"] and
          invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
    check("GUI identity", invocation["gui"]["pid"] == 13340 and
          invocation["gui"]["session_id"] == 1)
    steps = read(RUN / "steps.json")
    check("five successful guarded steps", [step["name"] for step in steps] ==
          ["import", "export", "calc", "jsonreport", "check_import_export"] and
          all(step["exit_code"] == 0 and step["gui_preserved"] for step in steps))
    check("twelve sealed raw files", len(closure["raw"]) == 12)
    for name, seal in sorted(closure["raw"].items()):
        path = RUN / name
        check(f"raw seal {name}", path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
    exported = tables(read(RUN / "roundtrip-raw.json", native=True))
    populated = 0
    for name, authored in sorted(child.items()):
        if not rows(authored):
            continue
        populated += 1
        target = exported.get(name)
        equal = target is not None
        if equal:
            width = len(authored["columns"])
            equal = ([column["name"] for column in authored["columns"]] ==
                     [column["name"] for column in target["columns"][:width]] and
                     [instance["rows"] for instance in authored["instances"]] ==
                     [[row[:width] for row in instance["rows"]] for instance in target["instances"]])
        check(f"exact authored roundtrip {name}", equal)
    check("22 source row-containing tables", populated == 22)
    converter = (RUN / "run.log").read_text(encoding="utf-8-sig")
    check("zero converter errors, warning108, no notes", bool(re.search(
          r"Errors:\s*0, Warnings:\s*1, Notes:\s*0", converter)) and
          re.findall(r"warning #(\d+)", converter) == ["108"])
    check("valid SXO, log and report", all((RUN / name).stat().st_size > 1000 for name in
          ("model.sxo", "model.log", "report-raw.json")))

    log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    check("entire event log byte-identical to flat parent", sha(RUN / "model.log") == sha(parent_run / "model.log"))
    events = [
        ("0", "scheduled transport task 0 created from <DEPOT-01,0> to <BASE-01,0>, scheduled to start at 8"),
        ("8", "scheduled transport task 1 created from <DEPOT-01,0> to <BASE-01,0>, scheduled to start at 11"),
        ("8", "scheduled transport task 0 cancelled with 0 items/systems"),
        ("9.8829", "critical random failure added"),
        ("9.8829", "BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted"),
        ("10", "Item demand arrives from pos <TEACH-AIR-01"),
        ("10", "Backorder added"),
        ("10", "Take replacement item <TEACH-LRU-01,0,0> from stock"),
        ("10", "transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> attached to  scheduled transport task 1"),
        ("10.1667", "transport task 2 starts with 1 items/systems, transport time: 2"),
        ("11", "scheduled transport task 1 starts with 1 items/systems, transport time: 2"),
        ("11", "transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> started"),
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
    check("only two planned finite downward points", sum("scheduled transport task" in line and
          "created from <DEPOT-01,0> to <BASE-01,0>, scheduled to start at 8" in line for line in log.splitlines()) == 1 and
          sum("scheduled transport task" in line and
          "created from <DEPOT-01,0> to <BASE-01,0>, scheduled to start at 11" in line for line in log.splitlines()) == 1)
    check("empty h8 has no physical shipment", not at(log, "8", "transport task 0 starts with") and
          not at(log, "8", "Take replacement item"))
    check("two physical transports close by horizon", sum("starts with 1 items/systems" in line for line in log.splitlines()) ==
          sum("arrives with 1 items/systems" in line for line in log.splitlines()) == 2)
    check("no resource allocation", not any("books resources" in line for line in log.splitlines()))

    report = tables(read(RUN / "report-raw.json", native=True), "report")
    parent_report = tables(read(parent_run / "report-raw.json", native=True), "report")
    check("selected report tables only", set(report) ==
          {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
        check(f"{name} exact flat-parent equality", report[name] == parent_report[name])
    system, stock, summary = (report[name] for name in ("SystemResults", "StockTotalResults", "ResultSummary"))
    system_rows, stock_rows = rows(system), rows(stock)
    parent_system_rows = rows(parent_report["SystemResults"])
    parent_stock_rows = rows(parent_report["StockTotalResults"])
    check("72 System and Stock half-hour bins", len(system_rows) == len(stock_rows) == 72)
    for index, (srow, trow) in enumerate(zip(system_rows, stock_rows)):
        start = index / 2
        check(f"system interval {index}", near(field(system, srow, "STINT"), start, 1e-6) and
              near(field(system, srow, "ETINT"), start + .5, 1e-6))
        check(f"stock interval {index}", near(field(stock, trow, "STINT"), start, 1e-6) and
              near(field(stock, trow, "ETINT"), start + .5, 1e-6))
        check(f"stock NBO {index}", (field(stock, trow, "NBO") or 0) ==
              (1 if 10 <= start < 13 else 0))
        check(f"stock NDF {index}", (field(stock, trow, "NDF") or 0) ==
              (1 if start == 10 else 0))
        check(f"entire SystemResults bin equals parent {index}", srow == parent_system_rows[index])
        check(f"entire StockTotalResults bin equals parent {index}", trow == parent_stock_rows[index])
    check("three stock waiting hours", near(sum((field(stock, row, "WT") or 0) for row in stock_rows), 3))
    check("one system fault and repair", near(sum((field(system, row, "NFAIL") or 0) for row in system_rows), 1) and
          near(sum((field(system, row, "NREPT") or 0) for row in system_rows), 1))
    check("terminal ready1, backorder0", near(field(system, system_rows[-1], "NSYRY"), 1) and
          (field(stock, stock_rows[-1], "NBO") or 0) == 0)
    summary_row = rows(summary)[0]
    check("one 36h repetition, two of three missions succeed", field(summary, summary_row, "NREP") == 1 and
          field(summary, summary_row, "RTIUP") == 36 and near(field(summary, summary_row, "MSUF"), 2 / 3))

    failed = [item["name"] for item in checks if not item["passed"]]
    result = {
        "schema": "simlox-e10-var05-independent-readonly/v1", "passed": not failed,
        "verdict": "GO_bounded_nested_repeated_FIXED_equivalence" if not failed else "NO_GO",
        "checks_passed": len(checks) - len(failed), "checks_total": len(checks),
        "failures": failed, "checks": checks,
        "hashes": {"input": sha(source_path), "contract": sha(CASE / "contract.json"),
                   "exact_diff": sha(CASE / "exact-diff.json"), "parent_input": sha(parent_source),
                   "parent_closure": sha(parent_closure), "closure": sha(RUN / "closure.json"),
                   "model_log": sha(RUN / "model.log"), "report": sha(RUN / "report-raw.json")},
        "scope": "The nested child FIXED row under an IQTY2/IINT3 wrapper yields native h8 and h11 scheduled departures. The empty h8 task explicitly cancels; the h10 demand binds spare ID0 to h11, which delivers at h13. The complete native event log and all non-description report tables are byte/structurally identical to accepted flat E10.var02 for this seed and model.",
        "limits": ["One nesting level, one repeated FIXED child, two points, one demand, one seed and one downward link.",
                   "No multi-level nesting, ONDEM child repetition, mixed child policies, boundary priority, batching, transport-time override, GUI-only or cross-engine inference.",
                   "No resource rows or ResourceResults are authored; no capacity inference."],
    }
    OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks_passed": result["checks_passed"],
                      "checks_total": result["checks_total"], "failures": failed}))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
