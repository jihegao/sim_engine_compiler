"""Independent standard-library, read-only E10.var06 raw evidence replay."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
ROOT = CASE.parent
OUT = Path(__file__).with_name("independent-verdict.json")
RUN_IDS = {
    "minbs1": "e10-var06-minbs1-v100-ssh-20261003-01",
    "minbs2": "e10-var06-minbs2-v100-ssh-20261003-01",
}
checks = []


def check(name, ok):
    checks.append({"name": name, "passed": bool(ok)})


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path, native=False):
    raw = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",(?=\s*[}\]])", "", raw) if native else raw)


def tables(doc, root="model"):
    return {t["name"]: t for t in doc[root]["tables"]}


def rows(table):
    return [r for instance in table["instances"] for r in instance["rows"]]


def field(table, row, name):
    return row[[c["name"] for c in table["columns"]].index(name)]


def at(log, time, phrase):
    return any(line.startswith(f"Time: {time} ") and phrase in line for line in log.splitlines())


def near(value, expected, tol=0.001):
    return math.isclose(float(value), float(expected), abs_tol=tol, rel_tol=0)


def occupancy(start, end, segments):
    return sum(max(0.0, min(end, finish) - max(start, begin)) * count
               for begin, finish, count in segments) / (end - start)


def changed_columns(left, right):
    diff = set()
    for lrow, rrow in zip(rows(left), rows(right)):
        for index, column in enumerate(left["columns"]):
            if lrow[index] != rrow[index]:
                diff.add(column["name"])
    return diff


def main():
    contract = read(CASE / "contract.json")
    diff = read(CASE / "exact-diff.json")
    parent_pkg = ROOT / contract["accepted_parent"]["package"]
    parent_source = parent_pkg / "native-input-ondem.json"
    parent_closure = parent_pkg / "runs" / contract["accepted_parent"]["run_id"] / "closure.json"
    parent_index = parent_pkg / "evidence-index.json"
    support_pkg = ROOT / contract["accepted_support"]["package"]
    support_source = support_pkg / "native-input.json"
    support_closure = support_pkg / "runs" / contract["accepted_support"]["run_id"] / "closure.json"
    support_signoff = support_pkg / "cli-scope-signoff-2026-09-29.md"
    input_paths = {arm: CASE / f"native-input-{arm}.json" for arm in RUN_IDS}
    check("E10 parent source/closure/index pins", sha(parent_source) == contract["accepted_parent"]["input_sha256"] and
          sha(parent_closure) == contract["accepted_parent"]["native_closure_sha256"] and
          sha(parent_index) == contract["accepted_parent"]["evidence_index_sha256"])
    check("E03 supporting source/closure/signoff pins", sha(support_source) == contract["accepted_support"]["input_sha256"] and
          sha(support_closure) == contract["accepted_support"]["native_closure_sha256"] and
          sha(support_signoff) == contract["accepted_support"]["signoff_sha256"])
    check("both arm inputs and exact diff SHA", all(sha(path) == contract["native_inputs_sha256"][arm]
          for arm, path in input_paths.items()) and sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"])
    check("diff lineage pins", diff["parent_sha256"] == sha(parent_source) and
          diff["support_e03_sha256"] == sha(support_source) and
          diff["arm1_sha256"] == sha(input_paths["minbs1"]) and
          diff["arm2_sha256"] == sha(input_paths["minbs2"]))
    parent = tables(read(parent_source))
    arms = {arm: tables(read(path)) for arm, path in input_paths.items()}
    a, b = arms["minbs1"], arms["minbs2"]
    pchanged = {name for name in parent.keys() | a.keys() if parent.get(name) != a.get(name)}
    achanged = {name for name in a.keys() | b.keys() if a.get(name) != b.get(name)}
    check("parent to MINBS1 exact table set", pchanged == set(diff["changed_tables_parent_to_arm1"]) and
          diff["unchanged_tables_parent_to_arm1"] == len(parent) - len(pchanged))
    check("MINBS arms exact table set", achanged == {"ProblemDescription", "TransportPolicyProfile"} and
          diff["changed_tables_arm1_to_arm2"] == ["ProblemDescription", "TransportPolicyProfile"] and
          diff["unchanged_tables_between_arms"] == len(a) - len(achanged))
    for name in sorted(parent.keys() - pchanged):
        check(f"parent table preserved {name}", a[name] == parent[name])
    for name in sorted(a.keys() - achanged):
        check(f"arm table preserved {name}", b[name] == a[name])
    check("common System and Item FRT-only edits", all(changed_columns(parent[name], a[name]) == {"FRT"} and
          field(a[name], rows(a[name])[0], "FRT") == 3000000 and
          field(parent[name], rows(parent[name])[0], "FRT") == 300000 for name in ("System", "Item")))
    check("two deployed aircraft", changed_columns(parent["SystemDeployment"], a["SystemDeployment"]) ==
          {"QTYPS"} and field(a["SystemDeployment"], rows(a["SystemDeployment"])[0], "QTYPS") == 2)
    check("one h8 two-mission scheduled row", len(rows(a["OperationProfile"])) == 1 and
          field(a["OperationProfile"], rows(a["OperationProfile"])[0], "STIM") == 8 and
          field(a["OperationProfile"], rows(a["OperationProfile"])[0], "IQTY") == 2)
    check("depot opening stock two, base zero", len(rows(a["StockAllocation"])) == 2 and
          [field(a["StockAllocation"], row, "STSIZ") for row in rows(a["StockAllocation"])] == [0, 2])
    check("profile MINBS only 1 to 2", rows(a["TransportPolicyProfile"]) == [diff["arm1_policy_row"]] and
          rows(b["TransportPolicyProfile"]) == [diff["arm2_policy_row"]] and
          changed_columns(a["TransportPolicyProfile"], b["TransportPolicyProfile"]) == {"MINBS"})
    check("no authored resource rows", all(not rows(a[name]) for name in
          ("Resource", "ResourceAllocation", "TaskResource")))

    reports = {}
    logs = {}
    run_hashes = {}
    for arm in RUN_IDS:
        run = CASE / "runs" / RUN_IDS[arm]
        invocation = read(run / "invocation.json")
        closure = read(run / "closure.json")
        source_path = input_paths[arm]
        prefix = arm
        check(f"{prefix} invocation/closure identity", invocation["run_id"] == closure["run_id"] == RUN_IDS[arm] and
              closure["invocation_sha256"] == sha(run / "invocation.json"))
        check(f"{prefix} source input binding", invocation["input_sha256"] == sha(run / "input.json") ==
              sha(source_path))
        pins = closure["source_hashes_before"]
        check(f"{prefix} frozen source hashes", pins == closure["source_hashes_after"] ==
              invocation["source_hashes_before"])
        source_files = {
            "input": source_path, "parent": parent_source, "parent_closure": parent_closure,
            "parent_index": parent_index, "support": support_source,
            "support_closure": support_closure, "support_signoff": support_signoff,
            "contract": CASE / "contract.json", "exact_diff": CASE / "exact-diff.json",
            "builder": CASE / "build.py", "diff_builder": CASE / "describe_diff.py",
            "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1",
        }
        for name, path in sorted(source_files.items()):
            check(f"{prefix} sealed source {name}", pins[name] == sha(path))
        check(f"{prefix} installed exe/manual/dictionary pins", all(
              pins[name] == contract["source"][key] for name, key in
              (("simlox_exe", "simlox_exe_sha256"), ("manual", "manual_pdf_sha256"),
               ("dictionary", "dictionary_sha256"))))
        check(f"{prefix} SSH0 and mutex", invocation["execution_mode"] == "ssh_cli_v1" and
              invocation["session_id"] == 0 and invocation["ssh_connection_present"] and
              "sshd.exe" in invocation["ssh_ancestor_names"] and
              invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
        check(f"{prefix} GUI preserved identity", invocation["gui"]["pid"] == 13340 and
              invocation["gui"]["session_id"] == 1)
        steps = read(run / "steps.json")
        check(f"{prefix} five guarded successful steps", [step["name"] for step in steps] ==
              ["import", "export", "calc", "jsonreport", "check_import_export"] and
              all(step["exit_code"] == 0 and step["gui_preserved"] for step in steps))
        check(f"{prefix} twelve raw seals", len(closure["raw"]) == 12)
        for name, seal in sorted(closure["raw"].items()):
            path = run / name
            check(f"{prefix} raw SHA {name}", path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
        exported = tables(read(run / "roundtrip-raw.json", native=True))
        count = 0
        for name, authored in sorted(arms[arm].items()):
            if not rows(authored):
                continue
            count += 1
            target = exported.get(name)
            equal = target is not None
            if equal:
                width = len(authored["columns"])
                equal = ([col["name"] for col in authored["columns"]] ==
                         [col["name"] for col in target["columns"][:width]] and
                         [inst["rows"] for inst in authored["instances"]] ==
                         [[row[:width] for row in inst["rows"]] for inst in target["instances"]])
            check(f"{prefix} exact authored table {name}", equal)
        check(f"{prefix} 22 row-containing tables", count == 22)
        converter = (run / "run.log").read_text(encoding="utf-8-sig")
        check(f"{prefix} zero converter errors/warning108", bool(re.search(
              r"Errors:\s*0, Warnings:\s*1, Notes:\s*0", converter)) and
              re.findall(r"warning #(\d+)", converter) == ["108"])
        check(f"{prefix} valid result outputs", all((run / name).stat().st_size > 1000 for name in
              ("model.sxo", "model.log", "report-raw.json")))
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        logs[arm] = log
        reports[arm] = tables(read(run / "report-raw.json", native=True), "report")
        run_hashes[arm] = {"closure": sha(run / "closure.json"), "model_log": sha(run / "model.log"),
                           "report": sha(run / "report-raw.json")}

    for arm, log in logs.items():
        prefix = arm
        common_events = [
            ("0", "Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 2"),
            ("8", "BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting"),
            ("8", "BASIC-MISSION,TEACH-UNIT,0,0,1> mission starting"),
            ("8.18829", "TEACH-AIR-01,0> critical random failure added"),
            ("8.31325", "TEACH-AIR-01,1> critical random failure added"),
            ("8.18829", "BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted"),
            ("8.31325", "BASIC-MISSION,TEACH-UNIT,0,0,1> mission aborted"),
            ("8.37658", "Item demand arrives from pos <TEACH-AIR-01"),
            ("8.6265", "Item demand arrives from pos <TEACH-AIR-01"),
            ("8.37658", "Take replacement item <TEACH-LRU-01,0,0> from stock"),
            ("8.6265", "Take replacement item <TEACH-LRU-01,0,1> from stock"),
            ("8.54325", "transport request <<TEACH-LRU-01,0,2>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> started"),
            ("8.79317", "transport request <<TEACH-LRU-01,0,3>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> started"),
            ("10.5432", "Start repair of item <TEACH-LRU-01,0,2>"),
            ("10.7932", "Start repair of item <TEACH-LRU-01,0,3>"),
            ("11.5432", "Finished repair of item <TEACH-LRU-01,0,2>"),
            ("11.7932", "Finished repair of item <TEACH-LRU-01,0,3>"),
            ("11.5432", "Put back replacement item <TEACH-LRU-01,0,2> to stock"),
            ("11.7932", "Put back replacement item <TEACH-LRU-01,0,3> to stock"),
        ]
        for time, fragment in common_events:
            if time == "0":
                check(f"{prefix} initial depot stock two IDs", "Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 2 Items:<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,1>," in log)
            else:
                check(f"{prefix} native {time} {fragment}", at(log, time, fragment))
        check(f"{prefix} exactly two local and two depot demands", sum("Item demand arrives" in line for line in log.splitlines()) == 4 and
              sum("Item demand arrives from pos <TEACH-AIR-01" in line for line in log.splitlines()) == 2)
        check(f"{prefix} physical failed IDs2/3 and spare IDs0/1", all(f"subitem failed: <TEACH-LRU-01,0,{n}>" in log for n in (2, 3)) and
              all(f"Take replacement item <TEACH-LRU-01,0,{n}> from stock" in log for n in (0, 1)))
        check(f"{prefix} no resources or mission success", not any("books resources" in line for line in log.splitlines()) and
              not any("mission success:" in line for line in log.splitlines()))
        check(f"{prefix} terminal two ready and depot stock IDs2/3", "systems ready: 2 :<TEACH-AIR-01,0>,<TEACH-AIR-01,1>" in log and
              "Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 2 Items:<TEACH-LRU-01,0,2>,<TEACH-LRU-01,0,3>," in log)

    one, two = logs["minbs1"], logs["minbs2"]
    check("MINBS1 first immediate single-item dispatch", at(one, "8.37658", "transport task 1 starts with 1 items/systems") and
          at(one, "8.37658", "transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> started"))
    check("MINBS1 second immediate single-item dispatch", at(one, "8.6265", "transport task 4 starts with 1 items/systems") and
          at(one, "8.6265", "transport request <<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> started"))
    check("MINBS1 separate downward arrivals and two-hour backorders", all(at(one, t, text) for t, text in (
          ("10.3766", "transport task 1 arrives with 1 items/systems"),
          ("10.6265", "transport task 4 arrives with 1 items/systems"),
          ("10.3766", "Backorder removed, waiting time was 2"),
          ("10.6265", "Backorder removed, waiting time was 2"))))
    check("MINBS2 first one-item task cancelled and request retained", all(at(two, "8.37658", text) for text in (
          "transport task 1 cancelled with 1 items/systems",
          "transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> attached to  scheduled transport task 0")) and
          not at(two, "8.37658", "transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> started"))
    check("MINBS2 one two-item dispatch at second demand", at(two, "8.6265", "transport task 4 starts with 2 items/systems") and
          all(at(two, "8.6265", f"transport request <<TEACH-LRU-01,0,{n}>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> started") for n in (0, 1)) and
          sum("starts with 2 items/systems" in line for line in two.splitlines()) == 1)
    check("MINBS2 one two-item arrival and both backorders clear", at(two, "10.6265", "transport task 4 arrives with 2 items/systems") and
          at(two, "10.6265", "Backorder removed, waiting time was 2.24992") and
          at(two, "10.6265", "Backorder removed, waiting time was 2"))
    check("two distinct downward shipment counts", sum("starts with 1 items/systems" in line and
          ("transport task 1 " in line or "transport task 4 " in line) for line in one.splitlines()) == 2 and
          not any("starts with 1 items/systems" in line and "transport task 1 " in line for line in two.splitlines()))

    for arm in RUN_IDS:
        report = reports[arm]
        log = logs[arm]
        system, stock, summary = (report[name] for name in ("SystemResults", "StockTotalResults", "ResultSummary"))
        system_rows, stock_rows = rows(system), rows(stock)
        check(f"{arm} expected report tables", set(report) ==
              {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
        check(f"{arm} 72 System/Stock bins", len(system_rows) == len(stock_rows) == 72)
        demand_first, demand_second = 8.37658, 8.6265
        clear_first, clear_second = ((10.37658, 10.6265) if arm == "minbs1" else (10.6265, 10.6265))
        ready_first, ready_second = ((10.7099, 10.9598) if arm == "minbs1" else (10.9598, 10.9598))
        nbo_segments = [(demand_first, clear_first, 1), (demand_second, clear_second, 1)]
        ready_segments = [(0, 7, 2), (ready_first, 36, 1), (ready_second, 36, 1)]
        # Native operating occupancy continues through the aborted missions' returns.
        operating_segments = [(8, 8.37658, 1), (8, 8.6265, 1)]
        for index, (srow, trow) in enumerate(zip(system_rows, stock_rows)):
            start, end = index / 2, (index + 1) / 2
            check(f"{arm} system interval {index}", near(field(system, srow, "STINT"), start, 1e-6) and
                  near(field(system, srow, "ETINT"), end, 1e-6))
            check(f"{arm} stock interval {index}", near(field(stock, trow, "STINT"), start, 1e-6) and
                  near(field(stock, trow, "ETINT"), end, 1e-6))
            check(f"{arm} event-derived NBO {index}", near(field(stock, trow, "NBO") or 0,
                  occupancy(start, end, nbo_segments), 0.001))
            check(f"{arm} event-derived NSYRY {index}", near(field(system, srow, "NSYRY") or 0,
                  occupancy(start, end, ready_segments), 0.001))
            check(f"{arm} event-derived NSYMO {index}", near(field(system, srow, "NSYMO") or 0,
                  occupancy(start, end, operating_segments), 0.001))
            check(f"{arm} failure-bin NFAIL {index}", (field(system, srow, "NFAIL") or 0) ==
                  (2 if start == 8 else 0))
            check(f"{arm} demand-bin NDF {index}", (field(stock, trow, "NDF") or 0) ==
                  (1 if start in (8, 8.5) else 0))
            check(f"{arm} repair-bin NREPT {index}", (field(system, srow, "NREPT") or 0) ==
                  (2 if start == 10.5 else 0))
        check(f"{arm} WT from two local backorders", near(sum((field(stock, row, "WT") or 0) for row in stock_rows),
              4 if arm == "minbs1" else 4.24992))
        summary_row = rows(summary)[0]
        check(f"{arm} two failed missions, one repetition", field(summary, summary_row, "NREP") == 1 and
              field(summary, summary_row, "RTIUP") == 36 and field(summary, summary_row, "MSUF") == 0)
        check(f"{arm} terminal ready2, no aggregate backorder", near(field(system, system_rows[-1], "NSYRY"), 2) and
              (field(stock, stock_rows[-1], "NBO") or 0) == 0)
        check(f"{arm} no terminal in-transit transport", sum("starts with" in line and "items/systems" in line for line in log.splitlines()) ==
              sum("arrives with" in line and "items/systems" in line for line in log.splitlines()))

    report_a, report_b = reports["minbs1"], reports["minbs2"]
    check("summary equal across arms", report_a["ResultSummary"] == report_b["ResultSummary"])
    for table_name in ("SystemResults", "StockTotalResults"):
        left, right = report_a[table_name], report_b[table_name]
        allowed = ({"NSYRY", "NSYUA", "NSYA", "NSYRP", "NSYWI", "SYDT"} if table_name == "SystemResults"
                   else {"NBO", "WT", "WTT", "WTS"})
        check(f"{table_name} differences limited to time/availability fields", changed_columns(left, right) == allowed)

    failures = [item["name"] for item in checks if not item["passed"]]
    result = {
        "schema": "simlox-e10-var06-independent-readonly/v1", "passed": not failures,
        "verdict": "GO_bounded_same_item_MINBS_1_vs_2" if not failures else "NO_GO",
        "checks_passed": len(checks) - len(failures), "checks_total": len(checks),
        "failures": failures, "checks": checks,
        "hashes": {"contract": sha(CASE / "contract.json"), "exact_diff": sha(CASE / "exact-diff.json"),
                   "parent_input": sha(parent_source), "parent_closure": sha(parent_closure),
                   "support_input": sha(support_source), "support_closure": sha(support_closure),
                   "inputs": {arm: sha(path) for arm, path in input_paths.items()}, "runs": run_hashes},
        "scope": "Two seeded same-IID depot demands for spare physical IDs0/1 occur at h8.37658 and h8.6265 after distinct aircraft/installed-item failures. MINBS1 dispatches two one-item downward transports immediately; MINBS2 cancels the first one-item task while retaining ID0, then dispatches one two-item transport at the second demand. Both upward failed IDs2/3 are repaired and restocked; all event-derived half-hour backorder/readiness/operating bins reconcile.",
        "limits": ["One fixed seed, two demands for the same IID, one downward general link and thresholds one/two only.",
                   "No mixed-item/system batching, cross-link pooling, thresholds above two, partial batches at horizon, GUI-only or cross-engine claim.",
                   "No authored resource capacity rows; ResourceResults is absent, so resource constraints are outside scope."],
    }
    OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks_passed": result["checks_passed"],
                      "checks_total": result["checks_total"], "failures": failures}))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
