"""Independent read-only replay of J09.var02 SCRPT=2 native artifacts."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
BASE = CASE.parent
PARENT = BASE / "E04-upstream-transport-slow-v1.0.0"
PRUN = PARENT / "runs/e04-slow-v100-ssh-20260929-01"
PRECEDENT = BASE / "J09-var06-transport-scale-v1.0.1"
XRUN = PRECEDENT / "runs/j09-var06-sctrt2-v101-ssh-20261004-01"
RUN = CASE / "runs/j09-var02-scrpt2-v100-ssh-20261004-01"
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


def tabs(doc, root):
    return {t["name"]: t for t in doc[root]["tables"]}


def cols(t):
    return [c["name"] for c in t["columns"]]


def rows(t):
    return [r for ins in t["instances"] for r in ins["rows"]]


def near(value, expected, label, tolerance=.00035):
    if value is None and expected == 0:
        value = 0
    ck(isinstance(value, (int, float)) and abs(value - expected) < tolerance,
       f"{label}: {value} versus {expected}")


def event(lines, time, phrase, arm):
    ck(any((m := re.match(r"Time: ([\d.e+\-]+) (.*)", s)) and
           abs(float(m[1])-time)<.00012 and phrase in m[2] for s in lines),
       f"{arm} event {time}: {phrase}")


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
    "precedent_input": PRECEDENT / "scaled-input.json",
    "precedent_closure": XRUN / "closure.json",
    "precedent_evidence_index": PRECEDENT / "evidence-index.json",
    "contract": CASE / "contract.json", "exact_diff": CASE / "exact-diff.json",
    "build.py": CASE / "build.py", "describe_diff.py": CASE / "describe_diff.py",
    "check_roundtrip.py": CASE / "check_roundtrip.py",
    "run_native_ssh.ps1": CASE / "run_native_ssh.ps1",
}
ck(closure["source_hashes_before"] == closure["source_hashes_after"],
   "frozen sources stable before/after")
ck(inv["source_hashes_before"] == closure["source_hashes_before"],
   "invocation source pins match closure")
for name, path in sorted(files.items()):
    ck(path.is_file(), f"source exists {name}")
    if path.is_file():
        ck(sha(path) == closure["source_hashes_before"][name],
           f"source SHA {name}")
ck(sha(source) == contract["scaled_input_sha256"], "contract child source")
ck(sha(parent_source) == contract["accepted_parent"]["input_sha256"],
   "contract accepted E04 source")
ck(sha(PRECEDENT / "scaled-input.json") ==
   contract["scale_schema_precedent"]["input_sha256"],
   "accepted scale precedent source")
ck(sha(XRUN / "closure.json") ==
   contract["scale_schema_precedent"]["closure_sha256"],
   "accepted scale precedent closure")
ck(sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"],
   "contract exact diff")
ck(sha(RUN / "input.json") == sha(source), "native input copy")
ck(sha(RUN / "invocation.json") == closure["invocation_sha256"],
   "invocation SHA")
ck(closure["run_id"] == RUN.name and closure["error"] is None,
   "fresh native closure")
ck(len(closure["raw"]) == 12, "twelve raw seals")
for name, seal in sorted(closure["raw"].items()):
    path = RUN / name
    ck(path.is_file(), f"raw exists {name}")
    if path.is_file():
        ck(path.stat().st_size == seal["bytes"], f"raw bytes {name}")
        ck(sha(path) == seal["sha256"], f"raw SHA {name}")
ck(inv["session_id"] == 0 and "sshd.exe" in inv["ssh_ancestor_names"],
   "SSH session zero")
ck(inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "global mutex")
ck(inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1,
   "separate GUI identity")
ck([s["name"] for s in steps] ==
   ["import", "export", "calc", "jsonreport", "check_import_export"],
   "five guarded native steps")
for s in steps:
    ck(s["status"] == "completed" and s["exit_code"] == 0,
       f"step {s['name']}")
for s in steps[:4]:
    ck(s["gui_preserved"] is True, f"GUI preserved {s['name']}")
log = (RUN / "run.log").read_text(encoding="utf-8-sig")
ck("Errors: 0, Warnings: 1, Notes: 0" in log, "zero converter errors")
ck(set(re.findall(r"\((?:warning|notice|error) #(\d+)\)", log)) == {"108"},
   "only warning #108")
ck((RUN / "model.sxo").stat().st_size > 4, "usable native SXO")

parent = tabs(read(parent_source), "model")
child = tabs(read(source), "model")
export = tabs(read(RUN / "roundtrip-raw.json"), "model")
ck(diff["parent_input_sha256"] == sha(parent_source), "diff parent SHA")
ck(diff["scaled_input_sha256"] == sha(source), "diff child SHA")
ck(len(parent) == 31 and len(child) == 32 and
   set(child) - set(parent) == {"ScaleFactors"},
   "ScaleFactors only new table")
ck(diff["unchanged_existing_tables"] == 31 and
   diff["other_changes"] == [] and
   diff["appended_table"] == child["ScaleFactors"],
   "source matches declared exact diff")
for name in sorted(parent):
    ck(child[name] == parent[name], f"existing source table unchanged {name}")
ck(cols(child["ScaleFactors"]) ==
   ["SCFRT", "SCRPT", "SCLDT", "SCPMI", "SCPMT", "SCTRT"] and
   rows(child["ScaleFactors"]) == [[1.0,2.0,1.0,1.0,1.0,1.0]],
   "SCRPT2 sole non-unit factor")
authored = sorted(name for name in child if rows(child[name]))
ck(len(authored) == 22, "22 row-containing authored tables")
for name in authored:
    ck(name in export, f"exported table {name}")
    if name not in export:
        continue
    ac, ec = cols(child[name]), cols(export[name])
    ck(all(c in ec for c in ac), f"exported authored columns {name}")
    if all(c in ec for c in ac):
        projected = [[r[ec.index(c)] for c in ac] for r in rows(export[name])]
        ck(projected == rows(child[name]), f"native authored-row roundtrip {name}")
extra = [c for c in cols(export["ScaleFactors"])
         if c not in cols(child["ScaleFactors"])]
ck(len(extra) == 10, "ten extra native optional scale columns")
for row in rows(export["ScaleFactors"]):
    for c in extra:
        ck(row[cols(export["ScaleFactors"]).index(c)] is None,
           f"native-only optional scale cell null {c}")

lines = (RUN / "model.log").read_text(encoding="utf-8-sig").splitlines()
plines = (PRUN / "model.log").read_text(encoding="utf-8-sig").splitlines()
for arm, evidence, repair_end in (("parent", plines, 13.1667),
                                  ("child", lines, 14.1667)):
    for time, phrase in [
        (8, "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 2"),
        (9.8829, "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted"),
        (10, "system SURP task 0 on <TEACH-AIR-01,0> started"),
        (10, "<TEACH-LRU-01,0,BASE-01,0> Backorder added"),
        (10.1667, "Item requiring maintenance arrives <TEACH-LRU-01,0,1>"),
        (10.1667, "transport task 0 starts with 1 items/systems, transport time: 2"),
        (12.1667, "transport task 0 arrives with 1 items/systems"),
        (12.1667, "Item requiring maintenance arrives <TEACH-LRU-01,0,1>"),
        (12.1667, "Take replacement item <TEACH-LRU-01,0,0> from stock"),
        (12.1667, "transport task 2 starts with 1 items/systems, transport time: 2"),
        (12.1667, "item DIRP task 1 on <TEACH-LRU-01,0,1> started"),
        (repair_end, "item DIRP task 1 on <TEACH-LRU-01,0,1> completed"),
        (repair_end, "Put back replacement item <TEACH-LRU-01,0,1> to stock"),
        (14.1667, "transport task 2 arrives with 1 items/systems"),
        (14.1667, "<TEACH-LRU-01,0,BASE-01,0> Backorder removed"),
        (14.1667, "system SURP task 0 on <TEACH-AIR-01,0> subitem received <TEACH-LRU-01,0,0>"),
        (14.5, "system SURP task 0 on <TEACH-AIR-01,0> completed"),
        (14.5, "System ready <TEACH-AIR-01,0>"),
        (20, "<BASIC-MISSION,TEACH-UNIT,0,0,1> mission starting, duration: 2"),
        (22, "<BASIC-MISSION,TEACH-UNIT,0,0,1> mission completed"),
        (32, "<BASIC-MISSION,TEACH-UNIT,0,0,2> mission starting, duration: 2"),
        (34, "<BASIC-MISSION,TEACH-UNIT,0,0,2> mission completed"),
    ]:
        event(evidence, time, phrase, arm)
    event(evidence, 12.1667,
          f"starts performing, planned to last for {int(repair_end-12.1667)} hours", arm)
    ck(sum("Backorder added" in s for s in evidence) == 1 and
       sum("Backorder removed" in s for s in evidence) == 1,
       f"{arm} single backorder lifecycle")
    ck(sum("item DIRP task 1" in s and "completed" in s for s in evidence) >= 1,
       f"{arm} failed LRU1 physically repaired")
ck(not any("<TEACH-LRU-01,0,0>" in s and "item DIRP task" in s for s in lines),
   "stocked spare0 is distinct from failed repaired LRU1")

report = tabs(read(RUN / "report-raw.json"), "report")
preport = tabs(read(PRUN / "report-raw.json"), "report")
ck(set(report) == set(preport), "same report table set")
ck(sha(RUN / "report-raw.json") == sha(PRUN / "report-raw.json"),
   "selected report bytes identical to accepted parent")
for name in sorted(report):
    ck(cols(report[name]) == cols(preport[name]) and
       rows(report[name]) == rows(preport[name]),
       f"all parsed native report rows equal parent {name}")
for name in ("SystemResults", "StockTotalResults"):
    ck(len(rows(report[name])) == 72, f"72 {name} half-hour bins")
    cc = cols(report[name])
    for i, row in enumerate(rows(report[name])):
        near(row[cc.index("STINT")], i/2, f"{name} bin {i} start")
        near(row[cc.index("ETINT")], (i+1)/2, f"{name} bin {i} end")
        for col, value in zip(cc, row):
            ck(value == rows(preport[name])[i][cc.index(col)],
               f"parent equal {name} bin {i} {col}")
system, stock = report["SystemResults"], report["StockTotalResults"]
sc, tc = cols(system), cols(stock)
sr, st = rows(system), rows(stock)
near(sum((r[sc.index("NSYWI")] or 0)/2 for r in sr), 4,
     "unchanged aircraft item-wait hours")
near(sum((r[tc.index("NBO")] or 0)/2 for r in st), 4.1666667,
     "unchanged base backorder hours")
near(sr[-1][sc.index("NSYRY")], 1, "terminal one aircraft ready")
near(sr[-1][sc.index("NSYWI")], 0, "terminal no item wait")
near(st[-1][tc.index("NBO")], 0, "terminal no backorder")
summary = dict(zip(cols(report["ResultSummary"]), rows(report["ResultSummary"])[0]))
near(summary["NREP"], 1, "one replication")
near(summary["MSUF"], 2/3, "two successful missions of three")

verdict = {
    "case": "J09.var02 depot item repair TAT scale v1.0.0",
    "passed": not failures,
    "verdict": "GO: bounded one-to-two-hour depot DIRP" if not failures else "NO-GO",
    "checks_passed": checks-len(failures), "checks_total": checks,
    "failures": failures,
    "native_closure_sha256": sha(RUN / "closure.json"),
    "native_report_sha256": sha(RUN / "report-raw.json"),
    "parent_closure_sha256": sha(PRUN / "closure.json"),
    "limits": [
        "One seed, one repairable depot LRU, SCRPT=2 and a 36-hour horizon.",
        "Failed LRU1 repair and stock return shift one hour; separately stocked spare0 arrives at base on the unchanged route.",
        "Selected System/Stock reports and aircraft readiness do not expose the depot item-repair timing difference; the native event log does.",
        "Ten optional native ScaleFactors columns are null; all six authored values are preserved.",
        "No system SURP scaling, other repair class, other scale factor, population law or cross-engine claim.",
    ],
}
OUT.write_bytes((json.dumps(verdict, indent=2, sort_keys=True)+"\n").encode("utf-8"))
print(json.dumps({"passed": verdict["passed"], "checks": checks,
                  "failures": failures[:20], "script_sha256": sha(Path(__file__)),
                  "verdict_sha256": sha(OUT)}, sort_keys=True))
raise SystemExit(0 if verdict["passed"] else 1)
