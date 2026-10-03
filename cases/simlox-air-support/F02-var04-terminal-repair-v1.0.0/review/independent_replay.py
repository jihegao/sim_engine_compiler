"""Independent read-only replay of F02.var04 terminal active-removal evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
ROOT = CASE.parent
PARENT = ROOT / "F02-var01-var02-integrated-fleet-v1.0.2"
PRUN = PARENT / "runs/f02-pair-v102-risk-ssh-20261004-01"
SIBLING = ROOT / "F02-var04-terminal-active-v1.0.2"
SRUN = SIBLING / "runs/f02-var04-terminal-v102-ssh-20261004-01"
RUN = CASE / "runs/f02-var04-active-repair-v100-ssh-20261004-01"
OUT = CASE / "review/independent-verdict.json"
count = 0
failures: list[str] = []


def ck(value, label):
    global count
    count += 1
    if not value:
        failures.append(label)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def obj(path):
    return json.loads(re.sub(r",\s*([}\]])", r"\1",
                             path.read_text(encoding="utf-8-sig")))


def tabs(doc, root):
    return {t["name"]: t for t in doc[root]["tables"]}


def cols(t):
    return [c["name"] for c in t["columns"]]


def data(t):
    return [r for x in t["instances"] for r in x["rows"]]


def near(value, expected, label, tol=.00035):
    if value is None and expected == 0:
        value = 0
    ck(isinstance(value, (int, float)) and abs(value - expected) <= tol,
       f"{label}: {value} vs {expected}")


def occupancy(a, b, intervals):
    return sum(max(0, min(b, stop) - max(a, start)) / (b-a)
               for start, stop in intervals)


def event(lines, time, phrase):
    ck(any((m := re.match(r"Time: ([\d.e+\-]+) (.*)", s))
           and abs(float(m[1]) - time) < .00012 and phrase in m[2]
           for s in lines), f"event at {time}: {phrase}")


contract = obj(CASE / "contract.json")
diff = obj(CASE / "exact-diff.json")
closure = obj(RUN / "closure.json")
inv = obj(RUN / "invocation.json")
steps = obj(RUN / "steps.json")
source = CASE / "repair-input.json"
parent_source = PARENT / "risk-input.json"
files = {
    "input": source, "parent": parent_source,
    "parent_closure": PRUN / "closure.json",
    "parent_evidence_index": PARENT / "evidence-index.json",
    "sibling_index": SIBLING / "evidence-index.json",
    "sibling_closure": SRUN / "closure.json",
    "contract": CASE / "contract.json", "exact_diff": CASE / "exact-diff.json",
    "build.py": CASE / "build.py", "describe_diff.py": CASE / "describe_diff.py",
    "check_roundtrip.py": CASE / "check_roundtrip.py",
    "run_native_ssh.ps1": CASE / "run_native_ssh.ps1",
}
ck(closure["source_hashes_before"] == closure["source_hashes_after"],
   "no frozen source changed across run")
ck(inv["source_hashes_before"] == closure["source_hashes_before"],
   "invocation/closure source pins agree")
for key, path in sorted(files.items()):
    ck(path.is_file(), f"source present {key}")
    if path.is_file():
        ck(sha(path) == closure["source_hashes_before"][key],
           f"source seal {key}")
ck(sha(source) == contract["repair_input_sha256"], "contract input pin")
ck(sha(parent_source) == contract["accepted_parent"]["input_sha256"],
   "contract parent input pin")
ck(sha(CASE / "exact-diff.json") == contract["exact_diff_sha256"],
   "contract diff pin")
ck(sha(SRUN / "closure.json") == contract["accepted_sibling"]["native_closure_sha256"],
   "accepted in-transit sibling closure")
ck(sha(RUN / "input.json") == sha(source), "native source byte copy")
ck(sha(RUN / "invocation.json") == closure["invocation_sha256"],
   "invocation hash")
ck(closure["error"] is None and closure["run_id"] == RUN.name,
   "successful native closure")
ck(len(closure["raw"]) == 12, "twelve sealed raw artifacts")
for name, seal in sorted(closure["raw"].items()):
    path = RUN / name
    ck(path.is_file(), f"raw present {name}")
    if path.is_file():
        ck(path.stat().st_size == seal["bytes"], f"raw length {name}")
        ck(sha(path) == seal["sha256"], f"raw hash {name}")
ck(inv["session_id"] == 0 and "sshd.exe" in inv["ssh_ancestor_names"],
   "guarded SSH session zero")
ck(inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "host mutex")
ck(inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1,
   "separate GUI identity")
ck([s["name"] for s in steps] ==
   ["import", "export", "calc", "jsonreport", "check_import_export"],
   "five guarded steps")
for step in steps:
    ck(step["status"] == "completed" and step["exit_code"] == 0,
       f"step {step['name']}")
for step in steps[:4]:
    ck(step["gui_preserved"] is True, f"GUI preserved {step['name']}")

parent = tabs(obj(parent_source), "model")
child = tabs(obj(source), "model")
export = tabs(obj(RUN / "roundtrip-raw.json"), "model")
ck(diff["parent_input_sha256"] == sha(parent_source), "diff parent seal")
ck(diff["terminal_input_sha256"] == sha(source), "diff child seal")
changes = []
for name in sorted(set(parent) | set(child)):
    a, b = parent.get(name), child.get(name)
    ck(a is not None and b is not None, f"retained table {name}")
    if a is None or b is None:
        continue
    ck(cols(a) == cols(b), f"source schema {name}")
    ck(len(data(a)) == len(data(b)), f"source cardinality {name}")
    for row_number, (before, after) in enumerate(zip(data(a), data(b))):
        for col, x, y in zip(cols(a), before, after):
            if x != y:
                changes.append((name, row_number, col, x, y))
ck(changes == [
    ("SystemRepair", 0, "SURPT", .5, 15.333333333333334),
    ("TaskBreakDown", 1, "DURN", 1/6, 15),
], "only matched system/removal duration cells changed")
ck(diff["changed_cells"] == [
    {"table": "SystemRepair", "instance": 0, "row": 0,
     "column": "SURPT", "before": .5, "after": 15.333333333333334},
    {"table": "TaskBreakDown", "instance": 0, "row": 1,
     "column": "DURN", "before": 1/6, "after": 15.0},
], "declared exact source diff")
authored = sorted(name for name in child if data(child[name]))
ck(len(authored) == 30, "thirty row-containing business tables")
for name in authored:
    ck(name in export, f"export contains {name}")
    if name not in export:
        continue
    ac, ec = cols(child[name]), cols(export[name])
    ck(all(c in ec for c in ac), f"native authored columns {name}")
    if all(c in ec for c in ac):
        ck([[r[ec.index(c)] for c in ac] for r in data(export[name])] ==
           data(child[name]), f"exact authored roundtrip {name}")
runlog = (RUN / "run.log").read_text(encoding="utf-8-sig")
ck("Errors: 0, Warnings: 1, Notes: 0" in runlog, "zero converter errors")
ck(set(re.findall(r"\((?:warning|notice|error) #(\d+)\)", runlog)) == {"108"},
   "only reviewed warning #108")
ck((RUN / "model.sxo").stat().st_size > 4, "valid nonempty SXO")

lines = (RUN / "model.log").read_text(encoding="utf-8-sig").splitlines()
for time, phrase in [
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
    (47.9896, "transport task 0 starts with 1 items/systems, transport time: 2"),
    (47.9896, "<P-MAINT at <BASE-01,0>> allocated to maintenance task"),
    (47.9896, "remove subitem subtask 14 seqno 1 within system SURP task 14 on <TEACH-AIR-01,0> starts performing, planned to last for 15 hours"),
    (49.9896, "transport task 0 arrives with 1 items/systems"),
    (49.9896, "<TEACH-LRU-01,0,BASE-01,0> Backorder removed, waiting time was 2"),
    (49.9896, "system SURP task 14 on <TEACH-AIR-01,0> subitem received <TEACH-LRU-01,0,2>"),
    (50.25, "<BASIC-MISSION,TEACH-UNIT,0,0,3> mission cancelled"),
    (53.5, "system PM task 17 on <TEACH-AIR-01,0> PMID: CAL24"),
    (54.5, "system PM task 18 on <TEACH-AIR-01,1> PMID: CAL24"),
    (54.5, "subtask 18 seqno 1 within system PM task 18 on <TEACH-AIR-01,1> resource availability test"),
]:
    event(lines, time, phrase)
ck(any("subitem failed: <TEACH-LRU-01,0,4>" in s for s in lines),
   "same physical failed LRU4")
ck(not any("transport task 2 starts" in s or "<TEACH-LRU-01,0,4>," in s and
           "transport request" in s for s in lines), "failed LRU4 not sent outbound")
ck(not any("remove subitem subtask 14" in s and "completed" in s for s in lines),
   "long removal work unfinished")
ck(not any("fit subitem subtask" in s and "starts performing" in s for s in lines),
   "no fit work before cutoff")
ck(not any(re.match(r"Time: [\d.e+\-]+  system SURP task 14 on <TEACH-AIR-01,0> completed$", s)
           for s in lines), "aircraft SURP unfinished")
ck(not any("item SURP task" in s or "item DIRP task" in s for s in lines),
   "failed LRU never reaches depot repair")
ck(not any("system PM task 18" in s and "completed" in s for s in lines),
   "second-day PM waits for worker")

# Reconstruct the worker leases; the final removal lease is intentionally open.
leases = []
open_lease = {"P-MAINT": None, "P-CREW": None}
for line in lines:
    m = re.match(r"Time: ([\d.e+\-]+)  <(P-MAINT|P-CREW) at <BASE-01,0>> "
                 r"(allocated to maintenance task|deallocated from  maintenance task)", line)
    if not m:
        continue
    time, kind, action = float(m[1]), m[2], m[3]
    if action.startswith("allocated"):
        ck(open_lease[kind] is None, f"no double booking {kind} {time}")
        open_lease[kind] = time
    else:
        ck(open_lease[kind] is not None, f"worker was booked {kind} {time}")
        if open_lease[kind] is not None:
            leases.append((open_lease[kind], time, kind))
        open_lease[kind] = None
ck(open_lease["P-MAINT"] is not None and
   abs(open_lease["P-MAINT"] - 47.9896) < .00012,
   "maintainer continuously booked beyond horizon")
ck(open_lease["P-CREW"] is None, "crew released before horizon")
leases.append((open_lease["P-MAINT"], 60, "P-MAINT"))

report = tabs(obj(RUN / "report-raw.json"), "report")
preport = tabs(obj(PRUN / "report-raw.json"), "report")
ck(set(report) == set(preport), "same report table set as accepted parent")
ck(data(report["ResultSummary"]) == data(preport["ResultSummary"]),
   "mission summary equality")
for name in ("SystemResults", "StockTotalResults", "ResourceResults"):
    ck(len(data(report[name])) == 120, f"120 {name} half-hour bins")
    ck(cols(report[name]) == cols(preport[name]), f"same {name} schema")
system, stock, resource = (report[n] for n in
                           ("SystemResults", "StockTotalResults", "ResourceResults"))
psystem, pstock, presource = (preport[n] for n in
                              ("SystemResults", "StockTotalResults", "ResourceResults"))
sc, tc, rc = map(cols, (system, stock, resource))
sr, st, rr = map(data, (system, stock, resource))
ps, pt, pr = map(data, (psystem, pstock, presource))
ck(st == pt, "every stock row equals parent: two-hour BO clears")
system_dynamic = {"NSYRY", "NSYUA", "NSYA", "NSYRP", "NSYPM", "NSYWI",
                  "NREPT", "NPMT", "SYDT", "NSYDT"}
resource_dynamic = {"NRUM", "NRW"}
for i in range(120):
    a, b = i/2, (i+1)/2
    sm, tm, rm = (dict(zip(c, row)) for c, row in
                  ((sc, sr[i]), (tc, st[i]), (rc, rr[i])))
    psm, prm = (dict(zip(c, row)) for c, row in ((sc, ps[i]), (rc, pr[i])))
    for name, row in (("system", sm), ("stock", tm), ("resource", rm)):
        near(row["STINT"], a, f"{name} start bin {i}")
        near(row["ETINT"], b, f"{name} end bin {i}")
    for col in sc:
        if col in system_dynamic or col in ("UNID", "SID", "STINT", "ETINT"):
            continue
        if isinstance(sm[col], (int, float)) or isinstance(psm[col], (int, float)):
            near(sm[col], psm[col] or 0, f"unchanged system {col} bin {i}")
        else:
            ck(sm[col] == psm[col], f"unchanged system {col} bin {i}")
    for col in rc:
        if col in resource_dynamic or col in ("RID", "STID", "STINT", "ETINT"):
            continue
        if isinstance(rm[col], (int, float)) or isinstance(prm[col], (int, float)):
            near(rm[col], prm[col] or 0, f"unchanged resource {col} bin {i}")
        else:
            ck(rm[col] == prm[col], f"unchanged resource {col} bin {i}")
    for col in tc:
        if col in ("STINT", "ETINT"):
            continue
        ck(tm[col] == pt[i][tc.index(col)], f"stock {col} parity bin {i}")
    busy = sum(occupancy(a, b, [(start, end)]) for start, end, _ in leases)
    near(rm["NRUM"], busy, f"physical worker booking bin {i}")
    wait = occupancy(a, b, [(20.5, 21), (24.5, 25), (28.5, 29.5),
                            (44.5, 45), (54.5, 60)])
    near(rm["NRW"], wait, f"resource queue bin {i}")
    near(sm["NSYRP"], occupancy(a, b, [(47.9896, 60)]),
         f"actively repairing aircraft bin {i}")
    near(sm["NSYWI"], 0, f"no item wait after receipt bin {i}")
    pm = occupancy(a, b, [(28.5, 29.5), (29.5, 30.5)])
    near(sm["NSYPM"], pm, f"performed PM bin {i}")
    if i >= 100:
        ready = occupancy(a, b, [(51.25, 60)])
        unavailable = occupancy(a, b, [(47.9896, 60)])
        near(sm["NSYRY"], ready, f"ready aircraft bin {i}")
        near(sm["NSYUA"], unavailable, f"unavailable aircraft bin {i}")
        near(sm["NSYA"], 2 - unavailable, f"available aircraft bin {i}")
    else:
        for col in ("NSYRY", "NSYUA", "NSYA"):
            near(sm[col], psm[col] or 0, f"pre-arrival aircraft {col} bin {i}")
    for col in ("NREPT", "NPMT", "SYDT", "NSYDT"):
        if (col == "NREPT" and i == 100) or \
           (col == "NPMT" and i in (109, 111)) or \
           (col in ("SYDT", "NSYDT") and i in (95, 107, 109)):
            near(sm[col], 0, f"unfinished event marker {col} bin {i}")
        else:
            ck(sm[col] == psm[col], f"unchanged marker {col} bin {i}")

near(sum((r[rc.index("NRUM")] or 0) / 2 for r in rr),
     sum(end-start for start, end, _ in leases), "integrated worker hours")
near(sum((r[rc.index("NRW")] or 0) / 2 for r in rr), 8,
     "eight queued resource-hours")
near(sum((r[sc.index("NSYRP")] or 0) / 2 for r in sr), 60-47.9896,
     "active repair exposure through horizon")
near(sum((r[tc.index("NBO")] or 0) / 2 for r in st), 2,
     "stock backorder cleared after two hours")
for table, col, expected in ((system, "NSYRP", 1), (system, "NSYWI", 0),
                             (system, "NSYRY", 1), (stock, "NBO", 0),
                             (resource, "NRUM", 1), (resource, "NRW", 1)):
    near(data(table)[-1][cols(table).index(col)], expected, f"terminal {col}")
res_total = dict(zip(cols(report["ResourceResultsTotal"]),
                     data(report["ResourceResultsTotal"])[0]))
near(res_total["NR"], 2, "two resource persons")
near(res_total["NRW"], 8/60, "resource total waiting fraction")
near(res_total["NRUM"], sum(end-start for start, end, _ in leases)/60,
     "resource total utilization fraction")

verdict = {
    "case": "F02.var04 terminal active removal v1.0.0",
    "passed": not failures,
    "verdict": "GO: bounded active repair at h60" if not failures else "NO-GO",
    "checks_passed": count-len(failures), "checks_total": count,
    "failures": failures,
    "child_closure_sha256": sha(RUN / "closure.json"),
    "child_report_sha256": sha(RUN / "report-raw.json"),
    "parent_closure_sha256": sha(PRUN / "closure.json"),
    "limits": [
        "One seed, two aircraft, one base/depot route, one 15-hour removal and one 60-hour horizon.",
        "P-MAINT remains booked performing removal at h60, while a separate PM subtask waits for that worker; task creation alone is not performed work.",
        "The depot spare reaches the base and the open SURP receives it, but the failed installed LRU has not been physically removed or shipped.",
        "No stock reservation, post-horizon completion or generic scheduling rule is inferred.",
        "The accepted transit sibling is a separate source branch with an item-wait terminal state; it is not evidence of active removal work.",
    ],
}
OUT.write_bytes((json.dumps(verdict, indent=2, sort_keys=True) + "\n").encode("utf-8"))
print(json.dumps({"checks": count, "failures": failures[:20],
                  "passed": verdict["passed"], "script_sha256": sha(Path(__file__)),
                  "verdict_sha256": sha(OUT)}, sort_keys=True))
raise SystemExit(0 if verdict["passed"] else 1)
