"""Independent standard-library replay of sealed E12.var01 raw evidence."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
PARENT = CASE.parent / "E12-symmetric-two-bases-v1.0.0"
RUN = CASE / "runs" / "e12-var01-explicit-bases-v100-ssh-20261003-01"
PRUN = PARENT / "runs" / "e12-symmetric-two-bases-v100-ssh-20261003-01"
OUT = Path(__file__).with_name("independent-verdict.json")

class Audit:
    def __init__(self):
        self.passed = 0
        self.failures = []
    def check(self, condition, label):
        if condition:
            self.passed += 1
        else:
            self.failures.append(label)
    def eq(self, actual, expected, label):
        self.check(actual == expected, f"{label}: expected {expected!r}; got {actual!r}")

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read_json(path, native=False):
    text = path.read_text(encoding="utf-8-sig")
    if native:
        text = re.sub(r",\s*([}\]])", r"\1", text)
    return json.loads(text)

def tables(path, key="model"):
    return {t["name"]: t for t in read_json(path, key == "report")[key]["tables"]}

def rows(table):
    return [r for inst in table["instances"] for r in inst.get("rows", [])]

def records(table):
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, r)) for r in rows(table)]

def main():
    a = Audit()
    contract = read_json(CASE / "contract.json")
    diff = read_json(CASE / "exact-diff.json")
    source = tables(CASE / "native-input.json")
    parent = tables(PARENT / "native-input.json")
    export = tables(RUN / "roundtrip-raw.json")
    report = tables(RUN / "report-raw.json", "report")
    preport = tables(PRUN / "report-raw.json", "report")
    inv = read_json(RUN / "invocation.json")
    closure = read_json(RUN / "closure.json")
    steps = read_json(RUN / "steps.json")
    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace").replace("\r\n", "\n")
    converter = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")

    a.eq(contract["variant_id"], "E12.var01", "contract case")
    a.eq(sha(CASE / "native-input.json"), contract["native_input_sha256"], "input pin")
    a.eq(sha(CASE / "exact-diff.json"), contract["exact_diff_sha256"], "diff pin")
    a.eq(sha(PARENT / "native-input.json"), contract["accepted_parent"]["input_sha256"], "accepted parent input")
    a.eq(sha(PRUN / "closure.json"), contract["accepted_parent"]["native_closure_sha256"], "accepted parent closure")
    a.eq(sha(PARENT / "evidence-index.json"), contract["accepted_parent"]["evidence_index_sha256"], "accepted parent index")
    a.eq(diff["parent_sha256"], sha(PARENT / "native-input.json"), "diff parent pin")
    a.eq(diff["source_sha256"], sha(CASE / "native-input.json"), "diff child pin")
    changed = sorted(name for name in source if source[name] != parent[name])
    a.eq(changed, diff["changed_tables"], "nine-table actual/declaration delta")
    a.eq(len(changed), 9, "nine changed tables")
    a.eq(len(source), 32, "32 business tables")
    a.eq(set(source), set(parent), "table set unchanged")
    for name in sorted(source):
        a.eq(source[name]["columns"], parent[name]["columns"], f"schema {name}")
        if name not in changed:
            a.eq(source[name], parent[name], f"unchanged table {name}")
    a.eq(len(diff["added_rows"]), 8, "eight added rows")
    for item in diff["added_rows"]:
        name = item["table"]
        index = item["index"]
        a.eq([c["name"] for c in source[name]["columns"]], item["columns"], f"added {name} columns")
        a.eq(rows(source[name])[index], item["row"], f"added {name} row")
        reduced = rows(source[name])[:index] + rows(source[name])[index+1:]
        if name == "Station":
            p = [list(r) for r in rows(parent[name])]
            q = next(i for i, c in enumerate(parent[name]["columns"]) if c["name"] == "QTY")
            p[0][q] = 1
            a.eq(reduced, p, "Station addition plus BASE-01 QTY2-to-1")
        else:
            a.eq(reduced, rows(parent[name]), f"only added {name} row")
    for name, key, old, new in [("Station", "QTY", 2, 1), ("ProblemDescription", "PDESC", diff["description_before"], diff["description_after"])]:
        prows, crows = records(parent[name]), records(source[name])
        a.eq(prows[0][key], old, f"parent {name}.{key}")
        a.eq(crows[0][key], new, f"child {name}.{key}")
    a.eq([(r["STID"], r["QTY"]) for r in records(source["Station"]) if r["STID"].startswith("BASE")], [("BASE-01", 1), ("BASE-02", 1)], "two individually named bases")
    a.eq([(r["UNID"], r["STID"]) for r in records(source["Unit"])], [("TEACH-UNIT", "BASE-01"), ("TEACH-UNIT-2", "BASE-02")], "one unit each")
    a.eq([(r["STID"], r["STSIZ"]) for r in records(source["StockAllocation"]) if r["STID"].startswith("BASE")], [("BASE-01", 1), ("BASE-02", 1)], "one local spare each")

    installed = {"simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"), "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"), "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")}
    for key, path in installed.items():
        field = {"simlox_exe": "simlox_exe_sha256", "manual": "manual_pdf_sha256", "dictionary": "dictionary_sha256"}[key]
        a.eq(sha(path), contract["source"][field], f"installed {key}")
    a.eq(inv["run_id"], RUN.name, "run identity")
    a.eq(inv["execution_mode"], "ssh_cli_v1", "SSH CLI")
    a.eq(inv["session_id"], 0, "session 0")
    a.check(inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"], "SSH ancestry")
    a.eq(inv["queue_mutex"], r"Global\SimloxIssue18NativeQueue", "mutex")
    a.eq((inv["gui"]["pid"], inv["gui"]["session_id"]), (13340, 1), "GUI identity")
    a.eq(inv["input_sha256"], sha(CASE / "native-input.json"), "invoked input")
    a.eq(closure["invocation_sha256"], sha(RUN / "invocation.json"), "invocation seal")
    a.eq(closure["source_hashes_before"], closure["source_hashes_after"], "source frozen during run")
    a.eq(closure["source_hashes_before"], inv["source_hashes_before"], "invocation/closure source agreement")
    paths = {"input": CASE / "native-input.json", "parent": PARENT / "native-input.json", "parent_closure": PRUN / "closure.json", "parent_index": PARENT / "evidence-index.json", "contract": CASE / "contract.json", "exact_diff": CASE / "exact-diff.json", "builder": CASE / "build.py", "diff_builder": CASE / "describe_diff.py", "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1", "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"), **installed}
    for key, path in sorted(paths.items()):
        a.eq(closure["source_hashes_before"][key], sha(path), f"frozen source {key}")
    a.eq(len(closure["raw"]), 12, "12 raw seals")
    for name, meta in sorted(closure["raw"].items()):
        path = RUN / name
        a.check(path.is_file(), f"raw exists {name}")
        if path.is_file():
            a.eq(path.stat().st_size, meta["bytes"], f"raw bytes {name}")
            a.eq(sha(path), meta["sha256"], f"raw SHA {name}")
    a.eq(sha(RUN / "input.json"), sha(CASE / "native-input.json"), "run source copy")
    a.eq([s["name"] for s in steps], ["import", "export", "calc", "jsonreport", "check_import_export"], "five steps")
    for s in steps:
        a.eq(s["exit_code"], 0, f"{s['name']} exit")
        a.eq(s["status"], "completed", f"{s['name']} status")
        a.check(s["gui_preserved"] is True, f"{s['name']} GUI preserved")
        a.eq(s["error"], None, f"{s['name']} no error")
    authored = sorted(name for name, t in source.items() if rows(t))
    a.eq(len(authored), 22, "22 authored row tables")
    a.eq(set(export), set(source), "export table set")
    for name in authored:
        a.eq(export[name], source[name], f"exact native roundtrip {name}")
    a.check((RUN / "model.sxo").stat().st_size > 4, "valid SXO")
    a.eq(re.findall(r"\(error #(\d+)\)", converter), [], "zero converter errors")
    a.eq(re.findall(r"\(warning #(\d+)\)", converter), ["108"], "warning 108 only")
    a.check("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in converter, "converter summary")

    def event(hour, phrase):
        a.check(any(line.startswith(f"Time: {hour} ") and phrase in line for line in log.splitlines()), f"h{hour} {phrase}")
    for base, unit, aircraft, spare in [("BASE-01", "TEACH-UNIT", 0, 1), ("BASE-02", "TEACH-UNIT-2", 1, 2)]:
        event("0", f"<{unit} at <{base},0>> systems ready: 1 :<TEACH-AIR-01,{aircraft}>")
        a.check(f"Time: 0 <TEACH-LRU-01,0,{base},0> Stock initiated \n  Stock at: <TEACH-LRU-01,0,{base},0> Level: 1 Items:<TEACH-LRU-01,0,{spare}>" in log, f"{base} initial spare ID{spare}")
        event("34", f"<{unit} at <{base},0>> systems ready: 1 :<TEACH-AIR-01,{aircraft}>")
    a.check("Time: 0 <TEACH-LRU-01,0,DEPOT-01,0> Stock initiated \n  Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 1 Items:<TEACH-LRU-01,0,0>" in log, "depot initial spare ID0")
    for mid in range(6):
        unit = "TEACH-UNIT" if mid % 2 == 0 else "TEACH-UNIT-2"
        aircraft = mid % 2
        ordered, started, finished = (7, 8, 10) if mid < 2 else (19, 20, 22) if mid < 4 else (31, 32, 34)
        ident = f"<BASIC-MISSION,{unit},0,0,{mid}>"
        event(str(ordered), f"{ident} mission created:")
        event(str(ordered), f"{ident} mission allocates system: <TEACH-AIR-01,{aircraft}>")
        event(str(started), f"{ident} mission starting, duration: 2 : <TEACH-AIR-01,{aircraft}>")
        event(str(finished), f"{ident} {'aborted mission completed:' if mid == 0 else 'mission completed:'}")
        if mid:
            event(str(finished), f"{ident} mission success:")
    for phrase, count in [("mission created:", 6), ("mission starting, duration:", 6), ("mission aborted:", 1), ("mission success:", 5), ("mission cancelled:", 0), ("Backorder added", 0), ("books resources", 0)]:
        a.eq(log.count(phrase), count, f"event count {phrase}")
    for hour, phrase in [("9.8829", "<TEACH-AIR-01,0> critical random failure added"), ("10", "<TEACH-LRU-01,0,BASE-01,0> Take replacement item <TEACH-LRU-01,0,1> from stock"), ("10", "<TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock"), ("10.5", "<TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>"), ("11", "<TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,0> to stock"), ("13.1667", "<TEACH-LRU-01,0,DEPOT-01,0> Start repair of item <TEACH-LRU-01,0,3>"), ("14.1667", "<TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item <TEACH-LRU-01,0,3>"), ("14.1667", "<TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-LRU-01,0,3> to stock")]:
        event(hour, phrase)
    event("10", "item requiring maintenance is <TEACH-LRU-01,0,3>")
    event("10", "transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> started")
    event("10.1667", "transport request <<TEACH-LRU-01,0,3>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> started")
    a.eq(log.count("<TEACH-LRU-01,0,BASE-02,0> Take replacement item"), 0, "BASE-02 spare unused")
    a.eq(log.count("transport request <<TEACH-LRU-01,0,2>"), 0, "BASE-02 spare not transported")
    a.check("Time: 11 <TEACH-LRU-01,0,BASE-01,0> Put back replacement item <TEACH-LRU-01,0,0> to stock \n  Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,0>" in log, "BASE-01 terminal stock ID0")
    a.check("Time: 14.1667 <TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-LRU-01,0,3> to stock \n  Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 1 Items:<TEACH-LRU-01,0,3>" in log, "depot terminal stock ID3")

    a.eq(set(report), {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "report tables")
    for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
        a.eq(report[name], preport[name], f"full {name} parity with symmetric parent")
    a.check(report["ProblemDescription"] != preport["ProblemDescription"], "only description differs")
    summary = records(report["ResultSummary"])[0]
    a.eq((summary["NREP"], summary["MTMF"], summary["MSTF"], summary["MSUF"], summary["STMF"]), (1, 1, 1, 0.8333333134651184, 1), "summary factors")
    system = records(report["SystemResults"])
    stock = records(report["StockTotalResults"])
    a.eq((len(system), len(stock)), (72, 72), "72 aligned report bins")
    for i, (s, t) in enumerate(zip(system, stock)):
        a.eq((s["STINT"], s["ETINT"], t["STINT"], t["ETINT"]), (i/2, (i+1)/2, i/2, (i+1)/2), f"bin {i} interval")
        a.eq(s, records(preport["SystemResults"])[i], f"SystemResults row {i} parity")
        a.eq(t, records(preport["StockTotalResults"])[i], f"StockTotalResults row {i} parity")
    a.eq(sum(r["NSYMO"] * .5 for r in system), 12, "12 aircraft operating hours")
    a.eq(sum(r["NFAIL"] for r in system), 1, "one failure")
    a.eq(sum(r["NBO"] * .5 for r in stock), 0, "zero aggregate backorder hours")
    a.eq((system[-1]["NSYRY"], stock[-1]["NBO"]), (2, 0), "terminal ready two, no BO")

    result = {"schema": "simlox-independent-readonly-review/v1", "case_id": "E12.var01", "run_id": RUN.name, "passed": not a.failures, "verdict": "GO: bounded explicit two-base parity" if not a.failures else "NO-GO: independent replay mismatch", "checks_passed": a.passed, "checks_total": a.passed + len(a.failures), "failures": a.failures, "evidence": {"child_closure_sha256": sha(RUN / "closure.json"), "parent_closure_sha256": sha(PRUN / "closure.json"), "raw_seals": len(closure["raw"]), "authored_tables_exact_roundtrip": len(authored), "report_bins_each": 72, "opening_physical_spares": {"BASE-01": 1, "BASE-02": 2, "DEPOT-01": 0}, "failed_item_id": 3, "mission_outcomes": ["abort", "success", "success", "success", "success", "success"]}, "limits": ["One fixed seed and 36-hour horizon. Exact aggregate parity does not establish statistical or general identity equivalence.", "Aggregate report rows do not identify individual bases; native event identities support the bounded base-specific conclusion.", "No GSTID defaults, overrides, differing support schemes, GUI-only behavior or cross-engine parity."]}
    OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return result

if __name__ == "__main__":
    result = main()
    print(json.dumps({k: result[k] for k in ("verdict", "checks_passed", "checks_total", "failures")}, indent=2))
    sys.exit(0 if result["passed"] else 1)
