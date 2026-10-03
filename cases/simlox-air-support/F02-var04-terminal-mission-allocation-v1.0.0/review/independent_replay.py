"""Independent read-only replay for F02.var04 report-cutoff mission allocation."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
ROOT = CASE.parent
PARENT = ROOT / "F02-var04-terminal-repair-v1.0.0"
PRUN = PARENT / "runs/f02-var04-active-repair-v100-ssh-20261004-01"
EXCLUDED = ROOT / "F02-var04-terminal-preassignment-v1.0.0"
DRUN = EXCLUDED / "runs/f02-var04-preassign-v100-ssh-20261004-01"
RUN = CASE / "runs/f02-var04-allocation-v100-ssh-20261004-01"
OUT = CASE / "review/independent-verdict.json"
count = 0
failures: list[str] = []


def ck(ok, label):
    global count
    count += 1
    if not ok:
        failures.append(label)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(re.sub(r",\s*([}\]])", r"\1",
                             path.read_text(encoding="utf-8-sig")))


def tables(doc, key):
    return {t["name"]: t for t in doc[key]["tables"]}


def cols(t):
    return [c["name"] for c in t["columns"]]


def rows(t):
    return [r for ins in t["instances"] for r in ins["rows"]]


def approx(actual, expected, label, tolerance=.00035):
    if actual is None and expected == 0:
        actual = 0
    ck(isinstance(actual, (int, float)) and abs(actual - expected) < tolerance,
       f"{label}: {actual} vs {expected}")


def occupancy(a, b, spans):
    return sum(max(0.0, min(b, stop) - max(a, start)) / (b - a)
               for start, stop in spans)


def event(lines, hour, fragment):
    ck(any((m := re.match(r"Time: ([\d.e+\-]+) (.*)", line)) and
           abs(float(m[1]) - hour) < .00012 and fragment in m[2]
           for line in lines), f"native event {hour}: {fragment}")


contract = load(CASE / "contract.json")
diff = load(CASE / "exact-diff.json")
closure = load(RUN / "closure.json")
inv = load(RUN / "invocation.json")
steps = load(RUN / "steps.json")
source = CASE / "allocation-input.json"
parent_source = PARENT / "repair-input.json"
diag_source = EXCLUDED / "preassignment-input.json"
files = {
    "input": source, "parent": parent_source,
    "parent_closure": PRUN / "closure.json",
    "parent_evidence_index": PARENT / "evidence-index.json",
    "diagnostic_input": diag_source,
    "diagnostic_contract": EXCLUDED / "contract.json",
    "diagnostic_closure": DRUN / "closure.json",
    "contract": CASE / "contract.json", "exact_diff": CASE / "exact-diff.json",
    "build.py": CASE / "build.py", "describe_diff.py": CASE / "describe_diff.py",
    "check_roundtrip.py": CASE / "check_roundtrip.py",
    "run_native_ssh.ps1": CASE / "run_native_ssh.ps1",
}
ck(closure["source_hashes_before"] == closure["source_hashes_after"],
   "frozen source stable during run")
ck(inv["source_hashes_before"] == closure["source_hashes_before"],
   "invocation/closure source pins")
for name, path in sorted(files.items()):
    ck(path.is_file(), f"source present {name}")
    if path.is_file():
        ck(sha(path) == closure["source_hashes_before"][name],
           f"source hash {name}")
ck(sha(source) == contract["allocation_input_sha256"], "contract child input")
ck(sha(parent_source) == contract["accepted_parent"]["input_sha256"],
   "contract accepted parent input")
ck(sha(diag_source) == contract["excluded_diagnostic"]["input_sha256"],
   "excluded diagnostic input pin")
ck(sha(source) == sha(diag_source), "same business input as excluded probe")
ck(sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"],
   "contract exact diff")
ck(sha(RUN / "input.json") == sha(source), "run input byte copy")
ck(sha(RUN / "invocation.json") == closure["invocation_sha256"],
   "invocation seal")
ck(closure["run_id"] == RUN.name and closure["error"] is None,
   "fresh native closure success")
ck(len(closure["raw"]) == 12, "twelve raw seals")
for name, seal in sorted(closure["raw"].items()):
    path = RUN / name
    ck(path.is_file(), f"raw exists {name}")
    if path.is_file():
        ck(path.stat().st_size == seal["bytes"], f"raw size {name}")
        ck(sha(path) == seal["sha256"], f"raw hash {name}")
ck(inv["session_id"] == 0 and "sshd.exe" in inv["ssh_ancestor_names"],
   "session-zero SSH")
ck(inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "native mutex")
ck(inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1,
   "separate protected GUI")
ck([s["name"] for s in steps] ==
   ["import", "export", "calc", "jsonreport", "check_import_export"],
   "guarded five-step sequence")
for step in steps:
    ck(step["status"] == "completed" and step["exit_code"] == 0,
       f"completed step {step['name']}")
for step in steps[:4]:
    ck(step["gui_preserved"] is True, f"GUI preserved {step['name']}")
ck(sha(DRUN / "closure.json") == contract["excluded_diagnostic"]["closure_sha256"],
   "excluded raw closure pinned, not accepted")
ck(sha(EXCLUDED / "contract.json") ==
   contract["excluded_diagnostic"]["contract_sha256"],
   "excluded positive gate contract pinned")

parent = tables(load(parent_source), "model")
child = tables(load(source), "model")
export = tables(load(RUN / "roundtrip-raw.json"), "model")
ck(diff["parent_input_sha256"] == sha(parent_source), "diff parent SHA")
ck(diff["child_input_sha256"] == sha(source), "diff child SHA")
changed = []
added = []
for name in sorted(set(parent) | set(child)):
    a, b = parent.get(name), child.get(name)
    ck(a is not None and b is not None, f"same table family {name}")
    if a is None or b is None:
        continue
    ck(cols(a) == cols(b), f"same authored schema {name}")
    ar, br = rows(a), rows(b)
    ck(len(br) >= len(ar), f"no removed rows {name}")
    for number, (old, new) in enumerate(zip(ar, br)):
        for column, x, y in zip(cols(a), old, new):
            if x != y:
                changed.append((name, number, column, x, y))
    for row in br[len(ar):]:
        added.append((name, dict(zip(cols(b), row))))
ck(changed == [("Control", 0, "SIMPE", 60.0, 65.0)],
   "only existing-cell delta is simulation end 60-to-65")
ck(diff["changed_cells"] == [
    {"table": "Control", "instance": 0, "row": 0, "column": "SIMPE",
     "before": 60.0, "after": 65.0}], "declared one-cell delta")
ck(added == [(r["table"], r["values"]) for r in
             sorted(diff["added_rows"], key=lambda z: z["table"])],
   "four exact appended business rows")
ck([name for name, _ in added] ==
   ["MissionPreparation", "MissionTurnround", "MissionType", "OperationProfile"],
   "added rows confined to terminal mission")
control = dict(zip(cols(child["Control"]), rows(child["Control"])[0]))
ck(control["SIMPE"] == 65 and control["RCEND"] == 60,
   "simulation end 65, report cutoff 60")
for row in rows(child["ResultCollection"]):
    ck(row[cols(child["ResultCollection"]).index("RCEND")] == 60,
       "result collection ends at 60")
authored = sorted(name for name in child if rows(child[name]))
ck(len(authored) == 30, "30 row-containing source tables")
for name in authored:
    ck(name in export, f"native export has {name}")
    if name not in export:
        continue
    ac, ec = cols(child[name]), cols(export[name])
    ck(all(c in ec for c in ac), f"export authored columns {name}")
    if all(c in ec for c in ac):
        projected = [[r[ec.index(c)] for c in ac] for r in rows(export[name])]
        ck(projected == rows(child[name]), f"exact native rows {name}")
log = (RUN / "run.log").read_text(encoding="utf-8-sig")
ck("Errors: 0, Warnings: 1, Notes: 0" in log, "zero conversion errors")
ck(set(re.findall(r"\((?:warning|notice|error) #(\d+)\)", log)) == {"108"},
   "only converter warning #108")
ck((RUN / "model.sxo").stat().st_size > 4, "usable result SXO")

lines = (RUN / "model.log").read_text(encoding="utf-8-sig").splitlines()
dlines = (DRUN / "model.log").read_text(encoding="utf-8-sig").splitlines()
ck(lines == dlines, "new native event log reproduces sealed diagnostic")
for hour, phrase in [
    (21.5, "<RISK-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 2"),
    (23.5, "<RISK-MISSION,TEACH-UNIT,0,0,0> mission completed"),
    (25.5, "<BASIC-MISSION,TEACH-UNIT,0,0,1> mission starting, duration: 2"),
    (27.5, "<BASIC-MISSION,TEACH-UNIT,0,0,1> mission completed"),
    (45.5, "<RISK-MISSION,TEACH-UNIT,0,0,2> mission starting, duration: 2"),
    (46.4896, "<TEACH-AIR-01,0> critical random failure added"),
    (46.4896, "<RISK-MISSION,TEACH-UNIT,0,0,2> mission aborted"),
    (47.9896, "system SURP task 14 on <TEACH-AIR-01,0> started"),
    (47.9896, "remove subitem subtask 14 seqno 1 within system SURP task 14 on <TEACH-AIR-01,0> starts performing, planned to last for 15 hours"),
    (49.9896, "system SURP task 14 on <TEACH-AIR-01,0> subitem received <TEACH-LRU-01,0,2>"),
    (50.25, "<BASIC-MISSION,TEACH-UNIT,0,0,3> mission cancelled"),
    (59.5, "<TEACH-UNIT> mission ordered: TERMINAL-HOLD"),
    (59.5, "<TERMINAL-HOLD,TEACH-UNIT,0,0,4> mission activated, systems requested: 2"),
    (59.5, "<TERMINAL-HOLD,TEACH-UNIT,0,0,4> mission allocates system: <TEACH-AIR-01,1>"),
    (59.5, "system PM task 18 on <TEACH-AIR-01,1> paused"),
    (59.5, "subtask 18 seqno 1 within system PM task 18 on <TEACH-AIR-01,1> resource waiting stopped"),
    (59.5, "<TEACH-AIR-01,1> preparation started, mission: <TERMINAL-HOLD,TEACH-UNIT,0,0,4>"),
    (59.5, "<TERMINAL-HOLD,TEACH-UNIT,0,0,4> mission waiting:  timeout at 62"),
    (59.5, "<P-CREW at <BASE-01,0>> allocated to maintenance task"),
    (59.5, "subtask 19 seqno 1 within system preparation task 19 on <TEACH-AIR-01,1> starts performing, planned to last for 0.5 hours"),
    (60, "subtask 19 seqno 1 within system preparation task 19 on <TEACH-AIR-01,1> completed"),
    (60, "<P-CREW at <BASE-01,0>> deallocated from  maintenance task"),
    (60, "<TEACH-AIR-01,1> preparation ended, mission: <TERMINAL-HOLD,TEACH-UNIT,0,0,4>"),
    (62, "<TERMINAL-HOLD,TEACH-UNIT,0,0,4> mission cancelled"),
    (62.9896, "remove subitem subtask 14 seqno 1 within system SURP task 14 on <TEACH-AIR-01,0> completed"),
]:
    event(lines, hour, phrase)
ck(not any("TERMINAL-HOLD" in s and "mission preassigns" in s for s in lines),
   "no named mission preassignment")
ck(not any("TERMINAL-HOLD" in s and ("mission cancelled" in s or
           "mission releases" in s) and s.startswith("Time: 59") for s in lines),
   "no release/cancel during final report bin")
ck(not any("TERMINAL-HOLD" in s and "mission starting" in s for s in lines),
   "held mission does not launch")
ck(not any("reserve" in s.lower() and "TEACH-LRU" in s for s in lines),
   "no explicit item reservation log")
ck(not any("remove subitem subtask 14" in s and "completed" in s and
           float(re.match(r"Time: ([\d.e+\-]+)", s)[1]) <= 60 for s in lines),
   "LRU removal is still performing through cutoff")

# Replay pooled worker use through the report cutoff, including two leases
# active during the final bin. The 65-hour tail is deliberately not a 60-hour
# terminal result.
opened = {"P-MAINT": None, "P-CREW": None}
leases = []
for line in lines:
    m = re.match(r"Time: ([\d.e+\-]+)  <(P-MAINT|P-CREW) at <BASE-01,0>> "
                 r"(allocated to maintenance task|deallocated from  maintenance task)", line)
    if not m or float(m[1]) > 60:
        continue
    hour, kind, action = float(m[1]), m[2], m[3]
    if action.startswith("allocated"):
        ck(opened[kind] is None, f"no double lease {kind} {hour}")
        opened[kind] = hour
    else:
        ck(opened[kind] is not None, f"matching lease {kind} {hour}")
        if opened[kind] is not None:
            leases.append((opened[kind], hour, kind))
        opened[kind] = None
ck(opened["P-MAINT"] is not None and
   abs(opened["P-MAINT"] - 47.9896) < .00012,
   "maintainer remains on aircraft removal at cutoff")
ck(opened["P-CREW"] is None, "crew releases exactly at cutoff")
leases.append((opened["P-MAINT"], 60, "P-MAINT"))
ck(any(abs(x-59.5)<.0001 and abs(y-60)<.0001 and k=="P-CREW"
       for x,y,k in leases), "crew works final half hour")

report = tables(load(RUN / "report-raw.json"), "report")
preport = tables(load(PRUN / "report-raw.json"), "report")
dreport = tables(load(DRUN / "report-raw.json"), "report")
ck(set(report) == set(preport), "same report tables as parent")
for name in sorted(report):
    ck(cols(report[name]) == cols(dreport[name]) and
       rows(report[name]) == rows(dreport[name]),
       f"fresh native report reproduces excluded probe bytes semantically: {name}")
summary = dict(zip(cols(report["ResultSummary"]), rows(report["ResultSummary"])[0]))
parent_summary = dict(zip(cols(preport["ResultSummary"]), rows(preport["ResultSummary"])[0]))
ck(summary["RTIUP"] == 65 and parent_summary["RTIUP"] == 60,
   "summary covers 65h simulation, not 60h cutoff")
for col in sorted(set(summary) - {"RTIUP"}):
    ck(summary[col] == parent_summary[col], f"summary other factor {col}")
for name in ("SystemResults", "StockTotalResults", "ResourceResults"):
    ck(len(rows(report[name])) == 120, f"120 half-hour {name} bins")
    ck(cols(report[name]) == cols(preport[name]), f"same {name} schema")
system, stock, resource = (report[n] for n in
                           ("SystemResults", "StockTotalResults", "ResourceResults"))
psystem, pstock, presource = (preport[n] for n in
                              ("SystemResults", "StockTotalResults", "ResourceResults"))
sc, tc, rc = map(cols, (system, stock, resource))
sr, st, rr = map(rows, (system, stock, resource))
ps, pt, pr = map(rows, (psystem, pstock, presource))
ck(st == pt, "all 120 stock rows unchanged from accepted active repair")
for i in range(120):
    a, b = i/2, (i+1)/2
    sm, tm, rm = (dict(zip(c, row)) for c, row in
                  ((sc, sr[i]), (tc, st[i]), (rc, rr[i])))
    psm, prm = (dict(zip(c, row)) for c, row in ((sc, ps[i]), (rc, pr[i])))
    for name, row in (("system", sm), ("stock", tm), ("resource", rm)):
        approx(row["STINT"], a, f"{name} bin {i} start")
        approx(row["ETINT"], b, f"{name} bin {i} end")
    for col in tc:
        ck(tm[col] == pt[i][tc.index(col)], f"stock cell bin {i} {col}")
    for col in sc:
        if col in ("UNID", "SID", "STINT", "ETINT"):
            continue
        if i == 95 and col in ("SYDT", "NSYDT"):
            approx(sm[col], 15.3333333 if col=="SYDT" else 1,
                   f"extended-horizon repair marker {col}")
        elif i == 119 and col in ("NSYRY", "NSYMA", "NSYMP", "NPSTA"):
            approx(sm[col], 0 if col=="NSYRY" else 1,
                   f"allocated preparation last bin {col}")
        else:
            ck(sm[col] == psm[col], f"parent system cell bin {i} {col}")
    for col in rc:
        if col in ("RID", "STID", "STINT", "ETINT", "NRUM", "NRW"):
            continue
        ck(rm[col] == prm[col], f"parent resource cell bin {i} {col}")
    working = sum(occupancy(a,b,[(x,y)]) for x,y,_ in leases)
    approx(rm["NRUM"], working, f"worker booking bin {i}")
    waiting = occupancy(a,b,[(20.5,21),(24.5,25),(28.5,29.5),
                              (44.5,45),(54.5,59.5)])
    approx(rm["NRW"], waiting, f"worker wait bin {i}")
    approx(sm["NSYRP"], occupancy(a,b,[(47.9896,60)]),
           f"aircraft removal occupancy bin {i}")
    approx(tm["NBO"], occupancy(a,b,[(47.9896,49.9896)]),
           f"base item backorder bin {i}")
    if i == 119:
        for col, expected in {"NSYMR":0,"NSYRP":1,"NSYWI":0,
                              "NSYRY":0,"NSYMA":1,"NSYMP":1,
                              "NPSTA":1}.items():
            approx(sm[col],expected,f"last interval {col}")
        for col,expected in {"NRUM":2,"NRW":0}.items():
            approx(rm[col],expected,f"last interval {col}")
        approx(tm["NBO"],0,"last interval no backorder")

approx(sum((r[rc.index("NRUM")] or 0)/2 for r in rr),
       sum(y-x for x,y,_ in leases), "integrated booked resource hours")
approx(sum((r[rc.index("NRW")] or 0)/2 for r in rr), 7.5,
       "integrated resource wait hours")
tot = dict(zip(cols(report["ResourceResultsTotal"]),
               rows(report["ResourceResultsTotal"])[0]))
approx(tot["NRUM"], sum(y-x for x,y,_ in leases)/60,
       "aggregate resource busy fraction")
approx(tot["NRW"], 7.5/60, "aggregate resource waiting fraction")

verdict = {
    "case": "F02.var04 report-cutoff mission allocation v1.0.0",
    "passed": not failures,
    "verdict": "GO: bounded allocation/preparation in final reporting interval" if not failures else "NO-GO",
    "checks_passed": count - len(failures), "checks_total": count,
    "failures": failures,
    "native_closure_sha256": sha(RUN / "closure.json"),
    "native_report_sha256": sha(RUN / "report-raw.json"),
    "parent_closure_sha256": sha(PRUN / "closure.json"),
    "limits": [
        "The healthy aircraft is allocated and preparing during [59.5,60), then preparation ends exactly at h60; it is not performing preparation after h60.",
        "The mission allocation is still open at the report cutoff, then the mission cancels at h62 in a 65-hour simulation.",
        "There is no native TERMINAL-HOLD preassignment event or stock-reservation event; neither is claimed.",
        "The final report row is an interval average, while ResultSummary spans the full 65-hour simulation.",
        "One seed, two aircraft and one 60-hour report cutoff; no general scheduling priority or cross-engine claim.",
    ],
}
OUT.write_bytes((json.dumps(verdict, indent=2, sort_keys=True) + "\n").encode("utf-8"))
print(json.dumps({"passed": verdict["passed"], "checks": count,
                  "failures": failures[:20], "script_sha256": sha(Path(__file__)),
                  "verdict_sha256": sha(OUT)}, sort_keys=True))
raise SystemExit(0 if verdict["passed"] else 1)
