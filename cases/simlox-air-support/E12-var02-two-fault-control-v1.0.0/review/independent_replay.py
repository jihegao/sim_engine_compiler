"""Independent, read-only replay of E12.var02 individual-repair control."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
PARENT = CASE.parent / "E12-var01-explicit-two-bases-v1.0.0"
RUN = CASE / "runs" / "e12-var02-two-fault-control-v100-ssh-20261003-01"
PRUN = PARENT / "runs" / "e12-var01-explicit-bases-v100-ssh-20261003-01"
OUT = Path(__file__).with_name("independent-verdict.json")

class Audit:
    def __init__(self):
        self.passed = 0
        self.failures = []
    def check(self, truth, label):
        if truth:
            self.passed += 1
        else:
            self.failures.append(label)
    def eq(self, value, expected, label):
        self.check(value == expected, f"{label}: expected {expected!r}, got {value!r}")
    def near(self, value, expected, label, tolerance=0.0002):
        self.check(value is not None and abs(value-expected) <= tolerance, f"{label}: expected {expected!r}, got {value!r}")

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def obj(path, native=False):
    text = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", text) if native else text)

def tables(path, root="model"):
    return {t["name"]: t for t in obj(path, root == "report")[root]["tables"]}

def rows(table):
    return [row for instance in table["instances"] for row in instance.get("rows", [])]

def records(table):
    cols = [c["name"] for c in table["columns"]]
    return [dict(zip(cols, row)) for row in rows(table)]

def overlap(start, end, lo, hi):
    return max(0.0, min(end, hi)-max(start, lo))

def main():
    a = Audit()
    contract = obj(CASE / "contract.json")
    diff = obj(CASE / "exact-diff.json")
    source = tables(CASE / "native-input.json")
    parent = tables(PARENT / "native-input.json")
    exported = tables(RUN / "roundtrip-raw.json")
    report = tables(RUN / "report-raw.json", "report")
    inv = obj(RUN / "invocation.json")
    closure = obj(RUN / "closure.json")
    steps = obj(RUN / "steps.json")
    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace").replace("\r\n", "\n")
    converter = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")

    a.eq(contract["variant_id"], "E12.var02", "contract variant")
    a.eq(sha(CASE / "native-input.json"), contract["native_input_sha256"], "input pin")
    a.eq(sha(CASE / "exact-diff.json"), contract["exact_diff_sha256"], "diff pin")
    a.eq(sha(PARENT / "native-input.json"), contract["accepted_parent"]["input_sha256"], "parent input pin")
    a.eq(sha(PRUN / "closure.json"), contract["accepted_parent"]["native_closure_sha256"], "parent closure pin")
    a.eq(sha(PARENT / "evidence-index.json"), contract["accepted_parent"]["evidence_index_sha256"], "parent index pin")
    a.eq(diff["parent_sha256"], sha(PARENT / "native-input.json"), "diff parent")
    a.eq(diff["source_sha256"], sha(CASE / "native-input.json"), "diff child")
    a.eq(len(source), 32, "32 source tables")
    a.eq(set(source), set(parent), "same table set")
    changed = sorted(name for name in source if source[name] != parent[name])
    a.eq(changed, diff["changed_tables"], "exact two-table source delta")
    a.eq(len(changed), 2, "two changed tables")
    for name in sorted(source):
        a.eq(source[name]["columns"], parent[name]["columns"], f"schema {name}")
        if name not in changed:
            a.eq(source[name], parent[name], f"unchanged table {name}")
    a.eq(len(diff["changes"]), 2, "two changed cells")
    for change in diff["changes"]:
        name = change["table"]
        p, c = rows(parent[name]), rows(source[name])
        col = next(i for i, field in enumerate(source[name]["columns"]) if field["name"] == change["column"])
        a.eq(p[change["row"]][col], change["before"], f"parent {name}.{change['column']}")
        a.eq(c[change["row"]][col], change["after"], f"child {name}.{change['column']}")
        actual = [(i, j) for i, (pr, cr) in enumerate(zip(p, c)) for j, (x, y) in enumerate(zip(pr, cr)) if x != y]
        a.eq(actual, [(change["row"], col)], f"only {name}.{change['column']} changes")
    a.eq(records(source["MissionType"])[0]["DURN"], 3.5, "3.5-hour mission duration")
    a.eq([(r["STID"], r["SURPT"]) for r in records(source["SystemRepair"])], [("BASE-01", .5), ("BASE-02", .5)], "individual half-hour SystemRepair rows")

    installed = {"simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"), "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"), "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")}
    for key, path in installed.items():
        field = {"simlox_exe": "simlox_exe_sha256", "manual": "manual_pdf_sha256", "dictionary": "dictionary_sha256"}[key]
        a.eq(sha(path), contract["source"][field], f"installed {key} pin")
    a.eq(inv["run_id"], RUN.name, "run ID")
    a.eq(inv["execution_mode"], "ssh_cli_v1", "SSH CLI")
    a.eq(inv["session_id"], 0, "session zero")
    a.check(inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"], "SSH ancestry")
    a.eq(inv["queue_mutex"], r"Global\SimloxIssue18NativeQueue", "mutex")
    a.eq((inv["gui"]["pid"], inv["gui"]["session_id"]), (13340, 1), "GUI preserved identity")
    a.eq(inv["input_sha256"], sha(CASE / "native-input.json"), "invocation input")
    a.eq(closure["invocation_sha256"], sha(RUN / "invocation.json"), "invocation seal")
    a.eq(closure["source_hashes_before"], closure["source_hashes_after"], "source stable")
    a.eq(closure["source_hashes_before"], inv["source_hashes_before"], "invocation source agreement")
    paths = {"input": CASE / "native-input.json", "parent": PARENT / "native-input.json", "parent_closure": PRUN / "closure.json", "parent_index": PARENT / "evidence-index.json", "contract": CASE / "contract.json", "exact_diff": CASE / "exact-diff.json", "builder": CASE / "build.py", "diff_builder": CASE / "describe_diff.py", "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1", "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"), **installed}
    for key, path in sorted(paths.items()):
        a.eq(closure["source_hashes_before"][key], sha(path), f"source seal {key}")
    a.eq(len(closure["raw"]), 12, "12 raw seals")
    for name, meta in sorted(closure["raw"].items()):
        path = RUN / name
        a.check(path.is_file(), f"raw exists {name}")
        if path.is_file():
            a.eq(path.stat().st_size, meta["bytes"], f"raw bytes {name}")
            a.eq(sha(path), meta["sha256"], f"raw SHA {name}")
    a.eq(sha(RUN / "input.json"), sha(CASE / "native-input.json"), "run input copy")
    a.eq([s["name"] for s in steps], ["import", "export", "calc", "jsonreport", "check_import_export"], "five guarded steps")
    for step in steps:
        a.eq(step["exit_code"], 0, f"{step['name']} exit")
        a.eq(step["status"], "completed", f"{step['name']} completed")
        a.eq(step["error"], None, f"{step['name']} no error")
        a.check(step["gui_preserved"] is True, f"{step['name']} GUI preserved")
    authored = sorted(name for name, table in source.items() if rows(table))
    a.eq(len(authored), 22, "22 authored row tables")
    a.eq(set(exported), set(source), "export table set")
    for name in authored:
        a.eq(exported[name], source[name], f"native exact roundtrip {name}")
    a.check((RUN / "model.sxo").stat().st_size > 4, "valid SXO")
    a.eq(re.findall(r"\(error #(\d+)\)", converter), [], "Errors0")
    a.eq(re.findall(r"\(warning #(\d+)\)", converter), ["108"], "warning108 only")
    a.check("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in converter, "converter summary")

    def event(hour, phrase):
        a.check(any(line.startswith(f"Time: {hour} ") and phrase in line for line in log.splitlines()), f"event h{hour} {phrase}")
    for base, unit, aircraft, spare in [("BASE-01", "TEACH-UNIT", 0, 1), ("BASE-02", "TEACH-UNIT-2", 1, 2)]:
        event("0", f"<{unit} at <{base},0>> systems ready: 1 :<TEACH-AIR-01,{aircraft}>")
        a.check(f"Time: 0 <TEACH-LRU-01,0,{base},0> Stock initiated \n  Stock at: <TEACH-LRU-01,0,{base},0> Level: 1 Items:<TEACH-LRU-01,0,{spare}>" in log, f"{base} opening spare ID{spare}")
    event("0", "<TEACH-LRU-01,0,DEPOT-01,0> Stock initiated")
    for mid in range(6):
        unit = "TEACH-UNIT" if mid % 2 == 0 else "TEACH-UNIT-2"
        aircraft = mid % 2
        ordered, started = (7, 8) if mid < 2 else (19, 20) if mid < 4 else (31, 32)
        ident = f"<BASIC-MISSION,{unit},0,0,{mid}>"
        event(str(ordered), f"{ident} mission created:")
        event(str(ordered), f"{ident} mission allocates system: <TEACH-AIR-01,{aircraft}>")
        event(str(started), f"{ident} mission starting, duration: 3.5 : <TEACH-AIR-01,{aircraft}>")
    for mid, hour in [(0, "9.8829"), (1, "11.1325"), (2, "22.5723"), (4, "34.7893")]:
        unit = "TEACH-UNIT" if mid % 2 == 0 else "TEACH-UNIT-2"
        event(hour, f"<BASIC-MISSION,{unit},0,0,{mid}> mission aborted:")
    for mid, hour in [(3, "23.5"), (5, "35.5")]:
        event(hour, f"<BASIC-MISSION,TEACH-UNIT-2,0,0,{mid}> mission success:")
    for phrase, count in [("mission created:",6), ("mission starting, duration:",6), ("mission aborted:",4), ("mission success:",2), ("mission cancelled:",0), ("critical random failure added",4)]:
        a.eq(log.count(phrase), count, f"event count {phrase}")
    for hour, aircraft, item in [("9.8829",0,3), ("11.1325",1,4), ("22.5723",0,5), ("34.7893",0,6)]:
        event(hour, f"<TEACH-AIR-01,{aircraft}> critical random failure added")
        a.check(f"subitem failed: <TEACH-LRU-01,0,{item}>" in log, f"failed physical item ID{item}")
    for start, finish, task, aircraft, base, spare in [("10.7579","11.2579",0,0,"BASE-01",1), ("11.5","12",1,1,"BASE-02",2), ("23.4473","23.9473",4,0,"BASE-01",0), ("35.5","36",6,0,"BASE-01",4)]:
        event(start, f"system SURP task {task} on <TEACH-AIR-01,{aircraft}> started")
        event(finish, f"system SURP task {task} on <TEACH-AIR-01,{aircraft}> completed")
        event(start, f"<TEACH-LRU-01,0,{base},0> Take replacement item <TEACH-LRU-01,0,{spare}> from stock")
    for hour, item, base in [("10.7579",0,"BASE-01"), ("14.9246",3,"BASE-02"), ("23.4473",4,"BASE-01"), ("35.5",5,"BASE-01")]:
        event(hour, f"transport request <<TEACH-LRU-01,0,{item}>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,{base},0>> started")
    for hour, item, base in [("10.9246",3,"BASE-01"), ("11.6667",4,"BASE-02"), ("23.614",5,"BASE-01"), ("35.6667",6,"BASE-01")]:
        event(hour, f"transport request <<TEACH-LRU-01,0,{item}>,<TEACH-LRU-01,0,{base},0>,<TEACH-LRU-01,0,DEPOT-01,0>> started")
    for start, finish, item in [("13.9246","14.9246",3), ("14.6667","15.6667",4), ("26.614","27.614",5)]:
        event(start, f"<TEACH-LRU-01,0,DEPOT-01,0> Start repair of item <TEACH-LRU-01,0,{item}>")
        event(finish, f"<TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item <TEACH-LRU-01,0,{item}>")
    event("11.5", "<TEACH-LRU-01,0,DEPOT-01,0> Backorder added")
    event("14.9246", "<TEACH-LRU-01,0,DEPOT-01,0> Backorder removed, waiting time was 3.42457")
    event("15.9246", "<TEACH-LRU-01,0,BASE-02,0> Put back replacement item <TEACH-LRU-01,0,3> to stock")
    event("24.4473", "<TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,4> to stock")
    event("27.614", "<TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-LRU-01,0,5> to stock")
    event("36", "<TEACH-UNIT at <BASE-01,0>> systems ready: 1 :<TEACH-AIR-01,0>")
    event("35.5", "<TEACH-UNIT-2 at <BASE-02,0>> systems ready: 1 :<TEACH-AIR-01,1>")
    a.check("Time: 15.9246 <TEACH-LRU-01,0,BASE-02,0> Put back replacement item <TEACH-LRU-01,0,3> to stock \n  Stock at: <TEACH-LRU-01,0,BASE-02,0> Level: 1 Items:<TEACH-LRU-01,0,3>" in log, "BASE-02 terminal spare ID3")
    a.check("Time: 35.5 <TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,4> from stock \n  Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 0 Items:" in log, "BASE-01 terminal on-hand zero")
    a.check("Time: 35.5 <TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,5> from stock \n  Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 0 Items:" in log, "depot terminal on-hand zero")
    a.eq(log.count("Finished repair of item <TEACH-LRU-01,0,6>"), 0, "last failed ID6 still in transit at horizon")
    a.eq(log.count("books resources"), 0, "no resource booking")

    a.eq(set(report), {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "report tables")
    summary = records(report["ResultSummary"])[0]
    a.eq(rows(report["ResultSummary"])[0], [1,0,36,0.9621521234512329,0,1,0,0.3333333432674408,0,0.9621521234512329,0], "complete ResultSummary row")
    s, t = records(report["SystemResults"]), records(report["StockTotalResults"])
    a.eq((len(s), len(t)), (72,72), "72 half-hour bins each")
    ready = [(0,7),(11.2579,19),(23.9473,31)]
    ready1 = [(0,7),(12,19),(23.5,31),(35.5,36)]
    missions0 = [(7,10.7579),(19,23.4473),(31,35.5)]
    missions1 = [(7,11.5),(19,23.5),(31,35.5)]
    flights0 = [(8,10.7579),(20,23.4473),(32,35.5)]
    flights1 = [(8,11.5),(20,23.5),(32,35.5)]
    repairs = [(10.7579,11.2579),(11.5,12),(23.4473,23.9473),(35.5,36)]
    failure_bins = {19,22,45,69}
    repair_start_bins = {21,23,46,71}
    repair_end_bins = {22,24,47}
    stock_demand_bins = {21,23,46,71}
    for i, (sr,tr) in enumerate(zip(s,t)):
        lo, hi = i/2, (i+1)/2
        a.eq((sr["STINT"],sr["ETINT"],tr["STINT"],tr["ETINT"]), (lo,hi,lo,hi), f"bin {i} interval")
        ready_value = 2*sum(overlap(x,y,lo,hi) for x,y in ready+ready1)
        mission_value = 2*sum(overlap(x,y,lo,hi) for x,y in missions0+missions1)
        flight_value = 2*sum(overlap(x,y,lo,hi) for x,y in flights0+flights1)
        unavailable = 2*sum(overlap(x,y,lo,hi) for x,y in repairs)
        expected = {k:0 for k in sr}
        expected.update(UNID="Total over all Units",SID="Total over all Systems",STINT=lo,ETINT=hi,NSYRY=ready_value,NSYMA=mission_value,NSYMO=flight_value,NSYMR=4*sum(overlap(x,x+1,lo,hi) for x in (7,19,31)),NSYUA=unavailable,NSYA=2-unavailable,FTMO=flight_value/2,NSYRP=unavailable,STACC=flight_value,NFAIL=int(i in failure_bins),NREPT=int(i in repair_end_bins),SYDT=.5 if i in repair_start_bins else None,NSYDT=int(i in repair_start_bins))
        for key,value in expected.items():
            if isinstance(value,float):
                a.near(sr[key],value,f"SystemResults bin {i} {key}")
            else:
                a.eq(sr[key],value,f"SystemResults bin {i} {key}")
        stock_expected = {k:0 for k in tr}
        stock_expected.update(STINT=lo,ETINT=hi,NBOU=None,ROS=0 if i in stock_demand_bins else None,ROST=0 if i in stock_demand_bins else None,WT=0 if i in stock_demand_bins else None,WTT=0 if i in stock_demand_bins else None,WTS=None,PNB=1,NDF=int(i in stock_demand_bins),NWT=int(i in stock_demand_bins))
        for key,value in stock_expected.items():
            a.eq(tr[key],value,f"StockTotalResults bin {i} {key}")
    a.eq(sum(r["NFAIL"] for r in s),4,"four system failures")
    a.eq(sum(r["NREPT"] for r in s),3,"three repairs complete before final report boundary")
    a.eq((s[-1]["NSYRY"],s[-1]["NSYUA"],s[-1]["NSYA"]),(1,1,1),"h35.5-36 report ready1/unavailable1")
    a.eq(t[-1]["NBO"],0,"reported terminal no aggregate backorder")
    result = {"schema":"simlox-independent-readonly-review/v1","case_id":"E12.var02-two-fault-control","run_id":RUN.name,"passed":not a.failures,"verdict":"GO: bounded two-base individual repair control" if not a.failures else "NO-GO: independent replay mismatch","checks_passed":a.passed,"checks_total":a.passed+len(a.failures),"failures":a.failures,"evidence":{"closure_sha256":sha(RUN/"closure.json"),"parent_closure_sha256":sha(PRUN/"closure.json"),"raw_seals":len(closure["raw"]),"authored_tables_exact_roundtrip":len(authored),"report_bins_each":72,"mission_outcomes":["abort","abort","abort","success","abort","success"],"system_repairs":[["BASE-01",10.7579,11.2579],["BASE-02",11.5,12],["BASE-01",23.4473,23.9473],["BASE-01",35.5,36]],"depot_backorder_interval":[11.5,14.9246],"horizon_physical_stock":{"BASE-01":0,"BASE-02":1,"DEPOT-01":0},"last_failed_item_in_transit":6},"limits":["Individual SystemRepair control only; group repair equivalence requires a separately frozen group arm.","One seed and 36-hour horizon. Report final half-hour bin is ready1/unavailable1, while event log reaches ready2 at exact h36 boundary.","Failed physical ID6 has begun the BASE-01-to-depot return at horizon and has not undergone item repair.","StockTotalResults aggregate NBO remains zero despite a physical depot backorder in model.log; do not equate the aggregate column with the depot's local ledger.","No GUI visual, other seed or cross-engine generalization."]}
    OUT.write_bytes((json.dumps(result,indent=2,ensure_ascii=False)+"\n").encode("utf-8"))
    return result

if __name__ == "__main__":
    result=main()
    print(json.dumps({k:result[k] for k in ("verdict","checks_passed","checks_total","failures")},indent=2))
    sys.exit(0 if result["passed"] else 1)
