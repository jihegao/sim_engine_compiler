"""Independent standard-library replay of G01.var03 primary DU evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
AIR = CASE.parent
PARENT_CASE = AIR / "E01-local-spare-explicit-replacement-v1.0.0"
PARENT = PARENT_CASE / "native-input.json"
RUN = CASE / "runs/g01-var03-du-v100-ssh-20261001-01"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
OUT = CASE / "review/independent-readonly-2026-10-01.json"
checks = 0
failures: list[str] = []


def ck(ok: bool, label: str) -> None:
    global checks
    checks += 1
    if not ok:
        failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(re.sub(r",(?=\s*[}\]])", "", path.read_text(encoding="utf-8-sig")))


def tables(path: Path, root: str) -> dict:
    return {t["name"]: t for t in load(path)[root]["tables"]}


def rows(table: dict) -> list:
    return [row for inst in table["instances"] for row in inst["rows"]]


def records(table: dict) -> list[dict]:
    keys = [col["name"] for col in table["columns"]]
    return [dict(zip(keys, row)) for row in rows(table)]


def at(log: str, time: str, token: str) -> bool:
    return any(line.startswith(f"Time: {time} ") and token in line for line in log.splitlines())


def near(x, y, eps=1e-5) -> bool:
    return isinstance(x, (float, int)) and abs(x-y) <= eps


def source() -> dict:
    contract, diff = load(CASE / "contract.json"), load(CASE / "exact-diff.json")
    path = CASE / "native-input.json"
    ck(sha(PARENT) == contract["parent"]["input_sha256"], "accepted E01 parent SHA")
    ck((PARENT_CASE / "cli-scope-signoff-2026-09-29.md").is_file(), "accepted E01 signoff")
    ck(sha(MANUAL) == contract["source"]["manual_pdf_sha256"], "installed manual SHA")
    ck(sha(DICTIONARY) == contract["source"]["dictionary_sha256"], "installed dictionary SHA")
    ck(sha(path) == contract["native_input_sha256"], "frozen DU source SHA")
    p, c = tables(PARENT, "model"), tables(path, "model")
    changed = {name for name in p if c.get(name) != p[name]}
    expected = {"ProblemDescription", "Item", "ItemRepair", "ItemStructure",
                "Station", "StationStructure", "StockAllocation", "ItemReorder"}
    ck(set(p) == set(c) and changed == expected == set(diff["changed_tables"]),
       "exact eight-table parent delta")
    ck(diff["parent_sha256"] == sha(PARENT) and diff["child_sha256"] == sha(path) and
       diff["unchanged_tables"] == len(p)-8, "exact-diff fingerprints")
    for name, table in p.items():
        if name in changed:
            ck(diff["changes"][name]["before"] == rows(table) and
               diff["changes"][name]["after"] == rows(c[name]) and
               table["columns"] == c[name]["columns"], f"exact changed table {name}")
        else:
            ck(table == c[name], f"invariant parent table {name}")
    ck(records(c["ProblemDescription"])[0]["PDESC"] ==
       "G01.var03 primary DU discard and depot reorder", "description")
    item = records(c["Item"])[0]
    parent_item = records(p["Item"])[0]
    ck({k for k in item if item[k] != parent_item[k]} == {"IID", "DESCR", "TYPE"} and
       item["IID"] == "TEACH-DU-01" and item["TYPE"] == "DU" and
       item["FRT"] == parent_item["FRT"] == 300000, "primary DU item/unchanged rate")
    ck(not rows(c["ItemRepair"]) and len(rows(p["ItemRepair"])) == 1, "no DU repair source row")
    struct, pstruct = records(c["ItemStructure"])[0], records(p["ItemStructure"])[0]
    ck({k for k in struct if struct[k] != pstruct[k]} == {"IID"} and
       struct["IID"] == "TEACH-DU-01" and struct["MID"] == "TEACH-AIR-01" and
       struct["QTYPM"] == 1, "primary DU system position")
    station = records(c["Station"])
    ck(station[:-1] == records(p["Station"]) and
       {k: v for k, v in station[-1].items() if v is not None} ==
       {"STID": "DEPOT-01", "DESCR": "Teaching reorder depot", "QTY": 1, "TYPE": "DEPOT"},
       "depot station source")
    route = records(c["StationStructure"])
    ck(route[:-1] == records(p["StationStructure"]) and
       {k: v for k, v in route[-1].items() if v is not None} ==
       {"STID": "BASE-01", "MSTID": "DEPOT-01", "TFRMS": 2, "TTOMS": 2,
        "DFRAC": 1, "OPOL": "FAST"}, "two-hour depot route")
    reorder = records(c["ItemReorder"])
    ck(reorder[:-1] == records(p["ItemReorder"]) and
       {k: v for k, v in reorder[-1].items() if v is not None} ==
       {"IID": "TEACH-DU-01", "STID": "DEPOT-01", "LEADT": 1}, "DU depot reorder")
    stock = records(c["StockAllocation"])
    ck(len(stock) == 2 and
       [{k: v for k, v in rec.items() if v is not None} for rec in stock] ==
       [{"POINT": "AIR_BASIC", "IID": "TEACH-DU-01", "STID": "BASE-01", "STSIZ": 1},
        {"POINT": "AIR_BASIC", "IID": "TEACH-DU-01", "STID": "DEPOT-01",
         "STSIZ": 2, "ROSIZ": 1}], "base/depot DU stock source")
    ck(len([name for name, table in c.items() if rows(table)]) == 21, "21 populated source tables")
    return c


def native(src: dict) -> str:
    inv, closure, steps = (load(RUN / f) for f in ("invocation.json", "closure.json", "steps.json"))
    ck(inv["run_id"] == closure["run_id"] == RUN.name and closure["error"] is None,
       "run identity/closure")
    ck(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation seal")
    ck(inv["input_sha256"] == sha(CASE / "native-input.json") == sha(RUN / "input.json") and
       inv["parent_sha256"] == sha(PARENT) and inv["contract_sha256"] == sha(CASE / "contract.json"),
       "run source/parent/contract pins")
    ck(inv["session_id"] == 0 and inv["execution_mode"] == "ssh_cli_v1" and
       inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"], "session0 SSH")
    ck(inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
       inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, "queue/GUI guard")
    ck(inv["source_hashes_before"] == closure["source_hashes_before"] ==
       closure["source_hashes_after"], "source stable during native run")
    for key, path in {"input": CASE / "native-input.json", "parent": PARENT,
                      "contract": CASE / "contract.json", "builder": CASE / "build.py",
                      "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1"}.items():
        ck(inv["source_hashes_before"].get(key) == sha(path), f"source seal {key}")
    ck(inv["source_hashes_before"]["simlox_exe"] ==
       "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0", "runtime seal")
    for name, meta in closure["raw"].items():
        f = RUN / name
        ck(f.is_file() and f.stat().st_size == meta["bytes"] and sha(f) == meta["sha256"],
           f"raw seal {name}")
    ck([s["name"] for s in steps] ==
       ["import", "export", "calc", "jsonreport", "check_import_export"], "five guarded steps")
    for step in steps:
        ck(step["exit_code"] == 0 and step["status"] == "completed" and
           step["gui_preserved"] and step["error"] is None, f"step {step['name']}")
    export = tables(RUN / "roundtrip-raw.json", "model")
    for name, table in src.items():
        if rows(table):
            ck(name in export and export[name]["columns"] == table["columns"] and
               rows(export[name]) == rows(table), f"native roundtrip {name}")
    runlog = (RUN / "run.log").read_text(errors="replace")
    ck("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and
       "warning #108" in runlog and "error #" not in runlog.lower(), "zero converter errors")
    ck((RUN / "model.sxo").stat().st_size > 100000, "usable SXO")
    return (RUN / "model.log").read_text(errors="replace")


def events(log: str) -> None:
    ck("Stock at: <TEACH-DU-01,0,DEPOT-01,0> Level: 2 Items:<TEACH-DU-01,0,0>,<TEACH-DU-01,0,1>" in log and
       "Stock at: <TEACH-DU-01,0,BASE-01,0> Level: 1 Items:<TEACH-DU-01,0,2>" in log,
       "opening DU physical stocks")
    ck(at(log, "9.8829", "critical random failure added") and
       "subitem failed: <TEACH-DU-01,0,3>" in log and
       at(log, "9.8829", "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted:"),
       "installed DU3 critical failure/mission abort")
    ck(at(log, "10", "Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is <TEACH-DU-01,0,3>") and
       at(log, "10", "Take replacement item <TEACH-DU-01,0,2> from stock"),
       "base DU2 issued for installed DU3")
    ck(at(log, "10", "remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> starts performing, planned to last for 0.166667 hours") and
       at(log, "10.1667", "fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> starts performing, planned to last for 0.333333 hours") and
       at(log, "10.5", "system SURP task 0 on <TEACH-AIR-01,0> completed"),
       "explicit ten-minute remove/twenty-minute fit")
    ck(at(log, "10.1667", "Item discarded: <TEACH-DU-01,0,3>") and
       "item DIRP task" not in log and "item SURP task" not in log and
       "Put back replacement item <TEACH-DU-01,0,3>" not in log,
       "removed DU3 discarded, not repaired/stocked")
    ck(at(log, "10", "Take replacement item <TEACH-DU-01,0,0> from stock") and
       at(log, "10", "transport task 0 starts with 1 items/systems, transport time: 2") and
       at(log, "12", "transport task 0 arrives with 1 items/systems") and
       at(log, "12", "Put back replacement item <TEACH-DU-01,0,0> to stock"),
       "depot DU0 reaches base in two hours")
    ck(at(log, "10", "<TEACH-DU-01,0,DEPOT-01,0> reorder task 0 started, reorder time: 1") and
       at(log, "11", "<TEACH-DU-01,0,DEPOT-01,0> reorder task 0 completed, total time was 1") and
       at(log, "11", "Put back replacement item <TEACH-DU-01,0,4> to stock"),
       "new DU4 arrives at depot after one-hour reorder")
    for station, levels in (("BASE-01", [1, 0, 1]), ("DEPOT-01", [2, 1, 2])):
        found = [int(x) for x in re.findall(
            rf"Stock at: <TEACH-DU-01,0,{station},0> Level: (\d+)", log)]
        ck(found == levels, f"{station} physical stock sequence")
    for j, start in ((0, "8"), (1, "20"), (2, "32")):
        mission = f"<BASIC-MISSION,TEACH-UNIT,0,0,{j}>"
        ck(at(log, start, f"{mission} mission starting, duration: 2") and
           (at(log, str(int(start)+2), f"{mission} mission success:") if j else
            at(log, "9.8829", f"{mission} mission aborted:")), f"mission outcome {j}")
    ck(at(log, "34", "systems ready: 1 :<TEACH-AIR-01,0>") and
       "Backorder added" not in log and log.count("mission success:") == 2,
       "terminal ready/no backorder/two successes")


def report() -> None:
    report = tables(RUN / "report-raw.json", "report")
    ck(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"},
       "report table set")
    summary = records(report["ResultSummary"])[0]
    ck(summary["NREP"] == 1 and summary["RTIUP"] == 36 and
       all(near(summary[k], v) for k, v in
           {"MTMF": 1, "STMF": 1, "MSTF": 1, "MSUF": 2/3}.items()), "report summary")
    system, stock = records(report["SystemResults"]), records(report["StockTotalResults"])
    ck(len(system) == len(stock) == 72, "72 System and Stock bins")
    for i, (s, t) in enumerate(zip(system, stock)):
        h = i/2
        prep = int(7 <= h < 8 or 19 <= h < 20 or 31 <= h < 32)
        mission = int(8 <= h < 10 or 20 <= h < 22 or 32 <= h < 34)
        repair = int(h == 10)
        ready = int(h < 7 or 10.5 <= h < 19 or 22 <= h < 31 or h >= 34)
        wanted_s = {"NSYRY": ready, "NSYMA": prep+mission, "NSYMO": mission,
                    "NSYMR": prep, "NSYUA": repair, "NSYA": ready+prep+mission,
                    "FTMO": mission, "NSYRP": repair, "NREPT": int(h == 10.5),
                    "NFAIL": int(h == 9.5), "STACC": mission,
                    "SYDT": .5 if h == 10 else None, "NSYDT": int(h == 10)}
        wanted_t = {"PNB": 1, "NDF": int(h == 10), "NWT": int(h == 10)}
        ck((s["STINT"], s["ETINT"], t["STINT"], t["ETINT"]) ==
           (h, h+.5, h, h+.5), f"bin times {i}")
        ck(s["UNID"] == "Total over all Units" and s["SID"] == "Total over all Systems",
           f"system labels {i}")
        for key, value in s.items():
            if key in ("UNID", "SID", "STINT", "ETINT"):
                continue
            target = wanted_s.get(key, 0)
            ck(value is None if target is None else near(value, target), f"system {key} bin {i}")
        for key, value in t.items():
            if key in ("STINT", "ETINT"):
                continue
            target = (None if key in ("NBOU", "WTS") or
                      (key in ("ROS", "ROST", "WT", "WTT") and h != 10)
                      else wanted_t.get(key, 0))
            ck(value is None if target is None else near(value, target), f"stock {key} bin {i}")
    ck(system[-1]["NSYRY"] == 1 and stock[-1]["PNB"] == 1 and stock[-1]["NBO"] == 0,
       "terminal report ready/no backorder")


def main() -> None:
    src = source()
    log = native(src)
    events(log)
    report()
    result = {"schema": "simlox-g01-var03-du-independent-review/v1",
              "passed": not failures, "verdict": "GO" if not failures else "NO-GO",
              "check_count": checks, "failure_count": len(failures), "failures": failures,
              "observed": {"discarded_du_id": 3, "base_issued_du_id": 2,
                           "depot_to_base_du_id": 0, "depot_reorder_du_id": 4,
                           "reorder_lead_hours": 1, "transport_hours": 2,
                           "terminal_du_base_stock": 1, "terminal_du_depot_stock": 2},
              "scope": "One fixed-seed 36-hour run of a primary DU with base spare, depot reorder and two-hour transport.",
              "limits": ["This tests one primary DU alone; the accepted secondary DP case is separate and no combined DU/DP structure is demonstrated.",
                         "Report NDF=1 is an aggregate metric and does not enumerate all physical base and depot movements; those are traced by item IDs in the event log.",
                         "Other inventory policies, stations, seeds, GUI simulation and cross-engine parity remain unverified."]}
    OUT.write_bytes((json.dumps(result, indent=2)+"\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks": checks, "failures": failures}))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
