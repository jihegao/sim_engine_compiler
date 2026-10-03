"""Independent, read-only F01.var04 raw-evidence replay (standard library only)."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
BASE = CASE.parent
RUN = CASE / "runs" / "f01-var04-levels-v102-ssh-20261004-01"
OUT = HERE / "independent-verdict.json"
checks = 0
failures = []


def check(ok, name):
    global checks
    checks += 1
    if not ok:
        failures.append(name)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_json(path):
    s = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", s))


def table_map(document, root="model"):
    return {t["name"]: t for t in document[root]["tables"]}


def rows(table):
    return [r for inst in table["instances"] for r in inst["rows"]]


def find_event(lines, t, needle):
    pattern = re.compile(r"^Time: ([0-9.e+\-]+) (.*)$")
    return any((m := pattern.match(line)) and abs(float(m[1]) - t) <= 0.00011
               and needle in m[2] for line in lines)


def event(t, needle):
    check(find_event(loglines, t, needle), f"event {t}: {needle}")


def overlap(a, b, start, end):
    return max(0.0, min(b, end) - max(a, start)) / (b - a)


def occupied(a, b, intervals):
    return sum(overlap(a, b, start, end) for start, end in intervals)


def close(actual, expected, label, tol=0.00025):
    if actual is None and expected == 0:
        actual = 0
    check(isinstance(actual, (float, int)) and abs(actual - expected) <= tol,
          f"{label}: expected {expected}, got {actual}")


contract = json.loads((CASE / "contract.json").read_text(encoding="utf-8"))
diff = json.loads((CASE / "exact-diff.json").read_text(encoding="utf-8"))
closure = native_json(RUN / "closure.json")
invocation = native_json(RUN / "invocation.json")
steps = native_json(RUN / "steps.json")
parent_case = BASE / "F01-var01-two-three-level-v1.0.1"
parent_input = parent_case / "three-level-input.json"
level_case = BASE / "I01-var03-level-filter-v1.0.0"
paths = {
    "input": CASE / "native-input.json",
    "parent": parent_input,
    "parent_closure": parent_case / "runs" / "f01-var01-three-v101-ssh-20261004-01" / "closure.json",
    "parent_evidence_index": parent_case / "evidence-index.json",
    "level_allocation_reference": level_case / "basic-base-input.json",
    "level_allocation_reference_closure": level_case / "runs" / "i01-var03-level-basic-base-v100-ssh-20261002-01" / "closure.json",
    "level_allocation_reference_evidence_index": level_case / "evidence-index.json",
    "excluded_diagnostic_closure": BASE / "F01-var04-two-repair-levels-v1.0.0" / "runs" / "f01-var04-levels-v100-ssh-20261004-01" / "closure.json",
    "second_excluded_diagnostic_closure": BASE / "F01-var04-two-repair-levels-v1.0.1" / "runs" / "f01-var04-levels-v101-ssh-20261004-01" / "closure.json",
    "exact_diff": CASE / "exact-diff.json",
    "contract": CASE / "contract.json",
    "builder": CASE / "build.py",
    "diff_builder": CASE / "describe_diff.py",
    "checker": CASE / "check_roundtrip.py",
    "runner_script": CASE / "run_native_ssh.ps1",
}
check(closure["source_hashes_before"] == closure["source_hashes_after"], "source hashes stable")
for key, path in sorted(paths.items()):
    check(path.is_file(), f"source exists {key}")
    if path.is_file():
        check(sha(path) == closure["source_hashes_before"][key], f"source SHA {key}")
check(sha(RUN / "input.json") == sha(CASE / "native-input.json"), "run input exact source")
check(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation closure SHA")
check(len(closure["raw"]) == 12, "12 raw seals")
for name, seal in sorted(closure["raw"].items()):
    path = RUN / name
    check(path.is_file(), f"raw exists {name}")
    if path.is_file():
        check(path.stat().st_size == seal["bytes"], f"raw bytes {name}")
        check(sha(path) == seal["sha256"], f"raw SHA {name}")
check(closure["error"] is None and closure["scope"] == "four_step_native_candidate", "closed run")
check(invocation["session_id"] == 0 and invocation["ssh_connection_present"], "session-zero SSH")
check("sshd.exe" in invocation["ssh_ancestor_names"], "SSH ancestor")
check(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "native mutex")
check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1,
      "separate GUI identity")
check([s["name"] for s in steps] ==
      ["import", "export", "calc", "jsonreport", "check_import_export"], "five steps")
for step in steps:
    check(step["exit_code"] == 0 and step["status"] == "completed" and step["gui_preserved"],
          f"step {step['name']}")
check(invocation["source_hashes_before"] == closure["source_hashes_before"], "invocation source pins")
check(invocation["input_sha256"] == sha(CASE / "native-input.json"), "invocation input pin")
first_diag = paths["excluded_diagnostic_closure"].parent
second_diag = paths["second_excluded_diagnostic_closure"].parent
check(native_json(paths["excluded_diagnostic_closure"])["error"] is not None,
      "v1.0.0 stopped at unexpected-note runner gate")
check("Errors: 0, Warnings: 1, Notes: 2" in (first_diag / "run.log").read_text(encoding="utf-8-sig"),
      "v1.0.0 diagnostic converter set")
check(not (first_diag / "report-raw.json").exists(), "v1.0.0 no report")
check(native_json(paths["second_excluded_diagnostic_closure"])["error"] is None,
      "v1.0.1 raw diagnostic closed")
prior_log = (second_diag / "model.log").read_text(encoding="utf-8-sig")
check("Time: 34.1578  transport task 6 starts" in prior_log and
      "Time: 36.1578  transport task 6 arrives" not in prior_log,
      "v1.0.1 horizon cuts off final SRU outbound journey")

parent = table_map(native_json(parent_input))
source = table_map(native_json(CASE / "native-input.json"))
export = table_map(native_json(RUN / "roundtrip-raw.json"))
check(diff["parent_sha256"] == sha(parent_input), "diff parent pin")
check(diff["input_sha256"] == sha(CASE / "native-input.json"), "diff child pin")
changed = sorted(name for name in source if name not in parent or rows(source[name]) != rows(parent[name]))
changed += sorted(name for name in parent if name not in source)
check(changed == sorted(t["table"] for t in diff["changed_tables"]), "exact changed table set")
for entry in diff["changed_tables"]:
    name = entry["table"]
    check(entry["before_rows"] == (rows(parent[name]) if name in parent else []), f"diff before {name}")
    check(entry["after_rows"] == rows(source[name]), f"diff after {name}")
check(diff["unchanged_existing_tables"] == 23, "23 unchanged tables")
for name in sorted(set(parent) & set(source) - set(changed)):
    check(rows(parent[name]) == rows(source[name]), f"fixed table {name}")
populated = [name for name in source if rows(source[name])]
check(len(populated) == 25, "25 authored row-containing tables")
for name in populated:
    check(name in export, f"roundtrip table {name}")
    if name in export:
        acol = [c["name"] for c in source[name]["columns"]]
        ecol = [c["name"] for c in export[name]["columns"]]
        check(all(c in ecol for c in acol), f"roundtrip columns {name}")
        if all(c in ecol for c in acol):
            selected = [[r[ecol.index(c)] for c in acol] for r in rows(export[name])]
            check(selected == rows(source[name]), f"roundtrip rows {name}")

runlog = (RUN / "run.log").read_text(encoding="utf-8-sig")
check("Errors: 0, Warnings: 1, Notes: 2" in runlog, "conversion counts")
check(len(re.findall(r"\(warning #108\)", runlog)) == 1, "warning #108 once")
check(len(re.findall(r"\(notice #2034\)", runlog)) == 2, "notice #2034 twice")
check(set(re.findall(r"\((?:warning|notice|error) #(\d+)\)", runlog)) == {"108", "2034"},
      "exact diagnostic code set")
check((RUN / "model.sxo").stat().st_size > 4, "valid SXO")
loglines = (RUN / "model.log").read_text(encoding="utf-8-sig").splitlines()
check(len(loglines) > 350, "substantive native event log")
check(not any("books resources" in line or "Resource booked" in line for line in loglines),
      "no resource booking")
check(sum("requests resources: no resources needed" in line for line in loglines) >= 15,
      "all repair subtasks resource-free")
for kind, stock, ident in [("SRU", "DEPOT-01", None), ("SRU", "BASE-01", 0),
                           ("LRU", "BASE-01", 1)]:
    phrase = f"Stock at: <TEACH-{kind}-01,0,{stock},0> Level: {0 if ident is None else 1}"
    check(any(phrase in line for line in loglines), f"opening {kind} {stock}")

missions = [(7, 8, 8.47072, 8.94145, 0), (19, 20, 21.9336, 22, 1),
            (31, 32, 33.1162, 33.6162, 2)]
for ordered, start, failed, returned, mid in missions:
    ident = f"<BASIC-MISSION,TEACH-UNIT,0,0,{mid}>"
    event(ordered, ident + " mission created")
    event(ordered, ident + " mission allocates system: <TEACH-AIR-01,0>")
    event(start, ident + " mission starting, duration: 2")
    event(failed, ident + " mission aborted")
    event(returned, ident + " aborted mission completed")
check(not any(" mission successful" in s or " mission succeeded" in s for s in loglines),
      "no successful mission event")

cycles = [
    dict(lru=2, spare_lru=1, sru=3, spare_sru=0, sys=0, it=1, direct=2,
         sysstart=8.94145, sysend=9.44145, lruremove=9.10812, lruend=9.85812,
         outbound=9.48312, depot=11.4831, repairend=12.4831, base=14.4831,
         outtask=0, intask=2),
    dict(lru=4, spare_lru=2, sru=5, spare_sru=3, sys=3, it=4, direct=5,
         sysstart=22, sysend=22.5, lruremove=22.1667, lruend=22.9167,
         outbound=22.5417, depot=24.5417, repairend=25.5417, base=27.5417,
         outtask=4, intask=5),
    dict(lru=6, spare_lru=4, sru=7, spare_sru=5, sys=6, it=7, direct=8,
         sysstart=33.6162, sysend=34.1162, lruremove=33.7828, lruend=34.5328,
         outbound=34.1578, depot=36.1578, repairend=37.1578, base=39.1578,
         outtask=6, intask=7),
]
for c in cycles:
    lru = f"<TEACH-LRU-01,0,{c['lru']}>"
    sru = f"<TEACH-SRU-01,0,{c['sru']}>"
    event(c["sysstart"], f"system SURP task {c['sys']} on <TEACH-AIR-01,0> started")
    event(c["sysstart"], f"Take replacement item <TEACH-LRU-01,0,{c['spare_lru']}> from stock")
    event(c["sysend"], f"system SURP task {c['sys']} on <TEACH-AIR-01,0> completed")
    event(c["sysend"], "System ready <TEACH-AIR-01,0>")
    event(c["lruremove"], f"Item requiring maintenance arrives {lru}")
    event(c["lruremove"], f"item SURP task {c['it']} on {lru} started")
    event(c["lruremove"], f"Take replacement item <TEACH-SRU-01,0,{c['spare_sru']}> from stock")
    event(c["lruend"], f"item SURP task {c['it']} on {lru} completed")
    event(c["lruend"], f"Put back replacement item {lru} to stock")
    event(c["outbound"], f"Item requiring maintenance arrives {sru}")
    event(c["outbound"], "<TEACH-SRU-01,0,DEPOT-01,0> Backorder added")
    event(c["outbound"], f"transport task {c['outtask']} starts with 1 items/systems, transport time: 2")
    event(c["depot"], f"transport task {c['outtask']} arrives with 1 items/systems")
    event(c["depot"], f"item DIRP task {c['direct']} on {sru} started")
    event(c["repairend"], f"item DIRP task {c['direct']} on {sru} completed")
    event(c["repairend"], "<TEACH-SRU-01,0,DEPOT-01,0> Backorder removed, waiting time was 3")
    event(c["repairend"], f"transport task {c['intask']} starts with 1 items/systems, transport time: 2")
    event(c["base"], f"transport task {c['intask']} arrives with 1 items/systems")
    event(c["base"], f"Put back replacement item {sru} to stock")
    close(c["sysend"]-c["sysstart"], .5, f"system SURP duration {c['sys']}")
    close(c["lruend"]-c["lruremove"], .75, f"LRU SURP duration {c['it']}")
    close(c["depot"]-c["outbound"], 2, f"outbound duration {c['outtask']}")
    close(c["repairend"]-c["depot"], 1, f"depot repair duration {c['direct']}")
    close(c["base"]-c["repairend"], 2, f"return duration {c['intask']}")
check(sum("Backorder added" in s and "DEPOT-01" in s for s in loglines) == 3,
      "three depot internal backorders")
check(sum("Backorder removed, waiting time was 3" in s for s in loglines) == 3,
      "three cleared depot backorders")
check(not any("Start repair of item <TEACH-SRU" in s and "BASE-01" in s for s in loglines),
      "SRU not repaired at base")
check(any("Stock at: <TEACH-SRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-SRU-01,0,7>" in s
          for s in loglines), "final SRU stock physical ID7")
check(any("Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,6>" in s
          for s in loglines), "final LRU stock physical ID6")

report = table_map(native_json(RUN / "report-raw.json"), "report")
check(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"},
      "default report table set")
check(rows(report["ProblemDescription"]) == rows(source["ProblemDescription"]), "report description")
summary = dict(zip([x["name"] for x in report["ResultSummary"]["columns"]],
                   rows(report["ResultSummary"])[0]))
for key, value in {"NREP": 1, "RTILW": 0, "RTIUP": 42, "MSTF": 1, "MSUF": 0}.items():
    close(summary[key], value, f"summary {key}")
close(summary["MTMF"], 0.7596011161804199, "summary mean mission time", .00001)

sr = report["SystemResults"]
st = report["StockTotalResults"]
srcols = [c["name"] for c in sr["columns"]]
stcols = [c["name"] for c in st["columns"]]
srrows, strows = rows(sr), rows(st)
check(len(srrows) == len(strows) == 84, "84 half-hour rows per report table")
mission_active = [(7,8.94145),(19,22),(31,33.6162)]
operating = [(8,8.94145),(20,22),(32,33.6162)]
reserved = [(7,8),(19,20),(31,32)]
repair = [(8.94145,9.44145),(22,22.5),(33.6162,34.1162)]
failure_bins = {16,43,66}
repair_start_bins = {17,44,67}
repair_done_bins = {18,45,68}
for i, (srow, trow) in enumerate(zip(srrows, strows)):
    a, b = i*.5, (i+1)*.5
    sm = dict(zip(srcols, srow))
    tm = dict(zip(stcols, trow))
    close(sm["STINT"], a, f"system bin {i} start")
    close(sm["ETINT"], b, f"system bin {i} end")
    close(tm["STINT"], a, f"stock bin {i} start")
    close(tm["ETINT"], b, f"stock bin {i} end")
    active = occupied(a,b,mission_active)
    flight = occupied(a,b,operating)
    res = occupied(a,b,reserved)
    down = occupied(a,b,repair)
    expected = {"NSYA":1-down,"NSYRY":1-active-down,"NSYMA":active,
                "NSYMO":flight,"FTMO":flight,"STACC":flight,"NSYMR":res,
                "NSYUA":down,"NSYRP":down,"NFAIL":int(i in failure_bins),
                "NREPT":int(i in repair_done_bins),"NSYDT":int(i in repair_start_bins),
                "SYDT":.5 if i in repair_start_bins else 0}
    for key in srcols:
        if key in ("UNID","SID","STINT","ETINT"):
            continue
        close(sm[key], expected.get(key,0), f"system bin {i} {key}")
    stock_expected = {"PNB":1,"NDF":int(i in repair_start_bins),
                      "NWT":int(i in repair_start_bins)}
    for key in stcols:
        if key in ("STINT","ETINT"):
            continue
        close(tm[key], stock_expected.get(key,0), f"stock bin {i} {key}")
check(srrows[-1][srcols.index("NSYRY")] == 1, "terminal ready one")
check(strows[-1][stcols.index("NBO")] == 0, "terminal aggregate backorder zero")
close(sum(r[srcols.index("STACC")]*.5 for r in srrows),
      sum(b-a for a,b in operating), "flight-hour integral")
close(sum((r[srcols.index("SYDT")] or 0) for r in srrows), 1.5, "system downtime integral")

result = {
    "case": "F01.var04 v1.0.2",
    "run_id": RUN.name,
    "passed": len(failures) == 0,
    "verdict": "GO: bounded two-level repair observation" if not failures else "NO-GO",
    "checks_passed": checks-len(failures),
    "checks_total": checks,
    "failures": failures,
    "accepted_closure_sha256": sha(RUN / "closure.json"),
    "accepted_report_sha256": sha(RUN / "report-raw.json"),
    "limits": [
        "One fixed seed, one physical aircraft, three observed LRU/SRU failure cycles and one level-2 depot route.",
        "v1.0.0 and v1.0.1 are excluded diagnostics; v1.0.1 ends before the third SRU returns.",
        "Resource rows are absent; native repair subtasks request no resources. No resource allocation claim.",
        "StockTotalResults.NBO is zero although native DEPOT-01 event log records three internal backorders.",
        "No population reliability, other item/station, GUI-only, or cross-engine conclusion.",
    ],
}
OUT.write_bytes((json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False)+"\n").encode("utf-8"))
print(json.dumps({"passed":result["passed"],"checks":checks,"failures":failures[:30],
                  "report_sha256":sha(OUT),"script_sha256":sha(Path(__file__))}, sort_keys=True))
raise SystemExit(0 if result["passed"] else 1)
