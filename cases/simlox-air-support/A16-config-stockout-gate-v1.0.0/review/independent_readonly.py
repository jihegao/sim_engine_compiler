"""Independent read-only replay of the sealed A16 B-stockout contrast."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
AIR = CASE.parent
RUN = CASE / "runs" / "a16-config-stockout-v100-20261001-01"
BASE = AIR / "A16-two-config-reconfiguration-v1.0.0"
BASE_RUN = BASE / "runs" / "a16-two-config-v100-20261001-01"
OUT = CASE / "review" / "independent-readonly-2026-10-01.json"
checks = 0
failures: list[str] = []


def ck(condition: bool, label: str) -> None:
    global checks
    checks += 1
    if not condition:
        failures.append(label)


def near(a: float, b: float) -> bool:
    return abs(a - b) < 1e-5


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(re.sub(r",(?=\s*[}\]])", "", path.read_text(encoding="utf-8-sig")))


def tables(path: Path, root: str) -> dict[str, dict]:
    return {t["name"]: t for t in load(path)[root]["tables"]}


def rows(table: dict) -> list[list]:
    return [r for instance in table["instances"] for r in instance["rows"]]


def records(table: dict) -> list[dict]:
    columns = [c["name"] for c in table["columns"]]
    return [dict(zip(columns, row)) for row in rows(table)]


def has(log: str, hour: str, phrase: str) -> bool:
    return any(line.startswith(f"Time: {hour} ") and phrase in line for line in log.splitlines())


def main() -> None:
    contract, delta = load(CASE / "contract.json"), load(CASE / "exact-diff.json")
    parent, donor, source = BASE / "native-input.json", AIR / "E02-zero-stock-local-backorder-v1.0.0" / "native-input.json", CASE / "native-input.json"
    ck(sha(parent) == contract["parent_sha256"], "accepted baseline parent sha")
    ck(sha(donor) == contract["zero_stock_method_sha256"], "accepted E02 donor sha")
    ck(sha(source) == contract["input_sha256"], "frozen stockout source sha")
    ptab, ctab = tables(parent, "model"), tables(source, "model")
    ck({name for name in ptab if ptab[name] != ctab[name]} == set(delta) == {"ProblemDescription", "StockAllocation"}, "exact two-table delta")
    for name, pair in delta.items():
        ck(rows(ptab[name]) == pair["parent"] and rows(ctab[name]) == pair["child"], f"{name} exact rows")
    base_stock = records(ptab["StockAllocation"])
    child_stock = records(ctab["StockAllocation"])
    ck([(r["IID"], r["STSIZ"]) for r in base_stock] ==
       [("TEACH-LRU-01", 1), ("TEACH-LRU-A", 1), ("TEACH-LRU-B", 1)], "baseline stock 1/1/1")
    ck([(r["IID"], r["STSIZ"]) for r in child_stock] ==
       [("TEACH-LRU-01", 1), ("TEACH-LRU-A", 1), ("TEACH-LRU-B", 0)], "child stock 1/1/0")
    ck(not rows(ctab["ItemReorder"]), "no B replenishment source")
    ck(records(ctab["MissionSystem"]) == records(ptab["MissionSystem"]), "mission requirements unchanged")
    inv, closure = load(RUN / "invocation.json"), load(RUN / "closure.json")
    ck(inv["run_id"] == closure["run_id"] == RUN.name and closure["error"] is None, "run identity/error")
    ck(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation sha")
    ck(inv["input_sha256"] == sha(source) == sha(RUN / "input.json"), "copied input sha")
    ck(inv["parent_sha256"] == sha(parent) and inv["contract_sha256"] == sha(CASE / "contract.json"), "parent/contract sha")
    ck(inv["session_id"] == 0 and inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"], "session0 SSH")
    ck(inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "mutex")
    ck(inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, "GUI identity")
    ck(inv["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"], "source stable")
    pinned = {"input": source, "parent": parent, "zero_stock_method": donor, "contract": CASE / "contract.json",
              "builder": CASE / "build.py", "exact_diff": CASE / "exact-diff.json",
              "diff_checker": CASE / "describe_diff.py", "checker": CASE / "check_roundtrip.py",
              "runner_script": CASE / "run_native_ssh.ps1"}
    for key, path in pinned.items():
        ck(inv["source_hashes_before"].get(key) == sha(path), f"sealed {key}")
    ck(inv["source_hashes_before"]["simlox_exe"] == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0", "runtime sha")
    for name, meta in closure["raw"].items():
        path = RUN / name
        ck(path.is_file() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"], f"raw {name}")
    steps = load(RUN / "steps.json")
    ck([step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], "five native steps")
    for step in steps:
        ck(step["exit_code"] == 0 and step["status"] == "completed" and step["gui_preserved"] and step["error"] is None, f"step {step['name']}")
    exported = tables(RUN / "roundtrip-raw.json", "model")
    populated = {name for name, table in ctab.items() if rows(table)}
    ck(len(populated) == 21, "21 populated source tables")
    for name in populated:
        ck(name in exported and ctab[name]["columns"] == exported[name]["columns"] and rows(ctab[name]) == rows(exported[name]), f"roundtrip {name}")
    runlog = (RUN / "run.log").read_text(errors="replace")
    ck("Input conversion completed. Errors: 0, Warnings: 4, Notes: 0" in runlog, "zero conversion errors")
    ck("warning #108" in runlog and runlog.count("warning #2053") == 3, "known warnings")
    ck((RUN / "model.sxo").stat().st_size > 100000, "valid SXO")
    log = (RUN / "model.log").read_text(errors="replace")
    base_log = (BASE_RUN / "model.log").read_text(errors="replace")
    ck(has(log, "7", "<TEACH-AIR-01,0> reconfig started, mission: <CONF-A-MISSION") and
       has(log, "7.33333", "<TEACH-AIR-01,0> reconfig ended, mission: <CONF-A-MISSION"), "A reconfig 7–7.33333")
    ck(has(log, "7", "Take replacement item <TEACH-LRU-A,0,0> from stock"), "A draw")
    ck(has(log, "8", "CONF-A-MISSION,TEACH-UNIT,0,0,0> mission starting, duration: 2 : <TEACH-CONF-A,0>") and
       has(log, "10", "CONF-A-MISSION,TEACH-UNIT,0,0,0> mission success:"), "A mission success")
    ck(has(log, "19", "CONF-B-MISSION,TEACH-UNIT,0,0,1> mission waiting:  timeout at 20.3333"), "B waits at19")
    ck(has(log, "20.3333", "CONF-B-MISSION,TEACH-UNIT,0,0,1> mission cancelled:"), "B cancelled at20.3333")
    ck("CONF-B-MISSION,TEACH-UNIT,0,0,1> mission starting" not in log, "no B launch")
    ck("Reconfiguration item demand arrives" not in "\n".join(line for line in log.splitlines() if line.startswith("Time: 19 ")), "no B reconfiguration item demand")
    ck("Take replacement item <TEACH-LRU-B" not in log and "Put back replacement item <TEACH-LRU-B" not in log, "no B stock movement")
    ck("<TEACH-CONF-A,0> reconfig started, mission: <CONF-B-MISSION" not in log and
       "system reconfig fit task 2" not in log, "no A to B reconfiguration")
    ck(has(log, "31", "<TEACH-CONF-A,0> reconfig started, mission: <BASE-MISSION") and
       has(log, "31.1667", "<TEACH-CONF-A,0> reconfig ended, mission: <BASE-MISSION"), "A to base 31–31.1667")
    ck(has(log, "31", "system reconfig remove task 1") and has(log, "31", "starts performing, planned to last for 0.166667 hours"), "10 minute A removal")
    ck(has(log, "31.1667", "Put back replacement item <TEACH-LRU-A,0,2> to stock"), "A stock return")
    ck(has(log, "32", "BASE-MISSION,TEACH-UNIT,0,0,2> mission starting, duration: 2 : <TEACH-AIR-01,0>") and
       has(log, "34", "BASE-MISSION,TEACH-UNIT,0,0,2> mission success:"), "base mission success")
    ck(has(log, "34", "systems ready: 1 :<TEACH-AIR-01,0>"), "terminal base ready")
    ck("critical random failure added" not in log and "mission aborted:" not in log, "no failure/abort")
    ck("Take replacement item <TEACH-LRU-B" in base_log and
       "CONF-B-MISSION,TEACH-UNIT,0,0,1> mission starting" in base_log, "accepted baseline B positive contrast")
    levels = {}
    for item in ("TEACH-LRU-01", "TEACH-LRU-A", "TEACH-LRU-B"):
        levels[item] = [int(x.group(1)) for x in re.finditer(rf"Stock at: <{re.escape(item)},0,BASE-01,0> Level: (\d+)", log)]
    ck(levels == {"TEACH-LRU-01": [1], "TEACH-LRU-A": [1, 0, 1], "TEACH-LRU-B": [0]}, "individual stock balances")
    report = tables(RUN / "report-raw.json", "report")
    base_report = tables(BASE_RUN / "report-raw.json", "report")
    ck(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "report tables")
    summary = records(report["ResultSummary"])
    ck(len(summary) == 1 and summary[0]["NREP"] == 1 and summary[0]["RTIUP"] == 36 and
       all(near(summary[0][x], 2 / 3) for x in ("MTMF", "MSTF", "MSUF", "STMF")), "two of three summary factors")
    ck(all(records(base_report["ResultSummary"])[0][x] == 1 for x in ("MTMF", "MSTF", "MSUF", "STMF")), "baseline three of three factors")
    sys, stock = records(report["SystemResults"]), records(report["StockTotalResults"])
    ck(len(sys) == len(stock) == 72, "72 System/Stock bins")
    for i, (sr, st) in enumerate(zip(sys, stock)):
        h = i / 2
        notice = int(7 <= h < 8 or 31 <= h < 32)
        mission = int(8 <= h < 10 or 32 <= h < 34)
        ready = 1 - int(bool(notice or mission))
        cfg = {7: 2 / 3, 31: 1 / 3}.get(h, 0)
        prep = (1 - cfg) if notice else 0
        request = int(8 <= h < 10 or 20 <= h < 22 or 32 <= h < 34)
        ck((sr["STINT"], sr["ETINT"], st["STINT"], st["ETINT"]) == (h, h + .5, h, h + .5), f"bin time {i}")
        ck((sr["NSYRY"], sr["NSYMA"], sr["NSYMO"], sr["NSYA"], sr["FTMO"], sr["STACC"]) ==
           (ready, int(bool(notice or mission)), mission, 1, mission, mission), f"System ledger {i}")
        ck(near(sr["NSYMC"], cfg) and near(sr["NSYMR"], prep) and sr["NRCFG"] == int(h in (7, 31)), f"reconfig ledger {i}")
        ck(sr["STREQ"] == .5 * request and all(sr[x] == 0 for x in ("NFAIL", "NREPT", "NPMT", "NSYRP", "NSYPM")), f"request/no-failure ledger {i}")
        ck(st["PNB"] == 1 and st["NBO"] == 0 and st["NDR"] == int(h == 7) and st["NWT"] == int(h == 7) and
           all(st[x] == 0 for x in ("NDF", "NDD", "NDP", "NLD")), f"Stock ledger {i}")
    ck(sys[-1]["NSYRY"] == 1 and stock[-1]["PNB"] == 1, "terminal report")
    result = {"schema": "simlox-a16-stockout-independent-review/v1", "passed": not failures,
              "verdict": "GO" if not failures else "NO-GO", "check_count": checks,
              "failure_count": len(failures), "failures": failures, "stock_level_sequences": levels,
              "scope": "One deterministic B-spare stockout relative to accepted A16 1-spare baseline.",
              "limits": ["No replenishment, mechanics contention, failures, PM, alternative seeds, GUI rendering, or cross-engine parity.",
                         "No B reconfiguration item demand is logged; native assignment rejects B before work starts. Aggregate StockTotalResults cannot show item identity; individual log supplies that ledger."]}
    OUT.write_bytes((json.dumps(result, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks": checks, "failures": failures, "result": str(OUT)}))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
