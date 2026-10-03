"""Independent standard-library replay of sealed E10.var04 native evidence."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
ROOT = CASE.parent
RUN_ID = "e10-var04-directions-v100-ssh-20261003-01"
RUN = CASE / "runs" / RUN_ID
OUT = Path(__file__).with_name("independent-verdict.json")
checks = []


def check(name, ok):
    checks.append({"name": name, "passed": bool(ok)})


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path, native=False):
    value = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",(?=\s*[}\]])", "", value) if native else value)


def tables(document, root="model"):
    return {t["name"]: t for t in document[root]["tables"]}


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
    parent_source = parent_pkg / "native-input-ondem.json"
    parent_run = parent_pkg / "runs" / contract["accepted_parent"]["run_id"]
    parent_closure = parent_run / "closure.json"
    parent_index = parent_pkg / "evidence-index.json"
    check("accepted parent source SHA", sha(parent_source) == contract["accepted_parent"]["input_sha256"])
    check("accepted parent closure SHA", sha(parent_closure) == contract["accepted_parent"]["native_closure_sha256"])
    check("accepted parent index SHA", sha(parent_index) == contract["accepted_parent"]["evidence_index_sha256"])
    check("child input/diff SHA", sha(source_path) == contract["native_input_sha256"] and
          sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"])
    check("diff parent and child identities", diff["parent_sha256"] == sha(parent_source) and
          diff["source_sha256"] == sha(source_path))
    parent = tables(read(parent_source))
    child = tables(read(source_path))
    changed = {name for name in parent.keys() | child.keys() if parent.get(name) != child.get(name)}
    check("exact changed tables", changed == {"ProblemDescription", "StationStructure", "TransportPolicyProfile"} and
          diff["changed_tables"] == ["ProblemDescription", "StationStructure", "TransportPolicyProfile"] and
          diff["unchanged_parent_tables"] == len(parent) - 3)
    for name in sorted(parent.keys() - changed):
        check(f"unchanged authored source {name}", child[name] == parent[name])
    check("exact description before/after", rows(parent["ProblemDescription"])[0] == [diff["description_before"]] and
          rows(child["ProblemDescription"])[0] == [diff["description_after"]])
    old_station = parent["StationStructure"]
    new_station = child["StationStructure"]
    check("station columns and one row", old_station["columns"] == new_station["columns"] and
          len(rows(old_station)) == len(rows(new_station)) == 1)
    old_row, new_row = rows(old_station)[0], rows(new_station)[0]
    ptoms = [column["name"] for column in old_station["columns"]].index("PTOMS")
    check("only station PTOMS null to UP-POLICY", old_row[ptoms] is None and
          new_row[ptoms] == "UP-POLICY" and old_row[:ptoms] + old_row[ptoms + 1:] ==
          new_row[:ptoms] + new_row[ptoms + 1:] and
          diff["station_structure_delta"] == [{"field": "PTOMS", "before": None, "after": "UP-POLICY"}])
    check("downward ONDEM policy unchanged; one upward FIXED row", rows(parent["TransportPolicyProfile"]) ==
          [diff["unchanged_downward_profile_row"]] and rows(child["TransportPolicyProfile"]) ==
          [diff["unchanged_downward_profile_row"], diff["added_upward_profile_row"]] and
          parent["TransportPolicyProfile"]["columns"] == child["TransportPolicyProfile"]["columns"])
    check("upward fixed departure h11, transport2", diff["added_upward_profile_row"][1:4] ==
          ["FIXED", 11, 1] and diff["added_upward_profile_row"][7] == 2)
    check("no authored resource rows", all(not rows(child[name]) for name in
          ("Resource", "ResourceAllocation", "TaskResource")))

    invocation = read(RUN / "invocation.json")
    closure = read(RUN / "closure.json")
    check("closure SHA and run identity", sha(RUN / "closure.json") ==
          "2c963263e3fe4f9c5ebaa550c094f85ea9c3c1b0edfd7072ac060b14314b990d" and
          invocation["run_id"] == closure["run_id"] == RUN_ID)
    check("invocation and source input bind", closure["invocation_sha256"] == sha(RUN / "invocation.json") and
          invocation["input_sha256"] == sha(RUN / "input.json") == sha(source_path))
    pins = closure["source_hashes_before"]
    check("source hashes stable before and after", pins == closure["source_hashes_after"] ==
          invocation["source_hashes_before"])
    source_files = {
        "input": source_path, "parent": parent_source, "parent_closure": parent_closure,
        "parent_index": parent_index, "contract": CASE / "contract.json",
        "exact_diff": CASE / "exact-diff.json", "builder": CASE / "build.py",
        "diff_builder": CASE / "describe_diff.py", "checker": CASE / "check_roundtrip.py",
        "runner_script": CASE / "run_native_ssh.ps1",
    }
    for name, path in sorted(source_files.items()):
        check(f"sealed source {name}", pins[name] == sha(path))
    check("installed exe/manual/dictionary pins", all(pins[key] == contract["source"][description] for key, description in
          (("simlox_exe", "simlox_exe_sha256"), ("manual", "manual_pdf_sha256"),
           ("dictionary", "dictionary_sha256"))))
    check("session0 SSH and mutex", invocation["execution_mode"] == "ssh_cli_v1" and
          invocation["session_id"] == 0 and invocation["ssh_connection_present"] and
          "sshd.exe" in invocation["ssh_ancestor_names"] and
          invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
    check("GUI identity preserved", invocation["gui"]["pid"] == 13340 and
          invocation["gui"]["session_id"] == 1)
    steps = read(RUN / "steps.json")
    check("five guarded successful steps", [step["name"] for step in steps] ==
          ["import", "export", "calc", "jsonreport", "check_import_export"] and
          all(step["exit_code"] == 0 and step["gui_preserved"] for step in steps))
    check("twelve raw seals", len(closure["raw"]) == 12)
    for name, seal in sorted(closure["raw"].items()):
        path = RUN / name
        check(f"sealed raw {name}", path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
    exported = tables(read(RUN / "roundtrip-raw.json", native=True))
    populated = 0
    for name, authored in sorted(child.items()):
        if not rows(authored):
            continue
        populated += 1
        native = exported.get(name)
        equal = native is not None
        if equal:
            width = len(authored["columns"])
            equal = ([column["name"] for column in authored["columns"]] ==
                     [column["name"] for column in native["columns"][:width]] and
                     [instance["rows"] for instance in authored["instances"]] ==
                     [[row[:width] for row in instance["rows"]] for instance in native["instances"]])
        check(f"exact authored row roundtrip {name}", equal)
    check("22 source row-containing tables", populated == 22)
    converter = (RUN / "run.log").read_text(encoding="utf-8-sig")
    check("zero conversion errors and classified warning108", bool(re.search(
          r"Errors:\s*0, Warnings:\s*1, Notes:\s*0", converter)) and
          re.findall(r"warning #(\d+)", converter) == ["108"])
    check("valid SXO/event/report", all((RUN / name).stat().st_size > 1000 for name in
          ("model.sxo", "model.log", "report-raw.json")))

    log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    parent_log = (parent_run / "model.log").read_text(encoding="utf-8-sig")
    evidence = [
        ("0", "scheduled transport task 0 created from <BASE-01,0> to <DEPOT-01,0>, scheduled to start at 11"),
        ("8", "BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting"),
        ("9.8829", "critical random failure added"), ("9.8829", "mission aborted"),
        ("10", "Item demand arrives from pos <TEACH-AIR-01"), ("10", "Backorder added"),
        ("10", "Take replacement item <TEACH-LRU-01,0,0> from stock"),
        ("10", "transport task 2 starts with 1 items/systems, transport time: 2"),
        ("10", "transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> started"),
        ("10.1667", "transport request <<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> attached to  scheduled transport task 0"),
        ("11", "scheduled transport task 0 starts with 1 items/systems, transport time: 2"),
        ("11", "transport request <<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> started"),
        ("12", "transport task 2 arrives with 1 items/systems"),
        ("12", "Replacement item arrives <TEACH-LRU-01,0,0>"),
        ("12", "Backorder removed, waiting time was 2"),
        ("12.3333", "System ready <TEACH-AIR-01,0>"),
        ("13", "scheduled transport task 0 arrives with 1 items/systems"),
        ("13", "Start repair of item <TEACH-LRU-01,0,1>"),
        ("14", "Finished repair of item <TEACH-LRU-01,0,1>"),
        ("14", "Put back replacement item <TEACH-LRU-01,0,1> to stock"),
        ("20", "BASIC-MISSION,TEACH-UNIT,0,0,1> mission starting"),
        ("22", "BASIC-MISSION,TEACH-UNIT,0,0,1> mission success"),
        ("32", "BASIC-MISSION,TEACH-UNIT,0,0,2> mission starting"),
        ("34", "BASIC-MISSION,TEACH-UNIT,0,0,2> mission success"),
    ]
    for hour, fragment in evidence:
        check(f"native event {hour} {fragment}", at(log, hour, fragment))
    check("upward not dispatched at removal time", not at(log, "10.1667", "transport request <<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> started") and
          not any("transport task 0 cancelled" in line for line in log.splitlines()))
    check("parent immediate upward, unchanged downward", at(parent_log, "10.1667", "transport request <<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> started") and
          at(parent_log, "12.1667", "Start repair of item <TEACH-LRU-01,0,1>") and
          at(parent_log, "10", "transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> started"))
    check("two physical transports, both arrived", sum("starts with 1 items/systems" in line for line in log.splitlines()) ==
          sum("arrives with 1 items/systems" in line for line in log.splitlines()) == 2)
    check("one failed item/demand/backorder", sum("critical random failure added" in line for line in log.splitlines()) == 1 and
          sum("Item demand arrives" in line for line in log.splitlines()) == 2 and
          sum("Backorder added" in line for line in log.splitlines()) == 1)
    check("no resource booking", not any("books resources" in line for line in log.splitlines()))

    report = tables(read(RUN / "report-raw.json", native=True), "report")
    parent_report = tables(read(parent_run / "report-raw.json", native=True), "report")
    check("expected report table set", set(report) ==
          {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
        check(f"selected {name} equal parent", report[name] == parent_report[name])
    check("event logs differ despite report equality", sha(RUN / "model.log") != sha(parent_run / "model.log"))
    system, stock, summary = (report[name] for name in ("SystemResults", "StockTotalResults", "ResultSummary"))
    system_rows, stock_rows = rows(system), rows(stock)
    check("72 System and Stock bins", len(system_rows) == len(stock_rows) == 72)
    parent_system_rows = rows(parent_report["SystemResults"])
    parent_stock_rows = rows(parent_report["StockTotalResults"])
    for index, (srow, trow) in enumerate(zip(system_rows, stock_rows)):
        start = index / 2
        check(f"system interval {index}", near(field(system, srow, "STINT"), start, 1e-6) and
              near(field(system, srow, "ETINT"), start + .5, 1e-6))
        check(f"stock interval {index}", near(field(stock, trow, "STINT"), start, 1e-6) and
              near(field(stock, trow, "ETINT"), start + .5, 1e-6))
        check(f"backorder bin {index}", (field(stock, trow, "NBO") or 0) ==
              (1 if 10 <= start < 12 else 0))
        check(f"stock demand bin {index}", (field(stock, trow, "NDF") or 0) ==
              (1 if start == 10 else 0))
        check(f"entire system bin parent equality {index}", srow == parent_system_rows[index])
        check(f"entire stock bin parent equality {index}", trow == parent_stock_rows[index])
    check("two hours of local stock waiting", near(sum((field(stock, r, "WT") or 0) for r in stock_rows), 2))
    check("one system failure/repair", near(sum((field(system, r, "NFAIL") or 0) for r in system_rows), 1) and
          near(sum((field(system, r, "NREPT") or 0) for r in system_rows), 1))
    check("terminal ready1/no aggregate backorder", near(field(system, system_rows[-1], "NSYRY"), 1) and
          (field(stock, stock_rows[-1], "NBO") or 0) == 0)
    summary_row = rows(summary)[0]
    check("one 36h repetition and two of three missions succeed", field(summary, summary_row, "NREP") == 1 and
          field(summary, summary_row, "RTIUP") == 36 and near(field(summary, summary_row, "MSUF"), 2 / 3))

    failures = [item["name"] for item in checks if not item["passed"]]
    result = {
        "schema": "simlox-e10-var04-independent-readonly/v1", "passed": not failures,
        "verdict": "GO_bounded_directional_policy_selection" if not failures else "NO_GO",
        "checks_passed": len(checks) - len(failures), "checks_total": len(checks),
        "failures": failures, "checks": checks,
        "hashes": {"input": sha(source_path), "contract": sha(CASE / "contract.json"),
                   "exact_diff": sha(CASE / "exact-diff.json"), "parent_input": sha(parent_source),
                   "parent_closure": sha(parent_closure), "closure": sha(RUN / "closure.json"),
                   "model_log": sha(RUN / "model.log"), "report": sha(RUN / "report-raw.json")},
        "scope": "In this fixed-seed general station link, PTOMS binds a new upward FIXED h11 policy while PFRMS retains downward ONDEM. Spare ID0 dispatches downward h10 and arrives h12; removed failed ID1 attaches to an h11 task at h10.1667, departs h11, reaches depot h13, and is repaired/restocked h14. The selected aggregate report tables are exactly equal to the parent despite the changed upward physical event times.",
        "limits": ["One upward request and one downward demand, one fixed point, one seed and one link.",
                   "Transport-time override precedence is untested because parent TTOMS and child upward TPTIM both equal two hours.",
                   "No repeated departures, multiple requests, item-specific policy, MINBS, nested profile, GUI-only behavior or cross-engine claim.",
                   "No ResourceResults table is expected: no resource rows are authored; aggregate report equality cannot reveal the upward delay."],
    }
    OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks_passed": result["checks_passed"],
                      "checks_total": result["checks_total"], "failures": failures}))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
