"""Independent standard-library replay of sealed F01.var03 native evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
BASE = CASE.parent
RUN = CASE / "runs/f01-var03-explicit-v100-ssh-20261004-04"
OUT = CASE / "review/independent-verdict.json"
n = 0
bad = []


def test(value, label):
    global n
    n += 1
    if not value:
        bad.append(label)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(re.sub(r",\s*([}\]])", r"\1", path.read_text(encoding="utf-8-sig")))


def tables(doc, root="model"):
    return {t["name"]: t for t in doc[root]["tables"]}


def body(table):
    return [row for inst in table["instances"] for row in inst["rows"]]


def ev(time, phrase):
    test(any((m := re.match(r"^Time: ([\d.e+\-]+) (.*)$", line))
             and abs(float(m[1])-time) < .00011 and phrase in m[2] for line in events),
         f"event {time} {phrase}")


def eq(actual, expected, label, tolerance=.00025):
    if actual is None and expected == 0:
        actual = 0
    test(isinstance(actual,(int,float)) and abs(actual-expected) <= tolerance,
         f"{label}: expected {expected}, got {actual}")


def portion(a,b,segments):
    return sum(max(0,min(b,y)-max(a,x))/(b-a) for x,y in segments)


closure = load(RUN / "closure.json")
inv = load(RUN / "invocation.json")
steps = load(RUN / "steps.json")
parent_case = BASE / "F01-var01-two-three-level-v1.0.1"
d06 = BASE / "D06-explicit-position-direct-repair-v1.0.0"
pins = {
    "input": CASE / "explicit-input.json",
    "parent": parent_case / "three-level-input.json",
    "parent_closure": parent_case / "runs/f01-var01-three-v101-ssh-20261004-01/closure.json",
    "parent_evidence_index": parent_case / "evidence-index.json",
    "explicit_reference": d06 / "native-input.json",
    "explicit_reference_closure": d06 / "runs/d06-position-cm-v100-ssh-20260930-02/closure.json",
    "contract": CASE / "contract.json",
    "exact_diff": CASE / "exact-diff.json",
    "build.py": CASE / "build.py",
    "describe_diff.py": CASE / "describe_diff.py",
    "check_roundtrip.py": CASE / "check_roundtrip.py",
    "run_native_ssh.ps1": CASE / "run_native_ssh.ps1",
}
test(closure["source_hashes_before"] == closure["source_hashes_after"], "stable run source pins")
test(inv["source_hashes_before"] == closure["source_hashes_before"], "invocation source pins")
for key,path in sorted(pins.items()):
    test(path.is_file(), f"pin exists {key}")
    if path.is_file():
        test(digest(path) == closure["source_hashes_before"][key], f"pin SHA {key}")
test(digest(RUN / "input.json") == digest(CASE / "explicit-input.json"), "native input copied unchanged")
test(digest(RUN / "invocation.json") == closure["invocation_sha256"], "invocation SHA")
test(len(closure["raw"]) == 12, "12 sealed raw files")
for name,meta in sorted(closure["raw"].items()):
    path = RUN / name
    test(path.exists(), f"raw exists {name}")
    if path.exists():
        test(path.stat().st_size == meta["bytes"], f"raw size {name}")
        test(digest(path) == meta["sha256"], f"raw SHA {name}")
test(closure["error"] is None and closure["run_id"] == RUN.name, "run closed cleanly")
test(inv["session_id"] == 0 and inv["execution_mode"] == "ssh_cli_v1", "SSH session zero")
test("sshd.exe" in inv["ssh_ancestor_names"], "sshd ancestor")
test(inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "native queue mutex")
test(inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, "preserved separate GUI")
test([s["name"] for s in steps] ==
     ["import","export","calc","jsonreport","check_import_export"], "guarded step order")
for step in steps:
    test(step["status"] == "completed" and step["exit_code"] == 0 and
         step.get("gui_preserved", True),
         f"step {step['name']}")
for step in steps[:4]:
    test(step["gui_preserved"] is True, f"native GUI guard {step['name']}")

parent = tables(load(pins["parent"]))
source = tables(load(pins["input"]))
roundtrip = tables(load(RUN / "roundtrip-raw.json"))
diff = load(pins["exact_diff"])
test(diff["traditional_input_sha256"] == digest(pins["parent"]), "diff parent digest")
test(diff["explicit_input_sha256"] == digest(pins["input"]), "diff child digest")
changed = sorted(k for k in set(parent)|set(source) if parent.get(k) != source.get(k))
test(changed == sorted(x["table"] for x in diff["changed_tables"]), "exact changed table set")
for change in diff["changed_tables"]:
    key = change["table"]
    test(parent.get(key) == change["before"], f"diff before {key}")
    test(source.get(key) == change["after"], f"diff after {key}")
def mapped(name):
    cols=[c["name"] for c in source[name]["columns"]]
    return [dict(zip(cols,row)) for row in body(source[name])]

test(mapped("FailureMode") == [{"FMID":"FM-SRU","DESCR":"Nested SRU failure",
    "MID":"TEACH-SRU-01","FRQ":1200000.0,"OPID":"OPHOURS","CRITF":1.0,
    "NCFTL":None,"NCFTT":None,"NOTE":None}], "single SRU FM source row")
test([(r["ID"],r["STID"],r["CMT"]) for r in mapped("CMLocation")] ==
     [("TEACH-AIR-01","BASE-01",.5),("TEACH-LRU-01","BASE-01",.75),
      ("TEACH-SRU-01","BASE-01",1)], "three local CM levels")
test([(r["MID"],r["IID"],r["CMRF"],r["CMRQ"]) for r in mapped("CMReplacement")] ==
     [("TEACH-AIR-01","TEACH-LRU-01",1,1),
      ("TEACH-LRU-01","TEACH-SRU-01",1,1)], "two nested CM replacement links")
test([(r["MID"],r["MMID"],r["QTYPM"]) for r in mapped("MaterielStructure")] ==
     [("TEACH-LRU-01","TEACH-AIR-01",1),("TEACH-SRU-01","TEACH-LRU-01",1)],
     "two physical materiel links")
test(all(r["FRT"] is None for r in mapped("Item")+mapped("System")),
     "traditional failure rates cleared")
test(len([k for k in source if body(source[k])]) == 21, "21 populated authored tables")
for key in sorted(k for k in source if body(source[k])):
    test(key in roundtrip, f"export table {key}")
    if key in roundtrip:
        original_columns = [c["name"] for c in source[key]["columns"]]
        export_columns = [c["name"] for c in roundtrip[key]["columns"]]
        test(all(c in export_columns for c in original_columns), f"export columns {key}")
        if all(c in export_columns for c in original_columns):
            projected = [[row[export_columns.index(c)] for c in original_columns]
                         for row in body(roundtrip[key])]
            test(projected == body(source[key]), f"export exact rows {key}")
runlog = (RUN / "run.log").read_text(encoding="utf-8-sig")
test("Errors: 0, Warnings: 1, Notes: 0" in runlog, "converter counts")
test(len(re.findall(r"\(warning #108\)", runlog)) == 1, "warning 108 only")
test(set(re.findall(r"\((?:warning|notice|error) #(\d+)\)",runlog)) == {"108"},
     "exact converter message set")
test((RUN / "model.sxo").stat().st_size > 4, "usable SXO")

events = (RUN / "model.log").read_text(encoding="utf-8-sig").splitlines()
test(len(events) >= 290, "substantive event log")
test(sum("Failure Mode: FM-SRU on materiel: <TEACH-SRU-01,0>" in s for s in events) == 6,
     "three FM-SRU failures shown at failure and return")
test(not any("books resources" in s for s in events), "no resource bookings")
test(sum("requests resources: no resources needed" in s for s in events) == 15,
     "15 repair subtasks each request no resources")
for typ, physical in [("LRU",1),("SRU",0)]:
    test(any(f"Stock at: <TEACH-{typ}-01,0,BASE-01,0> Level: 1 Items:<TEACH-{typ}-01,0,{physical}>"
             in s for s in events),f"opening {typ} stock identity")

cycles = [
    (0,7,8,8.47072,8.94145,9.44145,9.10812,9.48312,9.85812,10.4831,2,1,3,0,0),
    (1,19,20,21.3995,21.8995,22.3995,22.0662,22.4412,22.8162,23.4412,4,2,5,3,3),
    (2,31,32,32.953,33.453,33.953,33.6197,33.9947,34.3697,34.9947,6,4,7,5,6),
]
for mid,order,launch,fail,return_time,system_end,lru_start,sru_start,lru_end,sru_end,lru,spare_lru,sru,spare_sru,task in cycles:
    ident = f"<BASIC-MISSION,TEACH-UNIT,0,0,{mid}>"
    lru_id = f"<TEACH-LRU-01,0,{lru}>"
    sru_id = f"<TEACH-SRU-01,0,{sru}>"
    ev(order, ident+" mission created")
    ev(order, ident+" mission allocates system: <TEACH-AIR-01,0>")
    ev(launch, ident+" mission starting, duration: 2")
    ev(fail, "critical CM failure mode added")
    ev(fail, ident+" mission aborted")
    ev(return_time, ident+" aborted mission completed")
    ev(return_time, f"system CM task {task} on <TEACH-AIR-01,0> started")
    ev(return_time, f"system CM task {task} on <TEACH-AIR-01,0> FMID: FM-SRU")
    ev(return_time, f"Take replacement item <TEACH-LRU-01,0,{spare_lru}> from stock")
    ev(system_end, f"system CM task {task} on <TEACH-AIR-01,0> completed")
    ev(system_end, "System ready <TEACH-AIR-01,0>")
    ev(lru_start, f"item CM task {task+1} on {lru_id} started")
    ev(lru_start, f"Take replacement item <TEACH-SRU-01,0,{spare_sru}> from stock")
    ev(lru_end, f"item CM task {task+1} on {lru_id} completed")
    ev(lru_end, f"Put back replacement item {lru_id} to stock")
    ev(sru_start, f"item CM task {task+2} on {sru_id} started")
    ev(sru_end, f"item CM task {task+2} on {sru_id} completed")
    ev(sru_end, f"Put back replacement item {sru_id} to stock")
    eq(system_end-return_time,.5,f"system task duration {task}")
    eq(lru_end-lru_start,.75,f"LRU task duration {task+1}")
    eq(sru_end-sru_start,1,f"SRU task duration {task+2}")
test(not any("Backorder added" in s for s in events), "no event-log backorders")
test(not any("transport task" in s for s in events), "local route no transport")
test(not any(" mission successful" in s for s in events), "no successful missions")
test(any("Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,6>" in s
         for s in events), "terminal physical LRU6 on hand")
test(any("Stock at: <TEACH-SRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-SRU-01,0,7>" in s
         for s in events), "terminal physical SRU7 on hand")

report = tables(load(RUN / "report-raw.json"),"report")
test(set(report) == {"ProblemDescription","ResultSummary","SystemResults","StockTotalResults"},
     "report table set")
test(body(report["ProblemDescription"]) == body(source["ProblemDescription"]),
     "description matches source")
summary = dict(zip([c["name"] for c in report["ResultSummary"]["columns"]],
                   body(report["ResultSummary"])[0]))
for col,value in {"NREP":1,"RTILW":0,"RTIUP":36,"MSTF":1,"MSUF":0}.items():
    eq(summary[col],value,f"summary {col}")
eq(summary["MTMF"],.7156733274459839,"summary MTMF",.00001)
sys = report["SystemResults"]
stock = report["StockTotalResults"]
sc = [c["name"] for c in sys["columns"]]
tc = [c["name"] for c in stock["columns"]]
sr,tr = body(sys),body(stock)
test(len(sr) == len(tr) == 72, "72 aligned System/Stock bins")
active=[(7,8.94145),(19,21.8995),(31,33.453)]
flight=[(8,8.94145),(20,21.8995),(32,33.453)]
reserve=[(7,8),(19,20),(31,32)]
unready=[(8.94145,9.44145),(21.8995,22.3995),(33.453,33.953)]
fail_bins={16,42,65}
start_bins={17,43,66}
done_bins={18,44,67}
for i,(srow,trow) in enumerate(zip(sr,tr)):
    a,b=.5*i,.5*(i+1)
    sm=dict(zip(sc,srow))
    tm=dict(zip(tc,trow))
    for field in ("STINT","ETINT"):
        eq(sm[field],a if field=="STINT" else b,f"system {i} {field}")
        eq(tm[field],a if field=="STINT" else b,f"stock {i} {field}")
    ma,mo,mr,ua=(portion(a,b,x) for x in (active,flight,reserve,unready))
    sexpected={"NSYRY":1-ma-ua,"NSYMA":ma,"NSYMO":mo,"NSYMR":mr,
               "NSYUA":ua,"NSYA":1-ua,"FTMO":mo,"NSYRP":ua,"STACC":mo,
               "NREPT":int(i in done_bins),"NFAIL":int(i in fail_bins),
               "SYDT":.5 if i in start_bins else 0,"NSYDT":int(i in start_bins)}
    for col in sc:
        if col not in ("UNID","SID","STINT","ETINT"):
            eq(sm[col],sexpected.get(col,0),f"system bin {i} {col}")
    texpected={"PNB":1,"NDF":int(i in start_bins),"NWT":int(i in start_bins)}
    for col in tc:
        if col not in ("STINT","ETINT"):
            eq(tm[col],texpected.get(col,0),f"stock bin {i} {col}")
eq(sum((row[sc.index("STACC")] or 0)*.5 for row in sr),
   sum(y-x for x,y in flight),"aircraft operating-hour integral")
eq(sum((row[sc.index("SYDT")] or 0) for row in sr),1.5,"system repair-hour integral")
eq(sr[-1][sc.index("NSYRY")],1,"terminal aircraft ready")
eq(tr[-1][tc.index("NBO")],0,"terminal no aggregate backorder")

verdict={
    "case":"F01.var03 traditional versus explicit CM v1.0.0",
    "run_id":RUN.name,
    "passed":not bad,
    "verdict":"GO: bounded explicit nested CM observation" if not bad else "NO-GO",
    "checks_passed":n-len(bad),"checks_total":n,"failures":bad,
    "closure_sha256":digest(RUN/"closure.json"),
    "report_sha256":digest(RUN/"report-raw.json"),
    "limits":[
        "One seed, one aircraft, one FM-SRU, one LRU/SRU chain and one local BASE-01 repair route.",
        "Physical topology and task meaning can be compared with accepted traditional F01.var01; seeded failure times differ, so outcome-time parity is not claimed.",
        "No resource shortage or backorder occurred; task requests explicitly say no resources needed.",
        "No general nested-CM, other failure-mode, GUI-only or cross-engine inference.",
    ]
}
OUT.write_bytes((json.dumps(verdict,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode("utf-8"))
print(json.dumps({"passed":verdict["passed"],"checks":n,"failures":bad[:20],
                  "script_sha256":digest(Path(__file__)),"verdict_sha256":digest(OUT)},sort_keys=True))
raise SystemExit(0 if verdict["passed"] else 1)
