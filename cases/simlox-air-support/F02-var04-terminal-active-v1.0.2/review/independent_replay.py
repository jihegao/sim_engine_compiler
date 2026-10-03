"""Independent standard-library replay of the sealed F02.var04 v1.0.2 run.

Reads native artifacts and accepted-parent evidence; never invokes SIMLOX or author code.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
ROOT = CASE.parent
PARENT = ROOT / "F02-var01-var02-integrated-fleet-v1.0.2"
PRUN = PARENT / "runs/f02-pair-v102-risk-ssh-20261004-01"
RUN = CASE / "runs/f02-var04-terminal-v102-ssh-20261004-01"
OUT = CASE / "review/independent-verdict.json"
checks = 0
failures: list[str] = []


def check(condition: bool, label: str) -> None:
    global checks
    checks += 1
    if not condition:
        failures.append(label)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path):
    raw = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", raw))


def tables(doc, kind):
    return {table["name"]: table for table in doc[kind]["tables"]}


def columns(table):
    return [c["name"] for c in table["columns"]]


def rows(table):
    return [r for instance in table["instances"] for r in instance["rows"]]


def almost(observed, expected, label, tol=0.00035):
    if observed is None and expected == 0:
        observed = 0
    check(isinstance(observed, (int, float)) and abs(observed - expected) < tol,
          f"{label}: {observed} vs {expected}")


def occupancy(left, right, spans):
    return sum(max(0.0, min(right, end) - max(left, start)) / (right - left)
               for start, end in spans)


def event(lines, time, phrase):
    check(any((m := re.match(r"Time: ([\d.e+\-]+) (.*)", line))
              and abs(float(m[1]) - time) < 0.00012 and phrase in m[2]
              for line in lines), f"event {time}: {phrase}")


contract = read_json(CASE / "contract.json")
diff = read_json(CASE / "exact-diff.json")
closure = read_json(RUN / "closure.json")
invocation = read_json(RUN / "invocation.json")
steps = read_json(RUN / "steps.json")
source = CASE / "terminal-input.json"
parent_source = PARENT / "risk-input.json"
pins = {
    "input": source, "parent": parent_source,
    "parent_closure": PRUN / "closure.json",
    "parent_evidence_index": PARENT / "evidence-index.json",
    "prior0_diagnostic": ROOT / "F02-var04-terminal-active-v1.0.0/diagnostic.json",
    "prior1_diagnostic": ROOT / "F02-var04-terminal-active-v1.0.1/diagnostic.json",
    "prior0_closure": ROOT / "F02-var04-terminal-active-v1.0.0/runs/f02-var04-terminal-v100-ssh-20261004-01/closure.json",
    "prior1_closure": ROOT / "F02-var04-terminal-active-v1.0.1/runs/f02-var04-terminal-v101-ssh-20261004-01/closure.json",
    "contract": CASE / "contract.json", "exact_diff": CASE / "exact-diff.json",
    "build.py": CASE / "build.py", "describe_diff.py": CASE / "describe_diff.py",
    "check_roundtrip.py": CASE / "check_roundtrip.py",
    "run_native_ssh.ps1": CASE / "run_native_ssh.ps1",
}
check(closure["source_hashes_before"] == closure["source_hashes_after"],
      "frozen source before/after")
check(invocation["source_hashes_before"] == closure["source_hashes_before"],
      "invocation agrees with closure")
for key, path in sorted(pins.items()):
    check(path.is_file(), f"source file present: {key}")
    if path.is_file():
        check(digest(path) == closure["source_hashes_before"][key],
              f"source SHA: {key}")
check(digest(source) == contract["terminal_input_sha256"], "contract input SHA")
check(digest(parent_source) == contract["accepted_parent"]["input_sha256"],
      "contract parent SHA")
check(digest(CASE / "exact-diff.json") == contract["exact_diff_sha256"],
      "contract diff SHA")
check(digest(RUN / "input.json") == digest(source), "native input equals frozen input")
check(digest(RUN / "invocation.json") == closure["invocation_sha256"],
      "invocation SHA")
check(closure["run_id"] == RUN.name and closure["error"] is None,
      "successful native closure")
check(len(closure["raw"]) == 12, "twelve sealed raw files")
for name, seal in sorted(closure["raw"].items()):
    path = RUN / name
    check(path.is_file(), f"raw present: {name}")
    if path.is_file():
        check(path.stat().st_size == seal["bytes"], f"raw size: {name}")
        check(digest(path) == seal["sha256"], f"raw SHA: {name}")
check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"],
      "session-zero SSH")
check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1,
      "separate GUI identity")
check(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue",
      "shared native queue mutex")
check([step["name"] for step in steps] ==
      ["import", "export", "calc", "jsonreport", "check_import_export"],
      "guarded native step order")
for step in steps:
    check(step["status"] == "completed" and step["exit_code"] == 0,
          f"step success: {step['name']}")
for step in steps[:4]:
    check(step["gui_preserved"] is True, f"GUI preserved: {step['name']}")
for record in contract["revised_from"]:
    version = record["package"][-6:]
    check(record["diagnostic_sha256"] == digest(ROOT / record["package"] / "diagnostic.json"),
          f"excluded {version} diagnostic pin")
    diagnostic = read_json(ROOT / record["package"] / "diagnostic.json")
    check(diagnostic["publication_state"] == "excluded_diagnostic" and
          "#204" in diagnostic["native_result"] and
          diagnostic["native_closure_sha256"] == record["native_closure_sha256"],
          f"excluded {version} Operations #204")

parent = tables(read_json(parent_source), "model")
child = tables(read_json(source), "model")
export = tables(read_json(RUN / "roundtrip-raw.json"), "model")
check(diff["parent_input_sha256"] == digest(parent_source), "diff parent SHA")
check(diff["terminal_input_sha256"] == digest(source), "diff child SHA")
changed = []
for name in sorted(set(parent) | set(child)):
    pa, ch = parent.get(name), child.get(name)
    check(pa is not None and ch is not None, f"source table retained: {name}")
    if pa is None or ch is None:
        continue
    check(columns(pa) == columns(ch), f"source schema retained: {name}")
    check(len(rows(pa)) == len(rows(ch)), f"source row count retained: {name}")
    for row_index, (before, after) in enumerate(zip(rows(pa), rows(ch))):
        for column, old, new in zip(columns(pa), before, after):
            if old != new:
                changed.append((name, row_index, column, old, new))
check(changed == [("StationStructure", 0, "TFRMS", 2.0, 15.0),
                  ("StationStructure", 0, "TTOMS", 2.0, 15.0)],
      "only two 2-to-15 transport cells changed")
check(diff["changed_cells"] == [
    {"table": "StationStructure", "instance": 0, "row": 0,
     "column": "TFRMS", "before": 2.0, "after": 15.0},
    {"table": "StationStructure", "instance": 0, "row": 0,
     "column": "TTOMS", "before": 2.0, "after": 15.0},
], "frozen diff describes actual cells")
authored = sorted(name for name in child if rows(child[name]))
check(len(authored) == 30, "thirty row-containing source tables")
for name in authored:
    check(name in export, f"export table present: {name}")
    if name not in export:
        continue
    source_columns, export_columns = columns(child[name]), columns(export[name])
    check(all(col in export_columns for col in source_columns),
          f"export authored columns: {name}")
    if all(col in export_columns for col in source_columns):
        projected = [[r[export_columns.index(col)] for col in source_columns]
                     for r in rows(export[name])]
        check(projected == rows(child[name]), f"native authored roundtrip: {name}")
runlog = (RUN / "run.log").read_text(encoding="utf-8-sig")
check("Errors: 0, Warnings: 1, Notes: 0" in runlog, "zero converter errors")
check(set(re.findall(r"\((?:warning|notice|error) #(\d+)\)", runlog)) == {"108"},
      "only reviewed #108 warning")
check((RUN / "model.sxo").stat().st_size > 4, "usable simulated SXO")

lines = (RUN / "model.log").read_text(encoding="utf-8-sig").splitlines()
events = [
    (21.5, "<RISK-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 2"),
    (23.5, "<RISK-MISSION,TEACH-UNIT,0,0,0> mission completed"),
    (25.5, "<BASIC-MISSION,TEACH-UNIT,0,0,1> mission starting, duration: 2"),
    (27.5, "<BASIC-MISSION,TEACH-UNIT,0,0,1> mission completed"),
    (45.5, "<RISK-MISSION,TEACH-UNIT,0,0,2> mission starting, duration: 2"),
    (46.4896, "<TEACH-AIR-01,0> critical random failure added"),
    (46.4896, "<RISK-MISSION,TEACH-UNIT,0,0,2> mission aborted"),
    (47.9896, "system SURP task 14 on <TEACH-AIR-01,0> started"),
    (47.9896, "<TEACH-LRU-01,0,BASE-01,0> Backorder added"),
    (47.9896, "Take replacement item <TEACH-LRU-01,0,2> from stock"),
    (47.9896, "transport task 0 starts with 1 items/systems, transport time: 15"),
    (48.1563, "remove subitem subtask 14 seqno 1 within system SURP task 14 on <TEACH-AIR-01,0> completed"),
    (48.1563, "fit subitem subtask 16 seqno 2 within system SURP task 14 on <TEACH-AIR-01,0> wait for subitem"),
    (48.1563, "Item requiring maintenance arrives <TEACH-LRU-01,0,4>"),
    (48.1563, "transport task 2 starts with 1 items/systems, transport time: 15"),
    (50.25, "<BASIC-MISSION,TEACH-UNIT,0,0,3> mission cancelled"),
    (53.5, "system PM task 17 on <TEACH-AIR-01,0> started"),
    (54.5, "system PM task 18 on <TEACH-AIR-01,1> PMID: CAL24"),
    (55.5, "system PM task 18 on <TEACH-AIR-01,1> completed"),
]
for time, phrase in events:
    event(lines, time, phrase)
check(any("subitem failed: <TEACH-LRU-01,0,4>" in line for line in lines),
      "failed physical LRU4 identity")
check(any("transport request <<TEACH-LRU-01,0,2>," in line and
          "<TEACH-LRU-01,0,BASE-01,0>> started" in line for line in lines),
      "inbound physical LRU2 starts")
check(any("transport request <<TEACH-LRU-01,0,4>," in line and
          "<TEACH-LRU-01,0,DEPOT-01,0>> started" in line for line in lines),
      "outbound physical LRU4 starts")
for forbidden in ("transport task 0 arrives", "transport task 2 arrives",
                  "Backorder removed", "item SURP task", "item DIRP task"):
    check(not any(forbidden in line for line in lines),
          f"no pre-horizon arrival, clearance or item repair: {forbidden}")
check(not any(re.match(r"Time: [\d.e+\-]+  system SURP task 14 on "
                       r"<TEACH-AIR-01,0> completed$", line) for line in lines),
      "aircraft SURP task has not completed")
check(sum("system SURP task 14 on <TEACH-AIR-01,0>" in line and
          "starts performing" in line for line in lines) == 1,
      "one completed removal work phase")
check(not any("fit subitem subtask 16" in line and "starts performing" in line
              for line in lines), "fit is waiting, not working")
check(not any("<P-MAINT at <BASE-01,0>> allocated" in line and
              line.startswith("Time: 60") for line in lines),
      "no terminal maintainer allocation")
check(any("systems ready: 1 :<TEACH-AIR-01,1>" in line for line in lines[-45:]),
      "one ready aircraft at terminal")

report = tables(read_json(RUN / "report-raw.json"), "report")
preport = tables(read_json(PRUN / "report-raw.json"), "report")
check(set(report) == set(preport), "native report table set")
check(rows(report["ResultSummary"]) == rows(preport["ResultSummary"]),
      "fixed mission summary despite terminal repair")
summary = dict(zip(columns(report["ResultSummary"]), rows(report["ResultSummary"])[0]))
for col, val in {"NREP": 1, "RTIUP": 60, "MSTF": 0.75, "MSUF": 0.5}.items():
    almost(summary[col], val, f"summary {col}")
for name in ("SystemResults", "StockTotalResults", "ResourceResults"):
    check(len(rows(report[name])) == 120, f"120 {name} bins")
    check(columns(report[name]) == columns(preport[name]),
          f"parent {name} schema")
system, stock, resource = (report[name] for name in
                           ("SystemResults", "StockTotalResults", "ResourceResults"))
psystem, pstock, presource = (preport[name] for name in
                              ("SystemResults", "StockTotalResults", "ResourceResults"))
sc, tc, rc = map(columns, (system, stock, resource))
sr, st, rr = map(rows, (system, stock, resource))
ps, pt, pr = map(rows, (psystem, pstock, presource))

# Decode worker leases directly from native book/free events. A PM task's
# lifecycle start is not evidence that its subtask obtained a worker.
spans = []
opened = {"P-MAINT": None, "P-CREW": None}
for line in lines:
    m = re.match(r"Time: ([\d.e+\-]+)  <(P-MAINT|P-CREW) at <BASE-01,0>> "
                 r"(allocated to maintenance task|deallocated from  maintenance task)", line)
    if not m:
        continue
    time, person, action = float(m[1]), m[2], m[3]
    if action.startswith("allocated"):
        check(opened[person] is None, f"no double booking {person} at {time}")
        opened[person] = time
    else:
        check(opened[person] is not None, f"lease exists {person} at {time}")
        if opened[person] is not None:
            spans.append((opened[person], time, person))
        opened[person] = None
check(all(start is None for start in opened.values()), "all worker leases released")
check(any(abs(start - 47.9896) < .0001 and abs(end - 48.1563) < .0001
          and person == "P-MAINT" for start, end, person in spans),
      "only removal worker phase before item wait")
check(any(abs(start - 54.5) < .0001 and abs(end - 55.5) < .0001
          and person == "P-MAINT" for start, end, person in spans),
      "separate second-aircraft PM worker phase")

system_affected = {"NSYRY", "NSYUA", "NSYA", "NSYRP", "NSYPM", "NSYWI",
                   "NREPT", "NPMT", "SYDT", "NSYDT"}
stock_affected = {"NBO", "PNB", "WT", "WTT", "WTS", "NWT"}
for i in range(120):
    left, right = i / 2, (i + 1) / 2
    sm, tm, rm = (dict(zip(cols, item)) for cols, item in
                  ((sc, sr[i]), (tc, st[i]), (rc, rr[i])))
    psm, ptm, prm = (dict(zip(cols, item)) for cols, item in
                     ((sc, ps[i]), (tc, pt[i]), (rc, pr[i])))
    for table, data in (("system", sm), ("stock", tm), ("resource", rm)):
        almost(data["STINT"], left, f"{table} bin {i} start")
        almost(data["ETINT"], right, f"{table} bin {i} end")
    for col in sc:
        if col in system_affected or col in ("UNID", "SID", "STINT", "ETINT"):
            continue
        if isinstance(sm[col], (int, float)) or isinstance(psm[col], (int, float)):
            almost(sm[col], psm[col] or 0, f"system unchanged bin {i} {col}")
        else:
            check(sm[col] == psm[col], f"system unchanged bin {i} {col}")
    for col in tc:
        if col in stock_affected or col in ("STINT", "ETINT"):
            continue
        if isinstance(tm[col], (int, float)) or isinstance(ptm[col], (int, float)):
            almost(tm[col], ptm[col] or 0, f"stock unchanged bin {i} {col}")
        else:
            check(tm[col] == ptm[col], f"stock unchanged bin {i} {col}")
    for col in rc:
        if col in ("RID", "STID", "STINT", "ETINT", "NRUM"):
            continue
        if isinstance(rm[col], (int, float)) or isinstance(prm[col], (int, float)):
            almost(rm[col], prm[col] or 0, f"resource unchanged bin {i} {col}")
        else:
            check(rm[col] == prm[col], f"resource unchanged bin {i} {col}")
    busy = sum(occupancy(left, right, [(start, end)]) for start, end, _ in spans)
    almost(rm["NRUM"], busy, f"resource booked-time bin {i}")
    bo = occupancy(left, right, [(47.9896, 60)])
    almost(tm["NBO"], bo, f"base stock backorder bin {i}")
    almost(tm["PNB"], 1 - bo, f"base stock no-backorder bin {i}")
    almost(sm["NSYWI"], occupancy(left, right, [(48.1563, 60)]),
           f"system waiting item bin {i}")
    almost(sm["NSYRP"], occupancy(left, right, [(47.9896, 48.1563)]),
           f"system removal work bin {i}")
    pm = occupancy(left, right, [(28.5, 29.5), (29.5, 30.5), (54.5, 55.5)])
    almost(sm["NSYPM"], pm, f"system performed PM bin {i}")
    if i >= 100:
        ready = occupancy(left, right, [(51.25, 54.5), (55.5, 60)])
        unavailable = occupancy(left, right, [(48.1563, 60), (54.5, 55.5)])
        almost(sm["NSYRY"], ready, f"ready-aircraft bin {i}")
        almost(sm["NSYUA"], unavailable, f"unavailable-aircraft bin {i}")
        almost(sm["NSYA"], 2 - unavailable, f"available-aircraft bin {i}")
    else:
        for col in ("NSYRY", "NSYUA", "NSYA"):
            almost(sm[col], psm[col] or 0, f"parent prefix {col} bin {i}")
    for col in ("WT", "WTT", "WTS"):
        check(tm[col] is None, f"unfinished stock wait has no {col} bin {i}")
    almost(tm["NWT"], 0, f"no completed stock wait bin {i}")
    for col in ("NREPT", "NPMT", "NSYDT", "SYDT"):
        if (col == "NREPT" and i == 100) or (col == "NPMT" and i == 109) or \
           (col in ("NSYDT", "SYDT") and i in (95, 107)):
            almost(sm[col], 0, f"unfinished task marker {col} bin {i}")
        else:
            check(sm[col] == psm[col], f"unchanged task marker {col} bin {i}")

almost(sum((r[rc.index("NRUM")] or 0) / 2 for r in rr), 6.6666667,
       "integrated booked worker-hours")
almost(sum((r[tc.index("NBO")] or 0) / 2 for r in st), 60 - 47.9896,
       "integrated open base backorder-hours")
almost(sum((r[sc.index("NSYWI")] or 0) / 2 for r in sr), 60 - 48.1563,
       "integrated system item-wait hours")
almost(sr[-1][sc.index("NSYRY")], 1, "terminal one ready aircraft")
almost(sr[-1][sc.index("NSYWI")], 1, "terminal one aircraft waiting item")
almost(st[-1][tc.index("NBO")], 1, "terminal base backorder open")
almost(rr[-1][rc.index("NRUM")], 0, "terminal no worker booked")
total_resource = dict(zip(columns(report["ResourceResultsTotal"]),
                          rows(report["ResourceResultsTotal"])[0]))
almost(total_resource["NR"], 2, "resource total two workers")
almost(total_resource["NRUM"], 6.6666667 / 60, "resource total utilization")

verdict = {
    "case": "F02.var04 terminal active v1.0.2",
    "passed": not failures,
    "verdict": "GO: bounded in-transit and item-wait terminal observation" if not failures else "NO-GO",
    "checks_passed": checks - len(failures), "checks_total": checks,
    "failures": failures,
    "child_closure_sha256": digest(RUN / "closure.json"),
    "child_report_sha256": digest(RUN / "report-raw.json"),
    "parent_closure_sha256": digest(PRUN / "closure.json"),
    "limits": [
        "Single seed, two aircraft, one route, 15-hour travel each way, and a 60-hour horizon.",
        "Aircraft SURP remains open after physical removal work ends; the fit subtask waits for an item, while both distinct LRUs are in transit.",
        "The model log and aggregate report do not establish an item reservation, post-horizon arrival, or depot item repair.",
        "Predecessor v1.0.0/v1.0.1 #204 runs are excluded conversion diagnostics, not terminal observations.",
        "Report bins are half-hour averages; terminal event state is read from the event log as well as the last bin.",
    ],
}
OUT.write_bytes((json.dumps(verdict, indent=2, sort_keys=True) + "\n").encode("utf-8"))
print(json.dumps({"passed": verdict["passed"], "checks": checks,
                  "failures": failures[:25], "script_sha256": digest(Path(__file__)),
                  "verdict_sha256": digest(OUT)}, sort_keys=True))
raise SystemExit(0 if verdict["passed"] else 1)
