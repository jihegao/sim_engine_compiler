"""Independent read-only replay of J09.var06 SCTRT=2 native evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
BASE = CASE.parent
PARENT = BASE / "E04-upstream-transport-slow-v1.0.0"
PRUN = PARENT / "runs/e04-slow-v100-ssh-20260929-01"
DIAG = BASE / "J09-var06-transport-scale-v1.0.0"
DRUN = DIAG / "runs/j09-var06-sctrt2-v100-ssh-20261004-01"
RUN = CASE / "runs/j09-var06-sctrt2-v101-ssh-20261004-01"
OUT = CASE / "review/independent-verdict.json"
checks = 0
failures: list[str] = []


def ck(ok, label):
    global checks
    checks += 1
    if not ok:
        failures.append(label)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(re.sub(r",\s*([}\]])", r"\1",
                             path.read_text(encoding="utf-8-sig")))


def table_map(doc, root):
    return {table["name"]: table for table in doc[root]["tables"]}


def columns(table):
    return [c["name"] for c in table["columns"]]


def rows(table):
    return [row for instance in table["instances"] for row in instance["rows"]]


def approx(value, expected, label, tolerance=.00035):
    if value is None and expected == 0:
        value = 0
    ck(isinstance(value, (int, float)) and abs(value - expected) < tolerance,
       f"{label}: {value} vs {expected}")


def occupancy(a, b, intervals):
    return sum(max(0.0, min(b, y) - max(a, x)) / (b-a) for x, y in intervals)


def event(lines, time, phrase):
    ck(any((m := re.match(r"Time: ([\d.e+\-]+) (.*)", line)) and
           abs(float(m[1]) - time) < .00012 and phrase in m[2]
           for line in lines), f"event {time}: {phrase}")


contract = read(CASE / "contract.json")
diff = read(CASE / "exact-diff.json")
closure = read(RUN / "closure.json")
inv = read(RUN / "invocation.json")
steps = read(RUN / "steps.json")
source = CASE / "scaled-input.json"
parent_source = PARENT / "native-input.json"
files = {
    "input": source, "parent": parent_source,
    "parent_closure": PRUN / "closure.json",
    "parent_signoff": PARENT / "cli-scope-signoff-2026-09-29.md",
    "diagnostic_closure": DRUN / "closure.json",
    "contract": CASE / "contract.json", "exact_diff": CASE / "exact-diff.json",
    "build.py": CASE / "build.py", "describe_diff.py": CASE / "describe_diff.py",
    "check_roundtrip.py": CASE / "check_roundtrip.py",
    "run_native_ssh.ps1": CASE / "run_native_ssh.ps1",
}
ck(closure["source_hashes_before"] == closure["source_hashes_after"],
   "source before/after stable")
ck(inv["source_hashes_before"] == closure["source_hashes_before"],
   "invocation and closure source pins")
for key, path in sorted(files.items()):
    ck(path.is_file(), f"source exists {key}")
    if path.is_file():
        ck(sha(path) == closure["source_hashes_before"][key],
           f"source hash {key}")
ck(sha(source) == contract["scaled_input_sha256"], "contract child input")
ck(sha(parent_source) == contract["accepted_parent"]["input_sha256"],
   "contract parent input")
ck(sha(DRUN / "closure.json") ==
   contract["excluded_diagnostic"]["closure_sha256"],
   "excluded v1.0.0 closure pin")
diag = read(DIAG / "diagnostic.json")
ck(diag["publication_state"] == "excluded_diagnostic" and
   "optional columns" in diag["reason"] and
   diag["closure_sha256"] == sha(DRUN / "closure.json"),
   "previous strict-checker failure is excluded")
ck(sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"],
   "contract diff seal")
ck(sha(RUN / "input.json") == sha(source), "native input byte copy")
ck(sha(RUN / "invocation.json") == closure["invocation_sha256"],
   "invocation seal")
ck(closure["run_id"] == RUN.name and closure["error"] is None,
   "fresh native closure")
ck(len(closure["raw"]) == 12, "twelve sealed raw files")
for name, seal in sorted(closure["raw"].items()):
    path = RUN / name
    ck(path.is_file(), f"raw exists {name}")
    if path.is_file():
        ck(path.stat().st_size == seal["bytes"], f"raw length {name}")
        ck(sha(path) == seal["sha256"], f"raw SHA {name}")
ck(inv["session_id"] == 0 and "sshd.exe" in inv["ssh_ancestor_names"],
   "session-zero SSH")
ck(inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "host mutex")
ck(inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1,
   "preserved separate GUI")
ck([s["name"] for s in steps] ==
   ["import", "export", "calc", "jsonreport", "check_import_export"],
   "native five-step order")
for s in steps:
    ck(s["status"] == "completed" and s["exit_code"] == 0,
       f"step completed {s['name']}")
for s in steps[:4]:
    ck(s["gui_preserved"] is True, f"GUI preserved {s['name']}")
runlog = (RUN / "run.log").read_text(encoding="utf-8-sig")
ck("Errors: 0, Warnings: 1, Notes: 0" in runlog,
   "converter errors zero")
ck(set(re.findall(r"\((?:warning|notice|error) #(\d+)\)", runlog)) == {"108"},
   "only reviewed warning #108")
ck((RUN / "model.sxo").stat().st_size > 4, "valid simulated SXO")

parent = table_map(read(parent_source), "model")
child = table_map(read(source), "model")
export = table_map(read(RUN / "roundtrip-raw.json"), "model")
ck(diff["parent_input_sha256"] == sha(parent_source), "exact diff parent")
ck(diff["scaled_input_sha256"] == sha(source), "exact diff child")
ck(len(parent) == 31 and len(child) == 32 and
   set(child) - set(parent) == {"ScaleFactors"},
   "only appended ScaleFactors table")
ck(diff["unchanged_existing_tables"] == 31 and
   diff["other_changes"] == [] and
   child["ScaleFactors"] == diff["appended_table"],
   "declared source topology")
for name in sorted(parent):
    ck(parent[name] == child[name], f"unchanged authored table {name}")
ck(columns(child["ScaleFactors"]) ==
   ["SCFRT", "SCRPT", "SCLDT", "SCPMI", "SCPMT", "SCTRT"] and
   rows(child["ScaleFactors"]) == [[1.0,1.0,1.0,1.0,1.0,2.0]],
   "SCTRT2 is only non-unit scale")
authored = sorted(name for name in child if rows(child[name]))
ck(len(authored) == 22, "22 source row-containing tables")
for name in authored:
    ck(name in export, f"native table present {name}")
    if name not in export:
        continue
    sc, ec = columns(child[name]), columns(export[name])
    ck(all(c in ec for c in sc), f"native authored columns {name}")
    if all(c in ec for c in sc):
        projected = [[r[ec.index(c)] for c in sc] for r in rows(export[name])]
        ck(projected == rows(child[name]), f"authored rows preserved {name}")
extras = [c for c in columns(export["ScaleFactors"])
          if c not in columns(child["ScaleFactors"])]
ck(len(extras) == 10, "ten native optional ScaleFactors columns")
for row in rows(export["ScaleFactors"]):
    for col in extras:
        ck(row[columns(export["ScaleFactors"]).index(col)] is None,
           f"native optional column null {col}")

lines = (RUN / "model.log").read_text(encoding="utf-8-sig").splitlines()
plines = (PRUN / "model.log").read_text(encoding="utf-8-sig").splitlines()
for arm, log, down, up, ready in (
    ("parent", plines, 2, 2, 14.5),
    ("child", lines, 4, 4, 18.5),
):
    for hour, phrase in [
        (8, "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 2"),
        (9.8829, "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted"),
        (10, "system SURP task 0 on <TEACH-AIR-01,0> started"),
        (10, "<TEACH-LRU-01,0,BASE-01,0> Backorder added"),
        (10.1667, "Item requiring maintenance arrives <TEACH-LRU-01,0,1>"),
        (10.1667, f"transport task 0 starts with 1 items/systems, transport time: {down}"),
        (10.1667+down, "transport task 0 arrives with 1 items/systems"),
        (10.1667+down, "Take replacement item <TEACH-LRU-01,0,0> from stock"),
        (10.1667+down, f"transport task 2 starts with 1 items/systems, transport time: {up}"),
        (10.1667+down+1, "item DIRP task 1 on <TEACH-LRU-01,0,1> completed"),
        (10.1667+down+up, "transport task 2 arrives with 1 items/systems"),
        (10.1667+down+up, "<TEACH-LRU-01,0,BASE-01,0> Backorder removed"),
        (10.1667+down+up, "system SURP task 0 on <TEACH-AIR-01,0> subitem received <TEACH-LRU-01,0,0>"),
        (ready, "system SURP task 0 on <TEACH-AIR-01,0> completed"),
        (ready, "System ready <TEACH-AIR-01,0>"),
        (20, "<BASIC-MISSION,TEACH-UNIT,0,0,1> mission starting, duration: 2"),
        (22, "<BASIC-MISSION,TEACH-UNIT,0,0,1> mission completed"),
        (32, "<BASIC-MISSION,TEACH-UNIT,0,0,2> mission starting, duration: 2"),
        (34, "<BASIC-MISSION,TEACH-UNIT,0,0,2> mission completed"),
    ]:
        ck(any((m:=re.match(r"Time: ([\d.e+\-]+) (.*)",s)) and
               abs(float(m[1])-hour)<.00012 and phrase in m[2] for s in log),
           f"{arm} event {hour}: {phrase}")
    ck(sum("transport task 0 arrives" in s for s in log) == 1 and
       sum("transport task 2 arrives" in s for s in log) == 1,
       f"{arm} one arrival each direction")
    ck(sum("Backorder added" in s for s in log) == 1 and
       sum("Backorder removed" in s for s in log) == 1,
       f"{arm} one physical base backorder lifecycle")

report = table_map(read(RUN / "report-raw.json"), "report")
preport = table_map(read(PRUN / "report-raw.json"), "report")
ck(set(report) == set(preport), "report table set")
ck(rows(report["ResultSummary"]) == rows(preport["ResultSummary"]),
   "same 3-mission outcome summary")
for name in ("SystemResults", "StockTotalResults"):
    ck(len(rows(report[name])) == 72, f"72 {name} half-hour bins")
    ck(columns(report[name]) == columns(preport[name]),
       f"{name} schema as parent")
sc, tc = columns(report["SystemResults"]), columns(report["StockTotalResults"])
sr, st = rows(report["SystemResults"]), rows(report["StockTotalResults"])
ps, pt = rows(preport["SystemResults"]), rows(preport["StockTotalResults"])
system_changed = {"NSYRY","NSYUA","NSYA","NSYRP","NSYWI","NREPT","SYDT"}
stock_changed = {"NBO","WT","WTT","WTS","PNB"}
for i in range(72):
    a,b=i/2,(i+1)/2
    s,t,sp,tp=(dict(zip(c,r)) for c,r in
              ((sc,sr[i]),(tc,st[i]),(sc,ps[i]),(tc,pt[i])))
    for label,r in (("system",s),("stock",t)):
        approx(r["STINT"],a,f"{label} start bin {i}")
        approx(r["ETINT"],b,f"{label} end bin {i}")
    for col in sc:
        if col in system_changed or col in ("UNID","SID","STINT","ETINT"):
            continue
        if isinstance(s[col],(int,float)) or isinstance(sp[col],(int,float)):
            approx(s[col],sp[col] or 0,f"unchanged system {col} bin {i}")
        else:
            ck(s[col]==sp[col],f"unchanged system {col} bin {i}")
    for col in tc:
        if col in stock_changed or col in ("STINT","ETINT"):
            continue
        if isinstance(t[col],(int,float)) or isinstance(tp[col],(int,float)):
            approx(t[col],tp[col] or 0,f"unchanged stock {col} bin {i}")
        else:
            ck(t[col]==tp[col],f"unchanged stock {col} bin {i}")
    extra_wait=occupancy(a,b,[(14.1667,18.1667)])
    approx(s["NSYRY"],(sp["NSYRY"] or 0)-occupancy(a,b,[(14.5,18.5)]),
           f"ready-aircraft delay bin {i}")
    approx(s["NSYUA"],(sp["NSYUA"] or 0)+occupancy(a,b,[(14.5,18.5)]),
           f"unavailable-aircraft delay bin {i}")
    approx(s["NSYA"],(sp["NSYA"] or 0)-occupancy(a,b,[(14.5,18.5)]),
           f"available-aircraft delay bin {i}")
    approx(s["NSYRP"],occupancy(a,b,[(10,10.1667),(18.1667,18.5)]),
           f"repair-work bin {i}")
    approx(s["NSYWI"],occupancy(a,b,[(10.1667,18.1667)]),
           f"item-wait bin {i}")
    approx(t["NBO"],occupancy(a,b,[(10,18.1667)]),
           f"physical base backorder bin {i}")
    approx(t["PNB"],1-occupancy(a,b,[(10,18.1667)]),
           f"no-backorder share bin {i}")
    approx(s["NREPT"],1 if i==36 else 0 if i==29 else sp["NREPT"],
           f"repair-completion marker bin {i}")
    if i==20:
        approx(s["SYDT"],8.5,"system down-time marker")
        for col in ("WT","WTT","WTS"):
            approx(t[col],8.1666667,f"stock wait marker {col}")
    else:
        ck(s["SYDT"]==sp["SYDT"],f"system down-time unchanged bin {i}")
        for col in ("WT","WTT","WTS"):
            ck(t[col]==tp[col],f"stock wait unchanged {col} bin {i}")
approx(sum((r[sc.index("NSYWI")] or 0)/2 for r in sr),8,
       "eight aircraft item-wait hours")
approx(sum((r[tc.index("NBO")] or 0)/2 for r in st),8.1666667,
       "8.1667 base backorder hours")
approx(sr[-1][sc.index("NSYRY")],1,"terminal aircraft ready")
approx(sr[-1][sc.index("NSYWI")],0,"terminal no item wait")
approx(st[-1][tc.index("NBO")],0,"terminal no stock backorder")
summary=dict(zip(columns(report["ResultSummary"]),rows(report["ResultSummary"])[0]))
approx(summary["NREP"],1,"one replication")
approx(summary["MSUF"],2/3,"two of three missions succeed")

verdict={
    "case":"J09.var06 SCTRT2 v1.0.1",
    "passed":not failures,
    "verdict":"GO: bounded two-hour route scaled to four hours" if not failures else "NO-GO",
    "checks_passed":checks-len(failures),"checks_total":checks,"failures":failures,
    "native_closure_sha256":sha(RUN/"closure.json"),
    "native_report_sha256":sha(RUN/"report-raw.json"),
    "parent_closure_sha256":sha(PRUN/"closure.json"),
    "limits":[
        "One seed, one failed LRU, one SLOW base/depot route, one SCTRT=2 input and a 36-hour horizon.",
        "The observed physical legs last four hours each and shift base backorder clearance/aircraft readiness; no other ScaleFactors field is tested.",
        "Native optional ScaleFactors columns are null and preserve all six authored fields; the excluded v1.0.0 strict-checker failure is not accepted evidence.",
        "The reports aggregate half-hour occupancy; physical item IDs and movements come from the event log.",
        "No population law, other route, GUI visual behavior or cross-engine parity is inferred.",
    ],
}
OUT.write_bytes((json.dumps(verdict,indent=2,sort_keys=True)+"\n").encode("utf-8"))
print(json.dumps({"passed":verdict["passed"],"checks":checks,
                  "failures":failures[:20],"script_sha256":sha(Path(__file__)),
                  "verdict_sha256":sha(OUT)},sort_keys=True))
raise SystemExit(0 if verdict["passed"] else 1)
