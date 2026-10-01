"""Independent standard-library replay of G01.var03 discard/reorder evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
AIR = CASE.parent
PARENT_CASE = AIR / "G01-var01-lru-sru-v1.0.1"
PARENT = PARENT_CASE / "native-input.json"
RUN = CASE / "runs/g01-var03-dp-v100-ssh-20261001-01"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
OUT = CASE / "review/independent-readonly-2026-10-01.json"
checks = 0
failures: list[str] = []


def ck(test: bool, name: str) -> None:
    global checks
    checks += 1
    if not test:
        failures.append(name)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(re.sub(r",(?=\s*[}\]])", "", path.read_text(encoding="utf-8-sig")))


def tables(path: Path, root: str) -> dict:
    return {t["name"]: t for t in read(path)[root]["tables"]}


def rows(table: dict) -> list:
    return [r for inst in table["instances"] for r in inst["rows"]]


def records(table: dict) -> list[dict]:
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row)) for row in rows(table)]


def event(log: str, time: str, phrase: str) -> bool:
    return any(s.startswith(f"Time: {time} ") and phrase in s for s in log.splitlines())


def near(a, b, tol=1e-5) -> bool:
    return isinstance(a, (float, int)) and abs(a-b) <= tol


def source() -> dict:
    contract = read(CASE / "contract.json")
    input_path = CASE / "native-input.json"
    ck(sha(PARENT) == contract["parent"]["input_sha256"], "accepted G01.var01 parent SHA")
    ck((PARENT_CASE / "cli-scope-signoff-2026-10-01.md").is_file(), "parent signoff")
    ck(sha(input_path) == contract["native_input_sha256"], "child input SHA")
    ck(sha(MANUAL) == contract["source"]["manual_pdf_sha256"], "installed manual SHA")
    ck(sha(DICTIONARY) == contract["source"]["dictionary_sha256"], "installed dictionary SHA")
    p, c = tables(PARENT, "model"), tables(input_path, "model")
    changed = {name for name in p if p[name] != c.get(name)}
    ck(set(p) == set(c) and changed ==
       {"ProblemDescription", "Item", "ItemRepair", "Station", "StationStructure",
        "ItemReorder", "StockAllocation"}, "seven-table parent delta")
    for name in p:
        ck(p[name]["columns"] == c[name]["columns"] and
           (p[name] == c[name] if name not in changed else True), f"source {name} columns/invariance")
    ck(records(c["ProblemDescription"])[0]["PDESC"] ==
       "G01.var03 DP discarded after LRU repair and depot reorder", "source description")
    p_items = {r["IID"]: r for r in records(p["Item"])}
    c_items = {r["IID"]: r for r in records(c["Item"])}
    ck(set(p_items) == set(c_items) and c_items["TEACH-LRU-01"] == p_items["TEACH-LRU-01"] and
       {k for k in c_items["TEACH-SRU-01"] if c_items["TEACH-SRU-01"][k] != p_items["TEACH-SRU-01"][k]} ==
       {"TYPE", "DESCR"} and c_items["TEACH-SRU-01"]["TYPE"] == "DP", "source SRU to DP")
    p_repair, c_repair = records(p["ItemRepair"]), records(c["ItemRepair"])
    ck(len(p_repair) == 2 and len(c_repair) == 1 and
       c_repair == [r for r in p_repair if r["IID"] == "TEACH-LRU-01"], "no DP repair source row")
    station = records(c["Station"])
    ck(station[:-1] == records(p["Station"]) and len(station) == len(records(p["Station"]))+1 and
       {k: v for k, v in station[-1].items() if v is not None} ==
       {"STID": "DEPOT-01", "DESCR": "Teaching reorder depot", "QTY": 1, "TYPE": "DEPOT"},
       "depot station source")
    structure = records(c["StationStructure"])
    ck(structure[:-1] == records(p["StationStructure"]) and
       len(structure) == len(records(p["StationStructure"]))+1 and
       {k: v for k, v in structure[-1].items() if v is not None} ==
       {"STID": "BASE-01", "MSTID": "DEPOT-01", "TFRMS": 2, "TTOMS": 2,
        "DFRAC": 1, "OPOL": "FAST"}, "two-hour depot/base route")
    reorder = records(c["ItemReorder"])
    ck(reorder[:-1] == records(p["ItemReorder"]) and
       len(reorder) == len(records(p["ItemReorder"]))+1 and
       {k: v for k, v in reorder[-1].items() if v is not None} ==
       {"IID": "TEACH-SRU-01", "STID": "DEPOT-01", "LEADT": 1},
       "DP one-hour depot reorder")
    stock = records(c["StockAllocation"])
    ck(len(stock) == len(records(p["StockAllocation"]))+1 and
       stock[:-1] == records(p["StockAllocation"]) and
       {k: v for k, v in stock[-1].items() if v is not None} ==
       {"POINT": "AIR_BASIC", "IID": "TEACH-SRU-01", "STID": "DEPOT-01",
        "STSIZ": 2, "ROSIZ": 1}, "depot initial stock two/reorder one")
    ck(len([n for n, t in c.items() if rows(t)]) == 23, "23 populated source tables")
    return c


def native(src: dict) -> str:
    inv, closure, steps = (read(RUN / f) for f in ("invocation.json", "closure.json", "steps.json"))
    ck(inv["run_id"] == closure["run_id"] == RUN.name and closure["error"] is None, "run identity/closure")
    ck(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation SHA seal")
    ck(inv["input_sha256"] == sha(CASE / "native-input.json") == sha(RUN / "input.json") and
       inv["parent_sha256"] == sha(PARENT) and inv["contract_sha256"] == sha(CASE / "contract.json"),
       "frozen run input/parent/contract")
    ck(inv["execution_mode"] == "ssh_cli_v1" and inv["session_id"] == 0 and
       inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"], "session0 SSH")
    ck(inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
       inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, "mutex/GUI guard")
    ck(inv["source_hashes_before"] == closure["source_hashes_before"] ==
       closure["source_hashes_after"], "source stable during native run")
    for key, path in {"input": CASE / "native-input.json", "parent": PARENT,
                      "contract": CASE / "contract.json", "builder": CASE / "build.py",
                      "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1"}.items():
        ck(inv["source_hashes_before"].get(key) == sha(path), f"source seal {key}")
    ck(inv["source_hashes_before"]["simlox_exe"] ==
       "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0", "SIMLOX runtime seal")
    for name, meta in closure["raw"].items():
        path = RUN / name
        ck(path.is_file() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"],
           f"raw seal {name}")
    ck([s["name"] for s in steps] ==
       ["import", "export", "calc", "jsonreport", "check_import_export"], "five guarded steps")
    for step in steps:
        ck(step["exit_code"] == 0 and step["status"] == "completed" and step["gui_preserved"] and
           step["error"] is None, f"native step {step['name']}")
    exported = tables(RUN / "roundtrip-raw.json", "model")
    for name, table in src.items():
        if rows(table):
            ck(name in exported and exported[name]["columns"] == table["columns"] and
               rows(exported[name]) == rows(table), f"native roundtrip {name}")
    runlog = (RUN / "run.log").read_text(errors="replace")
    ck("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and
       "warning #108" in runlog and "error #" not in runlog.lower(), "zero conversion errors")
    ck((RUN / "model.sxo").stat().st_size > 100000, "usable SXO")
    return (RUN / "model.log").read_text(errors="replace")


def events(log: str) -> None:
    ck("Stock at: <TEACH-SRU-01,0,DEPOT-01,0> Level: 2 Items:<TEACH-SRU-01,0,0>,<TEACH-SRU-01,0,1>" in log and
       "Stock at: <TEACH-SRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-SRU-01,0,2>" in log and
       "Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,3>" in log,
       "opening physical item inventory")
    ck(event(log, "9.8829", "critical random failure added") and
       "subitem failed: <TEACH-LRU-01,0,4>" in log and
       event(log, "9.8829", "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted:"),
       "first mission fails on installed LRU4")
    ck(event(log, "10", "Take replacement item <TEACH-LRU-01,0,3> from stock") and
       event(log, "10.1667", "Item requiring maintenance arrives <TEACH-LRU-01,0,4>") and
       event(log, "10.5", "system SURP task 0 on <TEACH-AIR-01,0> completed"),
       "LRU exchange and aircraft restoration")
    ck("subitem failed: <TEACH-SRU-01,0,5>" in log and
       event(log, "10.1667", "Take replacement item <TEACH-SRU-01,0,2> from stock") and
       event(log, "10.1667", "item SURP task 1 on <TEACH-LRU-01,0,4> started"),
       "failed nested DP5 exchanged with base DP2")
    ck(event(log, "10.5417", "Item discarded: <TEACH-SRU-01,0,5>") and
       "item DIRP task" not in log and
       "Put back replacement item <TEACH-SRU-01,0,5>" not in log,
       "DP5 physically discarded, no repair/stock return")
    ck(event(log, "10.9167", "item SURP task 1 on <TEACH-LRU-01,0,4> completed") and
       event(log, "10.9167", "Put back replacement item <TEACH-LRU-01,0,4> to stock"),
       "mother LRU repaired and returned")
    ck(event(log, "10.1667", "Take replacement item <TEACH-SRU-01,0,0> from stock") and
       event(log, "10.1667", "transport task 0 starts with 1 items/systems, transport time: 2") and
       event(log, "12.1667", "transport task 0 arrives with 1 items/systems") and
       event(log, "12.1667", "Put back replacement item <TEACH-SRU-01,0,0> to stock"),
       "depot DP0 transported to base in two hours")
    ck(event(log, "10.1667", "<TEACH-SRU-01,0,DEPOT-01,0> reorder task 0 started, reorder time: 1") and
       event(log, "11.1667", "<TEACH-SRU-01,0,DEPOT-01,0> reorder task 0 completed, total time was 1") and
       event(log, "11.1667", "Put back replacement item <TEACH-SRU-01,0,6> to stock"),
       "one new DP6 arrives from depot reorder in one hour")
    expected_levels = {
        ("TEACH-SRU-01", "DEPOT-01"): [2, 1, 2],
        ("TEACH-SRU-01", "BASE-01"): [1, 0, 1],
        ("TEACH-LRU-01", "BASE-01"): [1, 0, 1]}
    for (item, station), expected in expected_levels.items():
        observed = [int(x) for x in re.findall(
            rf"Stock at: <{item},0,{station},0> Level: (\d+)", log)]
        ck(observed == expected, f"physical stock levels {item}/{station}")
    for j, start in ((0, "8"), (1, "20"), (2, "32")):
        mission = f"<BASIC-MISSION,TEACH-UNIT,0,0,{j}>"
        ck(event(log, start, f"{mission} mission starting, duration: 2") and
           (event(log, str(int(start)+2), f"{mission} mission success:") if j else
            event(log, "9.8829", f"{mission} mission aborted:")), f"mission outcome {j}")
    ck(event(log, "34", "systems ready: 1 :<TEACH-AIR-01,0>") and
       "Backorder added" not in log and log.count("mission success:") == 2,
       "terminal ready, two successes and no backlog")


def report() -> None:
    r = tables(RUN / "report-raw.json", "report")
    ck(set(r) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"},
       "report table set")
    summary = records(r["ResultSummary"])[0]
    ck(summary["NREP"] == 1 and summary["RTIUP"] == 36 and
       all(near(summary[k], v) for k, v in
           {"MTMF": 1, "STMF": 1, "MSTF": 1, "MSUF": 2/3}.items()), "report summary")
    system, stock = records(r["SystemResults"]), records(r["StockTotalResults"])
    ck(len(system) == len(stock) == 72, "72 half-hour report bins")
    for i, (s, t) in enumerate(zip(system, stock)):
        h = i/2
        prep = int(7 <= h < 8 or 19 <= h < 20 or 31 <= h < 32)
        mission = int(8 <= h < 10 or 20 <= h < 22 or 32 <= h < 34)
        repair = int(h == 10)
        ready = int(h < 7 or 10.5 <= h < 19 or 22 <= h < 31 or h >= 34)
        expected_system = {"NSYRY": ready, "NSYMA": prep+mission, "NSYMO": mission,
                           "NSYMR": prep, "NSYUA": repair, "NSYA": ready+prep+mission,
                           "FTMO": mission, "NSYRP": repair, "NREPT": int(h == 10.5),
                           "NFAIL": int(h == 9.5), "STACC": mission,
                           "SYDT": .5 if h == 10 else None, "NSYDT": int(h == 10)}
        expected_stock = {"PNB": 1, "NDF": int(h == 10), "NWT": int(h == 10)}
        ck((s["STINT"], s["ETINT"], t["STINT"], t["ETINT"]) ==
           (h, h+.5, h, h+.5), f"bin times {i}")
        ck(s["UNID"] == "Total over all Units" and s["SID"] == "Total over all Systems",
           f"report labels {i}")
        for key, value in s.items():
            if key in ("UNID", "SID", "STINT", "ETINT"):
                continue
            target = expected_system.get(key, 0)
            ck(value is None if target is None else near(value, target), f"system {key} bin {i}")
        for key, value in t.items():
            if key in ("STINT", "ETINT"):
                continue
            target = (None if key in ("NBOU", "WTS") or
                      (key in ("ROS", "ROST", "WT", "WTT") and h != 10)
                      else expected_stock.get(key, 0))
            ck(value is None if target is None else near(value, target), f"stock {key} bin {i}")
    ck(system[-1]["NSYRY"] == 1 and stock[-1]["PNB"] == 1 and stock[-1]["NBO"] == 0,
       "terminal report ready/no backorder")


def main() -> None:
    src = source()
    log = native(src)
    events(log)
    report()
    result = {"schema": "simlox-g01-var03-independent-review/v1",
              "passed": not failures, "verdict": "GO" if not failures else "NO-GO",
              "check_count": checks, "failure_count": len(failures), "failures": failures,
              "observed": {"discarded_dp_id": 5, "base_issued_dp_id": 2,
                           "depot_to_base_dp_id": 0, "depot_reorder_dp_id": 6,
                           "reorder_lead_hours": 1, "transport_hours": 2,
                           "terminal_dp_base_stock": 1, "terminal_dp_depot_stock": 2},
              "scope": "One seed, one discarded nested DP, one base and depot, one-hour reorder and two-hour transport in a 36-hour native run.",
              "limits": ["The aggregate report's NDF=1 should not be read as a count of every physical LRU and DP issue; those movements are separately established by typed event identities.",
                         "No DU primary-item behavior, alternative reorder policy/lead time, GUI simulation, or cross-engine result is established."]}
    OUT.write_bytes((json.dumps(result, indent=2)+"\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks": checks, "failures": failures}))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
