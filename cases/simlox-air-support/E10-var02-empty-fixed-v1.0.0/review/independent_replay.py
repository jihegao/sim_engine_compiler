"""Independent standard-library, read-only E10.var02 raw evidence replay."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
ROOT = CASE.parent
RUN_ID = "e10-var02-empty-v100-ssh-20261003-01"
RUN = CASE / "runs" / RUN_ID
OUT = Path(__file__).with_name("independent-verdict.json")
checks = []


def check(name, passed):
    checks.append({"name": name, "passed": bool(passed)})


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


def has(log, hour, fragment):
    return any(line.startswith(f"Time: {hour} ") and fragment in line for line in log.splitlines())


def close(a, b, tolerance=0.0001):
    return math.isclose(float(a), float(b), rel_tol=0, abs_tol=tolerance)


def check_roundtrip(source, exported):
    count = 0
    for name, authored in source.items():
        if not rows(authored):
            continue
        count += 1
        target = exported.get(name)
        equal = target is not None
        if equal:
            width = len(authored["columns"])
            equal = ([c["name"] for c in authored["columns"]] ==
                     [c["name"] for c in target["columns"][:width]])
            equal &= ([i["rows"] for i in authored["instances"]] ==
                      [[r[:width] for r in i["rows"]] for i in target["instances"]])
        check(f"native exact authored table {name}", equal)
    check("22 row-containing authored tables", count == 22)


def main():
    contract = read(CASE / "contract.json")
    diff = read(CASE / "exact-diff.json")
    parent_pkg = ROOT / "E10-var01-fixed-ondem-v1.0.1"
    parent_source = parent_pkg / "native-input-fixed.json"
    parent_run = parent_pkg / "runs" / contract["accepted_parent"]["run_id"]
    parent_closure = parent_run / "closure.json"
    parent_index = parent_pkg / "evidence-index.json"
    check("accepted parent source pin", sha(parent_source) == contract["accepted_parent"]["input_sha256"])
    check("accepted parent closure pin", sha(parent_closure) == contract["accepted_parent"]["native_closure_sha256"])
    check("accepted parent evidence index pin", sha(parent_index) == contract["accepted_parent"]["evidence_index_sha256"])
    check("child source pin", sha(CASE / "native-input.json") == contract["native_input_sha256"])
    check("exact diff pin", sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"])
    check("diff parent/child pins", diff["parent_sha256"] == sha(parent_source) and
          diff["source_sha256"] == sha(CASE / "native-input.json"))
    parent = tables(read(parent_source))
    child = tables(read(CASE / "native-input.json"))
    changed = {name for name in parent.keys() | child.keys() if parent.get(name) != child.get(name)}
    check("only description/profile source-table delta", changed == {"ProblemDescription", "TransportPolicyProfile"})
    for name in sorted(parent.keys() - changed):
        check(f"unchanged parent table {name}", child[name] == parent[name])
    original = parent["TransportPolicyProfile"]
    extra = child["TransportPolicyProfile"]
    check("profile column schema preserved", original["columns"] == extra["columns"])
    check("one earlier FIXED h8 row, parent h11 row unchanged", rows(extra) ==
          [diff["added_profile_row"], diff["unchanged_h11_profile_row"]] and
          rows(original) == [diff["unchanged_h11_profile_row"]])
    check("no authored resource capacity or task lease", not rows(child["Resource"]) and
          not rows(child["ResourceAllocation"]) and not rows(child["TaskResource"]))

    invocation = read(RUN / "invocation.json")
    closure = read(RUN / "closure.json")
    check("run identity and closure SHA", invocation["run_id"] == closure["run_id"] == RUN_ID and
          sha(RUN / "closure.json") == "24ebef40dbb685ca704023566ee9d23f8fea7121cb849e48a04a4a4f143281d3")
    check("invocation input pin", invocation["input_sha256"] == sha(CASE / "native-input.json") == sha(RUN / "input.json"))
    check("closure invocation pin", closure["invocation_sha256"] == sha(RUN / "invocation.json"))
    check("stable source hashes before/after", closure["source_hashes_before"] ==
          closure["source_hashes_after"] == invocation["source_hashes_before"])
    sources = {
        "input": CASE / "native-input.json", "parent": parent_source,
        "parent_closure": parent_closure, "parent_index": parent_index,
        "contract": CASE / "contract.json", "exact_diff": CASE / "exact-diff.json",
        "builder": CASE / "build.py", "diff_builder": CASE / "describe_diff.py",
        "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1",
    }
    for name, path in sources.items():
        check(f"source seal {name}", closure["source_hashes_before"][name] == sha(path))
    pins = closure["source_hashes_before"]
    check("installed exe/manual/dictionary fingerprints", pins["simlox_exe"] == contract["source"]["simlox_exe_sha256"] and
          pins["manual"] == contract["source"]["manual_pdf_sha256"] and
          pins["dictionary"] == contract["source"]["dictionary_sha256"])
    check("SSH session0, queue mutex, GUI PID", invocation["execution_mode"] == "ssh_cli_v1" and
          invocation["session_id"] == 0 and invocation["ssh_connection_present"] and
          invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue" and
          invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1)
    steps = read(RUN / "steps.json")
    check("five guarded successful steps", [s["name"] for s in steps] ==
          ["import", "export", "calc", "jsonreport", "check_import_export"] and
          all(s["exit_code"] == 0 and s["gui_preserved"] for s in steps))
    check("12 raw closure files", len(closure["raw"]) == 12)
    for name, metadata in sorted(closure["raw"].items()):
        path = RUN / name
        check(f"raw seal {name}", path.stat().st_size == metadata["bytes"] and
              sha(path) == metadata["sha256"])
    check_roundtrip(child, tables(read(RUN / "roundtrip-raw.json", native=True)))
    converter = (RUN / "run.log").read_text(encoding="utf-8-sig")
    check("converter errors0/warning108/notes0", bool(re.search(r"Errors:\s*0, Warnings:\s*1, Notes:\s*0", converter)) and
          re.findall(r"warning #(\d+)", converter) == ["108"])
    check("valid SXO/event/report", all((RUN / name).stat().st_size > 1000 for name in
          ("model.sxo", "model.log", "report-raw.json")))

    log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    parent_log = (parent_run / "model.log").read_text(encoding="utf-8-sig")
    check("h8 empty task explicitly cancelled", has(log, "0", "scheduled transport task 0 created from <DEPOT-01,0> to <BASE-01,0>, scheduled to start at 8") and
          has(log, "8", "scheduled transport task 0 cancelled with 0 items/systems"))
    check("no physical item move before h10 demand", not any(re.match(r"Time: ([\d.]+) ", line) and
          float(re.match(r"Time: ([\d.]+) ", line).group(1)) < 10 and
          any(p in line for p in ("Take replacement item", "transport task 0 starts with", "transport request <<", "Replacement item arrives"))
          for line in log.splitlines()))
    check("matched first failure and first mission abort", has(log, "9.8829", "<TEACH-AIR-01,0> critical random failure added") and
          has(log, "9.8829", "BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted"))
    check("sole h10 local and depot item demands", sum("Item demand arrives" in line for line in log.splitlines()) == 2 and
          has(log, "10", "<TEACH-LRU-01,0,BASE-01,0> Item demand arrives") and
          has(log, "10", "<TEACH-LRU-01,0,DEPOT-01,0> Item demand arrives"))
    check("depot spare ID0 reserved after demand", has(log, "10", "Take replacement item <TEACH-LRU-01,0,0> from stock") and
          has(log, "10", "transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> attached to  scheduled transport task 1"))
    check("retained h11 physical dispatch and h13 arrival", all(has(log, time, phrase) for time, phrase in (
          ("8", "scheduled transport task 1 created from <DEPOT-01,0> to <BASE-01,0>, scheduled to start at 11"),
          ("11", "scheduled transport task 1 starts with 1 items/systems, transport time: 2"),
          ("13", "scheduled transport task 1 arrives with 1 items/systems"),
          ("13", "Replacement item arrives <TEACH-LRU-01,0,0>"),
          ("13", "Backorder removed, waiting time was 3"))))
    check("upward ID1 transit and depot repair", all(has(log, time, phrase) for time, phrase in (
          ("10.1667", "transport task 2 starts with 1 items/systems, transport time: 2"),
          ("12.1667", "transport task 2 arrives with 1 items/systems"),
          ("12.1667", "Start repair of item <TEACH-LRU-01,0,1>"),
          ("13.1667", "Finished repair of item <TEACH-LRU-01,0,1>"),
          ("13.1667", "Put back replacement item <TEACH-LRU-01,0,1> to stock"))))
    check("system fit/readiness restored h13.3333", has(log, "13.3333", "fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> completed") and
          has(log, "13.3333", "System ready <TEACH-AIR-01,0>"))
    check("later missions succeed, no later demand", all(has(log, time, phrase) for time, phrase in (
          ("20", "BASIC-MISSION,TEACH-UNIT,0,0,1> mission starting"),
          ("22", "BASIC-MISSION,TEACH-UNIT,0,0,1> mission success"),
          ("32", "BASIC-MISSION,TEACH-UNIT,0,0,2> mission starting"),
          ("34", "BASIC-MISSION,TEACH-UNIT,0,0,2> mission success"))) and
          all(line.startswith("Time: 10 ") for line in log.splitlines() if "Item demand arrives" in line))
    check("two physical transports start and arrive; no item in transit at horizon", sum("starts with 1 items/systems" in line
          for line in log.splitlines()) == sum("arrives with 1 items/systems" in line for line in log.splitlines()) == 2)
    check("no resource task demand", not rows(child["Resource"]) and
          not any("requests resources" in line and "no resources needed" not in line for line in log.splitlines()))
    check("event difference from parent is task numbering plus explicit empty cancellation", sha(RUN / "model.log") != sha(parent_run / "model.log") and
          "scheduled transport task 0 cancelled with 0 items/systems" not in parent_log and
          "scheduled transport task 0 cancelled with 0 items/systems" in log)

    report = tables(read(RUN / "report-raw.json", native=True), "report")
    parent_report = tables(read(parent_run / "report-raw.json", native=True), "report")
    check("report business tables equal accepted parent", all(report[name] == parent_report[name] for name in
          ("ResultSummary", "SystemResults", "StockTotalResults")))
    check("no ResourceResults expected or emitted", "ResourceResults" not in report)
    system, stock, summary = (report[name] for name in ("SystemResults", "StockTotalResults", "ResultSummary"))
    sys_rows, stock_rows = rows(system), rows(stock)
    check("72 System and Stock bins", len(sys_rows) == len(stock_rows) == 72)
    for i, (s, t) in enumerate(zip(sys_rows, stock_rows)):
        start, end = i / 2, (i + 1) / 2
        check(f"SystemResults half-hour interval {i}", close(field(system, s, "STINT"), start, 1e-6) and
              close(field(system, s, "ETINT"), end, 1e-6))
        check(f"StockTotalResults half-hour interval {i}", close(field(stock, t, "STINT"), start, 1e-6) and
              close(field(stock, t, "ETINT"), end, 1e-6))
        check(f"stock backorder bin {i}", (field(stock, t, "NBO") or 0) == (1 if 10 <= start < 13 else 0))
        check(f"stock demand bin {i}", (field(stock, t, "NDF") or 0) == (1 if start == 10 else 0))
    check("stock waiting time three hours", sum((field(stock, r, "WT") or 0) for r in stock_rows) == 3)
    check("system one first fault/repair", sum((field(system, r, "NFAIL") or 0) for r in sys_rows) == 1 and
          sum((field(system, r, "NREPT") or 0) for r in sys_rows) == 1)
    check("ready fraction at h13 and terminal ready1", close(field(system, sys_rows[26], "NSYRY"), 1 / 3) and
          field(system, sys_rows[-1], "NSYRY") == 1 and (field(stock, stock_rows[-1], "NBO") or 0) == 0)
    sr = rows(summary)[0]
    check("one 36h repetition, 2/3 mission success", field(summary, sr, "NREP") == 1 and
          field(summary, sr, "RTIUP") == 36 and close(field(summary, sr, "MSUF"), 2 / 3))

    failures = [c["name"] for c in checks if not c["passed"]]
    result = {
        "schema": "simlox-e10-var02-independent-readonly/v1", "passed": not failures,
        "verdict": "GO_bounded_one_empty_FIXED_departure" if not failures else "NO_GO",
        "checks_passed": len(checks) - len(failures), "checks_total": len(checks), "failures": failures,
        "checks": checks,
        "hashes": {"input": sha(CASE / "native-input.json"), "contract": sha(CASE / "contract.json"),
                   "exact_diff": sha(CASE / "exact-diff.json"), "parent_input": sha(parent_source),
                   "parent_closure": sha(parent_closure), "closure": sha(RUN / "closure.json"),
                   "model_log": sha(RUN / "model.log"), "report": sha(RUN / "report-raw.json")},
        "scope": "With no queued item at h8, native task 0 explicitly cancels with zero items and no physical movement. The sole h10 demand queues physical ID0 for h11 dispatch, h13 arrival, three-hour local backorder, and h13.3333 readiness. Failed ID1 follows unchanged upward transit and depot repair.",
        "limits": ["One empty FIXED point, one subsequent demand-bearing point, one seed and one support link only.",
                   "No later demand occurs; repeated empty points, multiple demands, same-time priority and batching remain untested.",
                   "The identical aggregate business report tables do not by themselves prove the empty h8 cancellation; the event log supplies that evidence.",
                   "No GUI visual or cross-engine claim."],
    }
    OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks_passed": result["checks_passed"],
                      "checks_total": result["checks_total"], "failures": failures, "output": str(OUT)}))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
