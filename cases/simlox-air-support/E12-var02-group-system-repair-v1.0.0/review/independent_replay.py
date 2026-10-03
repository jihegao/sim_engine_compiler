"""Read-only independent replay of sealed E12.var02 group repair evidence."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
PARENT = CASE.parent / "E12-var01-explicit-two-bases-v1.0.0"
RUN = CASE / "runs" / "e12-var02-group-repair-v100-ssh-20261003-01"
PRUN = PARENT / "runs" / "e12-var01-explicit-bases-v100-ssh-20261003-01"
OUT = Path(__file__).with_name("independent-verdict.json")

class Audit:
    def __init__(self):
        self.passed = 0
        self.failures = []
    def check(self, ok, label):
        if ok:
            self.passed += 1
        else:
            self.failures.append(label)
    def eq(self, found, expected, label):
        self.check(found == expected, f"{label}: expected {expected!r}, found {found!r}")

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def obj(path, native=False):
    text = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", text) if native else text)

def tables(path, key="model"):
    return {t["name"]: t for t in obj(path, key == "report")[key]["tables"]}

def rows(t):
    return [r for inst in t["instances"] for r in inst.get("rows", [])]

def records(t):
    names = [c["name"] for c in t["columns"]]
    return [dict(zip(names, r)) for r in rows(t)]

def main():
    a = Audit()
    contract = obj(CASE / "contract.json")
    diff = obj(CASE / "exact-diff.json")
    source = tables(CASE / "native-input.json")
    parent = tables(PARENT / "native-input.json")
    export = tables(RUN / "roundtrip-raw.json")
    report = tables(RUN / "report-raw.json", "report")
    preport = tables(PRUN / "report-raw.json", "report")
    inv = obj(RUN / "invocation.json")
    closure = obj(RUN / "closure.json")
    steps = obj(RUN / "steps.json")
    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    converter = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    a.eq(contract["variant_id"], "E12.var02", "contract variant")
    a.eq(sha(CASE / "native-input.json"), contract["native_input_sha256"], "child input pin")
    a.eq(sha(CASE / "exact-diff.json"), contract["exact_diff_sha256"], "diff pin")
    a.eq(sha(PARENT / "native-input.json"), contract["accepted_parent"]["input_sha256"], "parent input pin")
    a.eq(sha(PRUN / "closure.json"), contract["accepted_parent"]["native_closure_sha256"], "parent closure pin")
    a.eq(sha(PARENT / "evidence-index.json"), contract["accepted_parent"]["evidence_index_sha256"], "parent index pin")
    a.eq(diff["parent_sha256"], sha(PARENT / "native-input.json"), "diff parent")
    a.eq(diff["source_sha256"], sha(CASE / "native-input.json"), "diff child")
    a.eq(len(source), 32, "32 source tables")
    a.eq(set(source), set(parent), "source table sets equal")
    changed = sorted(name for name in source if source[name] != parent[name])
    a.eq(changed, diff["changed_tables"], "exact three changed tables")
    a.eq(diff["unchanged_parent_tables"], 29, "29 unchanged tables")
    for name in sorted(source):
        a.eq(source[name]["columns"], parent[name]["columns"], f"schema {name}")
        if name not in changed:
            a.eq(source[name], parent[name], f"untouched table {name}")
    old_station, new_station = records(parent["Station"]), records(source["Station"])
    a.eq([r["GSTID"] for r in old_station], diff["station_gstid_before"], "parent GSTID rows")
    a.eq([r["GSTID"] for r in new_station], diff["station_gstid_after"], "child GSTID rows")
    for i in range(len(old_station)):
        before, after = dict(old_station[i]), dict(new_station[i])
        before["GSTID"] = after["GSTID"]
        a.eq(before, after, f"Station row {i} GSTID-only delta")
    a.eq([c["name"] for c in source["SystemRepair"]["columns"]], diff["repair_columns"], "repair schema")
    a.eq(rows(parent["SystemRepair"]), diff["repair_rows_before"], "parent explicit repair rows")
    a.eq(rows(source["SystemRepair"]), diff["repair_rows_after"], "child one group repair row")
    a.eq(len(rows(source["SystemRepair"])), 1, "one group repair row")
    a.eq(records(parent["ProblemDescription"])[0]["PDESC"], diff["description_before"], "parent description")
    a.eq(records(source["ProblemDescription"])[0]["PDESC"], diff["description_after"], "child description")
    a.eq(len(rows(source["ProblemDescription"])), 1, "single description row")
    pdesc, cdesc = dict(records(parent["ProblemDescription"])[0]), dict(records(source["ProblemDescription"])[0])
    pdesc["PDESC"] = cdesc["PDESC"]
    a.eq(pdesc, cdesc, "description field alone changes")

    installed = {"simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"), "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"), "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")}
    for key, path in installed.items():
        field = {"simlox_exe": "simlox_exe_sha256", "manual": "manual_pdf_sha256", "dictionary": "dictionary_sha256"}[key]
        a.eq(sha(path), contract["source"][field], f"installed {key} pin")
    a.eq(inv["run_id"], RUN.name, "run ID")
    a.eq(inv["execution_mode"], "ssh_cli_v1", "SSH CLI")
    a.eq(inv["session_id"], 0, "session zero")
    a.check(inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"], "SSH ancestry")
    a.eq(inv["queue_mutex"], r"Global\SimloxIssue18NativeQueue", "queue mutex")
    a.eq((inv["gui"]["pid"], inv["gui"]["session_id"]), (13340, 1), "GUI identity")
    a.eq(inv["input_sha256"], sha(CASE / "native-input.json"), "invocation source")
    a.eq(closure["invocation_sha256"], sha(RUN / "invocation.json"), "invocation seal")
    a.eq(closure["source_hashes_before"], closure["source_hashes_after"], "source stability")
    a.eq(closure["source_hashes_before"], inv["source_hashes_before"], "source agreement")
    paths = {"input": CASE / "native-input.json", "parent": PARENT / "native-input.json", "parent_closure": PRUN / "closure.json", "parent_index": PARENT / "evidence-index.json", "contract": CASE / "contract.json", "exact_diff": CASE / "exact-diff.json", "builder": CASE / "build.py", "diff_builder": CASE / "describe_diff.py", "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1", "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"), **installed}
    for key, path in sorted(paths.items()):
        a.eq(closure["source_hashes_before"][key], sha(path), f"source seal {key}")
    a.eq(len(closure["raw"]), 12, "12 raw seals")
    for name, meta in sorted(closure["raw"].items()):
        path = RUN / name
        a.check(path.is_file(), f"raw present {name}")
        if path.is_file():
            a.eq(path.stat().st_size, meta["bytes"], f"raw size {name}")
            a.eq(sha(path), meta["sha256"], f"raw hash {name}")
    a.eq(sha(RUN / "input.json"), sha(CASE / "native-input.json"), "run input")
    a.eq([s["name"] for s in steps], ["import", "export", "calc", "jsonreport", "check_import_export"], "five steps")
    for step in steps:
        a.eq(step["exit_code"], 0, f"{step['name']} exit")
        a.eq(step["status"], "completed", f"{step['name']} completed")
        a.eq(step["error"], None, f"{step['name']} error")
        a.check(step["gui_preserved"] is True, f"{step['name']} GUI preserved")
    authored = sorted(name for name, table in source.items() if rows(table))
    a.eq(len(authored), 22, "22 authored row tables")
    a.eq(set(source), set(export), "export table set")
    for name in authored:
        a.eq(export[name], source[name], f"exact roundtrip {name}")
    a.check((RUN / "model.sxo").stat().st_size > 4, "usable SXO")
    a.eq(re.findall(r"\(error #(\d+)\)", converter), [], "no converter errors")
    a.eq(re.findall(r"\(warning #(\d+)\)", converter), ["108"], "warning #108 only")
    a.check("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in converter, "conversion summary")

    a.eq(sha(RUN / "model.log"), sha(PRUN / "model.log"), "byte-identical parent and group event logs")
    for base, unit, aircraft, spare in [("BASE-01", "TEACH-UNIT", 0, 1), ("BASE-02", "TEACH-UNIT-2", 1, 2)]:
        a.check(f"Time: 0 <{unit} at <{base},0>> systems ready: 1 :<TEACH-AIR-01,{aircraft}>" in log, f"{base} unique unit and aircraft")
        a.check(f"Time: 0 <TEACH-LRU-01,0,{base},0> Stock initiated \n  Stock at: <TEACH-LRU-01,0,{base},0> Level: 1 Items:<TEACH-LRU-01,0,{spare}>" in log.replace("\r\n", "\n"), f"{base} initial stock ID{spare}")
        a.check(f"Time: 34 <{unit} at <{base},0>> systems ready: 1 :<TEACH-AIR-01,{aircraft}>" in log, f"{base} terminal ready")
    a.check("Time: 0 <TEACH-LRU-01,0,DEPOT-01,0> Stock initiated \n  Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 1 Items:<TEACH-LRU-01,0,0>" in log.replace("\r\n", "\n"), "depot opening stock ID0")
    a.eq(log.count("mission created:"), 6, "six missions created")
    a.eq(log.count("mission starting, duration:"), 6, "six missions launched")
    a.eq(log.count("mission success:"), 5, "five successes")
    a.eq(log.count("mission aborted:"), 1, "one abort")
    a.eq(log.count("mission cancelled:"), 0, "zero cancellations")
    a.check("Time: 9.8829 <TEACH-AIR-01,0> critical random failure added" in log, "BASE-01 first critical failure")
    a.check("Time: 10  system SURP task 0 on <TEACH-AIR-01,0> started" in log, "group-row half-hour task starts BASE-01")
    a.check("Time: 10.5  system SURP task 0 on <TEACH-AIR-01,0> completed" in log, "group-row half-hour task ends BASE-01")
    for time, phrase in [("10", "BASE-01,0> Take replacement item <TEACH-LRU-01,0,1>"), ("10", "DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0>"), ("11", "BASE-01,0> Put back replacement item <TEACH-LRU-01,0,0>"), ("13.1667", "DEPOT-01,0> Start repair of item <TEACH-LRU-01,0,3>"), ("14.1667", "DEPOT-01,0> Finished repair of item <TEACH-LRU-01,0,3>"), ("14.1667", "DEPOT-01,0> Put back replacement item <TEACH-LRU-01,0,3>")]:
        a.check(any(line.startswith(f"Time: {time} ") and phrase in line for line in log.splitlines()), f"physical event h{time} {phrase}")
    a.eq(log.count("<TEACH-LRU-01,0,BASE-02,0> Take replacement item"), 0, "BASE-02 spare untouched")
    a.eq(log.count("Backorder added"), 0, "zero physical backorders")
    a.eq(log.count("books resources"), 0, "no resource booking")
    a.check("Time: 10  transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> started" in log, "depot ID0 dispatched only to BASE-01")
    a.check("Time: 10.1667  transport request <<TEACH-LRU-01,0,3>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> started" in log, "failed ID3 dispatched only from BASE-01")
    normalized_log = log.replace("\r\n", "\n")
    a.check("Time: 11 <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,0> to stock \n  Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,0>" in normalized_log, "BASE-01 terminal stock ID0")
    a.check("Time: 14.1667 <TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-LRU-01,0,3> to stock \n  Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 1 Items:<TEACH-LRU-01,0,3>" in normalized_log, "depot terminal stock ID3")
    for mid in range(6):
        unit = "TEACH-UNIT" if mid % 2 == 0 else "TEACH-UNIT-2"
        aircraft = mid % 2
        order, start, end = (7, 8, 10) if mid < 2 else (19, 20, 22) if mid < 4 else (31, 32, 34)
        ident = f"<BASIC-MISSION,{unit},0,0,{mid}>"
        a.check(f"Time: {order} {ident} mission created:" in log, f"mission {mid} created")
        a.check(f"Time: {order} {ident} mission allocates system: <TEACH-AIR-01,{aircraft}>" in log, f"mission {mid} aircraft")
        a.check(f"Time: {start} {ident} mission starting, duration: 2" in log, f"mission {mid} start")
        outcome = "aborted mission completed:" if mid == 0 else "mission success:"
        a.check(f"Time: {end} {ident} {outcome}" in log, f"mission {mid} outcome")
    a.eq(set(report), {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "report table set")
    a.check(report["ProblemDescription"] != preport["ProblemDescription"], "description changed")
    for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
        a.eq(report[name], preport[name], f"entire {name} table parity")
    s = records(report["SystemResults"])
    t = records(report["StockTotalResults"])
    a.eq((len(s), len(t)), (72, 72), "72 half-hour bins each")
    ps = records(preport["SystemResults"])
    pt = records(preport["StockTotalResults"])
    for i, (sr, tr) in enumerate(zip(s, t)):
        a.eq((sr["STINT"], sr["ETINT"], tr["STINT"], tr["ETINT"]), (i/2, (i+1)/2, i/2, (i+1)/2), f"bin {i} interval")
        a.eq(sr, ps[i], f"SystemResults bin {i} parity")
        a.eq(tr, pt[i], f"StockTotalResults bin {i} parity")
    summary = records(report["ResultSummary"])[0]
    a.eq((summary["NREP"], summary["MSUF"], summary["MTMF"], summary["STMF"]), (1, 0.8333333134651184, 1, 1), "summary factors")
    a.eq(sum(row["NSYMO"]*.5 for row in s), 12, "12 aircraft operating hours")
    a.eq(sum(row["NFAIL"] for row in s), 1, "one failure")
    a.eq((s[-1]["NSYRY"], t[-1]["NBO"]), (2, 0), "terminal two ready, no BO")
    result = {"schema": "simlox-independent-readonly-review/v1", "case_id": "E12.var02", "run_id": RUN.name, "passed": not a.failures, "verdict": "GO: bounded BASE-01 group SystemRepair application and full parent parity" if not a.failures else "NO-GO: independent replay mismatch", "checks_passed": a.passed, "checks_total": a.passed + len(a.failures), "failures": a.failures, "evidence": {"child_closure_sha256": sha(RUN / "closure.json"), "parent_closure_sha256": sha(PRUN / "closure.json"), "raw_seals": len(closure["raw"]), "authored_tables_exact_roundtrip": len(authored), "event_log_sha256": sha(RUN / "model.log"), "report_bins_each": 72, "observed_repair_base": "BASE-01", "unexercised_group_member": "BASE-02"}, "limits": ["Only BASE-01 had a repair demand in this fixed-seed run. BASE-02 inherits the group source row but native behavior there was not exercised.", "One SystemRepair group default, one seed and 36-hour horizon; no individual override or precedence test.", "StockAllocation and support links remain individual-station rows; no group behavior claim for those tables.", "No GUI visual or cross-engine claim."]}
    OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return result

if __name__ == "__main__":
    verdict = main()
    print(json.dumps({key: verdict[key] for key in ("verdict", "checks_passed", "checks_total", "failures")}, indent=2))
    sys.exit(0 if verdict["passed"] else 1)
