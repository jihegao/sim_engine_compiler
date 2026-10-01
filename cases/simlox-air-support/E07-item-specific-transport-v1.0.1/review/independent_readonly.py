"""Independent standard-library replay of the sealed E07 v1.0.1 CLI run."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
AIR = CASE.parent
RUN = CASE / "runs" / "e07-item-route-v101-20261001-01"
PARENT = AIR / "E04-upstream-transport-fast-v1.0.0"
CONTROL = PARENT / "runs" / "e04-fast-v100-ssh-20260929-01"
OLD = AIR / "E07-item-specific-transport-v1.0.0" / "runs" / "e07-item-route-v100-20261001-01"
DICT = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
OUT = CASE / "review" / "independent-readonly-2026-10-01.json"
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


def tab(path: Path, root: str) -> dict:
    return {t["name"]: t for t in load(path)[root]["tables"]}


def rows(t: dict) -> list:
    return [r for i in t["instances"] for r in i["rows"]]


def records(t: dict) -> list[dict]:
    names = [c["name"] for c in t["columns"]]
    return [dict(zip(names, r)) for r in rows(t)]


def near(a, b, tol=1e-5) -> bool:
    return isinstance(a, (int, float)) and abs(a - b) <= tol


def line(log: str, time: str, phrase: str) -> bool:
    return any(s.startswith(f"Time: {time} ") and phrase in s for s in log.splitlines())


def main() -> None:
    contract = load(CASE / "contract.json")
    source = CASE / "native-input.json"
    parent = PARENT / "native-input.json"
    diff = load(CASE / "exact-diff.json")
    ck(sha(source) == contract["input_sha256"], "frozen child input")
    ck(sha(parent) == contract["parent_sha256"], "accepted E04 parent")
    ck(sha(DICT) == contract["table_dictionary_sha256"], "installed dictionary")
    ck(sha(MANUAL) == contract["manual_pdf_sha256"], "installed manual")
    p, c = tab(parent, "model"), tab(source, "model")
    ck(set(c) - set(p) == {"ItemStationStructure"} and not set(p) - set(c), "one added table")
    changed = {n for n in c if n not in p or c[n] != p[n]}
    ck(changed == set(diff) == {"ProblemDescription", "ItemStationStructure"}, "exact two-table source delta")
    for name in changed:
        pair = diff[name]
        ck(pair["parent_columns"] == (p[name]["columns"] if name in p else None) and
           pair["child_columns"] == c[name]["columns"] and
           pair["parent_rows"] == (rows(p[name]) if name in p else None) and
           pair["child_rows"] == rows(c[name]), f"source diff {name}")
    ck([col["name"] for col in c["ItemStationStructure"]["columns"]] ==
       ["IID", "STID", "MSTID", "TFRMS", "TTOMS", "CFRMS", "CTOMS", "DFRAC", "OPOL", "PFRMS", "PTOMS", "NOTE"], "full native item-link schema")
    ck(rows(c["ItemStationStructure"]) == [["TEACH-LRU-01", "BASE-01", "DEPOT-01", 1, 3, None, None, 1, "FAST", None, None, None]], "item route 1h down/3h up")
    ck(rows(c["StationStructure"]) == rows(p["StationStructure"]) and
       rows(c["StationStructure"])[0][2:4] == [2, 2], "general 2h/2h route retained")
    ck(rows(c["StockAllocation"]) == rows(p["StockAllocation"]) and
       rows(c["ItemRepair"]) == rows(p["ItemRepair"]) and
       rows(c["OperationProfile"]) == rows(p["OperationProfile"]), "stock/repair/missions retained")

    inv, closure = load(RUN / "invocation.json"), load(RUN / "closure.json")
    ck(inv["run_id"] == closure["run_id"] == RUN.name and closure["error"] is None, "run identity and closure")
    ck(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation seal")
    ck(inv["input_sha256"] == sha(source) == sha(RUN / "input.json"), "run input seal")
    ck(inv["parent_sha256"] == sha(parent) and inv["contract_sha256"] == sha(CASE / "contract.json"), "run parent/contract seals")
    ck(inv["session_id"] == 0 and inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"], "session0 SSH")
    ck(inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, "mutex and GUI identity")
    ck(inv["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"], "source unchanged across run")
    pinned = {"input": source, "parent": parent, "table_dictionary": DICT, "contract": CASE / "contract.json",
              "builder": CASE / "build.py", "exact_diff": CASE / "exact-diff.json",
              "diff_checker": CASE / "describe_diff.py", "checker": CASE / "check_roundtrip.py",
              "runner_script": CASE / "run_native_ssh.ps1"}
    for key, path in pinned.items():
        ck(inv["source_hashes_before"].get(key) == sha(path), f"source seal {key}")
    ck(inv["source_hashes_before"]["simlox_exe"] == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0", "native exe seal")
    for name, meta in closure["raw"].items():
        path = RUN / name
        ck(path.is_file() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"], f"raw seal {name}")
    steps = load(RUN / "steps.json")
    ck([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], "five-step workflow")
    for step in steps:
        ck(step["exit_code"] == 0 and step["status"] == "completed" and step["gui_preserved"] and step["error"] is None, f"step {step['name']}")
    export = tab(RUN / "roundtrip-raw.json", "model")
    populated = {n for n, t in c.items() if rows(t)}
    ck(len(populated) == 22, "22 row-containing source tables")
    for name in populated:
        ck(name in export and c[name]["columns"] == export[name]["columns"] and rows(c[name]) == rows(export[name]), f"exact roundtrip {name}")
    runlog = (RUN / "run.log").read_text(errors="replace")
    ck("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and "warning #108" in runlog, "zero errors/known warning")
    ck((RUN / "model.sxo").stat().st_size > 100000, "usable SXO")
    old_result = load(OLD / "roundtrip-validation.json")
    ck(old_result["passed"] is False and old_result["differences"] == ["roundtrip changed ItemStationStructure"], "excluded v1.0.0 diagnostic")
    ck(sha(OLD / "closure.json") == "311e5af8fe0ceca2425c0ee543421ebf52dd4568241e7d6fd967832a1b36ad00" and
       load(OLD / "closure.json")["error"] == "roundtrip checker exit=1", "excluded diagnostic closure")
    ck(sha(RUN / "model.log") == sha(OLD / "model.log") and sha(RUN / "report-raw.json") == sha(OLD / "report-raw.json"), "null-column revision leaves business output identical")

    log = (RUN / "model.log").read_text(errors="replace")
    base_log = (CONTROL / "model.log").read_text(errors="replace")
    ck(sha(CONTROL / "model.log") == "7df3278befbc1f8da8051d3024eedfebb321ee40ec1595992a808391ca0561a2" and
       sha(CONTROL / "report-raw.json") == "3284c19ccce1237ca651cd50c6c0fb3320e9ed914a77f61c75cb4830e624c376", "accepted E04 control raw seals")
    ck(line(log, "9.8829", "mission aborted:") and line(log, "10", "aborted mission completed:"), "first mission failure/return")
    ck(line(log, "10", "Item demand arrives from pos <TEACH-AIR-01,BASE-01,0>") and
       line(log, "10", "Backorder added") and line(log, "10", "<TEACH-LRU-01,0,DEPOT-01,0> Item demand arrives"), "FAST demand and local backorder")
    ck(line(log, "10", "Take replacement item <TEACH-LRU-01,0,0> from stock") and
       log.count("Take replacement item <TEACH-LRU-01,0,0> from stock") == 1, "one depot spare issued")
    ck(line(log, "10", "transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>>") and
       line(log, "10", "transport task 0 starts with 1 items/systems, transport time: 1") and
       line(log, "11", "transport task 0 arrives with 1 items/systems"), "spare 0 depot-to-base one hour")
    ck(line(base_log, "10", "transport task 0 starts with 1 items/systems, transport time: 2") and
       line(base_log, "12", "transport task 0 arrives with 1 items/systems"), "E04 spare two-hour control")
    ck(line(log, "10.1667", "remove subitem subtask 0 seqno 1") and
       line(log, "10.1667", "<TEACH-LRU-01,0,BASE-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,1>"), "failed item 1 removal")
    ck(line(log, "10.1667", "transport request <<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>>") and
       line(log, "10.1667", "transport task 2 starts with 1 items/systems, transport time: 3") and
       line(log, "13.1667", "transport task 2 arrives with 1 items/systems"), "faulty item 1 base-to-depot three hours")
    ck(line(base_log, "10.1667", "transport task 2 starts with 1 items/systems, transport time: 2") and
       line(base_log, "12.1667", "transport task 2 arrives with 1 items/systems"), "E04 faulty-item two-hour control")
    ck(line(log, "11", "Backorder removed, waiting time was 1") and
       line(log, "11", "Replacement item arrives <TEACH-LRU-01,0,0>"), "one-hour backorder clearance")
    ck(line(log, "11", "fit subitem subtask 1 seqno 2") and
       line(log, "11.3333", "System ready <TEACH-AIR-01,0>"), "fit and aircraft readiness")
    ck(line(log, "13.1667", "Start repair of item <TEACH-LRU-01,0,1>") and
       line(log, "14.1667", "Finished repair of item <TEACH-LRU-01,0,1>"), "depot one-hour repair")
    ck(line(log, "22", "<BASIC-MISSION,TEACH-UNIT,0,0,1> mission success:") and
       line(log, "34", "<BASIC-MISSION,TEACH-UNIT,0,0,2> mission success:"), "later two missions succeed")
    ck(log.count("Take replacement item <TEACH-LRU-01") == 1 and
       line(log, "14.1667", "Put back replacement item <TEACH-LRU-01,0,1> to stock"), "no duplicate issue/repair return")
    levels = {station: [int(m.group(1)) for m in re.finditer(
        rf"Stock at: <TEACH-LRU-01,0,{station},0> Level: (\d+)", log)]
        for station in ("BASE-01", "DEPOT-01")}
    ck(levels == {"BASE-01": [0], "DEPOT-01": [1, 0, 1]}, "physical station stock conservation")
    ck(log.count("Backorder added") == log.count("Backorder removed") == 1, "one local backorder lifecycle")
    ck(line(log, "34", "systems ready: 1 :<TEACH-AIR-01,0>") and
       "Stock at: <TEACH-LRU-01,0,DEPOT-01,0> Level: 1 Items:<TEACH-LRU-01,0,1>" in log and
       "Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 0 Items:" in log, "terminal ready and item stock identities")

    report = tab(RUN / "report-raw.json", "report")
    control_report = tab(CONTROL / "report-raw.json", "report")
    ck(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "four report tables")
    summary = records(report["ResultSummary"])[0]
    ck(summary["NREP"] == 1 and summary["RTIUP"] == 36 and all(near(summary[k], v) for k, v in
       {"MTMF": 1, "MSTF": 1, "MSUF": 2/3, "STMF": 1}.items()), "summary factors")
    ck(records(report["ResultSummary"]) == records(control_report["ResultSummary"]), "summary parity with E04")
    sys, stock = records(report["SystemResults"]), records(report["StockTotalResults"])
    ck(len(sys) == len(stock) == 72, "72 half-hour report bins")
    null_sys = set()
    null_stock = {"NBOU"}
    transient_stock = {"ROS", "ROST", "WT", "WTT", "WTS"}
    for i, (s, t) in enumerate(zip(sys, stock)):
        h = i / 2
        prep = int(7 <= h < 8 or 19 <= h < 20 or 31 <= h < 32)
        mission = int(8 <= h < 10 or 20 <= h < 22 or 32 <= h < 34)
        ready = 1 if h < 7 or 11.5 <= h < 19 or 22 <= h < 31 or 34 <= h else (1/3 if h == 11 else 0)
        active = ready + prep + mission
        expected_sys = {"NSYRY": ready, "NSYMA": prep + mission, "NSYMO": mission,
                        "NSYMR": prep, "NSYUA": 1 if h in (10, 10.5) else (2/3 if h == 11 else 0),
                        "NSYA": active, "FTMO": mission,
                        "NSYRP": 1/3 if h == 10 else (2/3 if h == 11 else 0),
                        "NSYWI": 2/3 if h == 10 else (1 if h == 10.5 else 0),
                        "NREPT": int(h == 11), "NFAIL": int(h == 9.5), "STACC": mission,
                        "SYDT": 4/3 if h == 10 else 0, "NSYDT": int(h == 10)}
        expected_stock = {"NBO": int(h in (10, 10.5)), "PNB": int(h not in (10, 10.5)),
                          "NDF": int(h == 10), "NWT": int(h == 10)}
        ck((s["STINT"], s["ETINT"], t["STINT"], t["ETINT"]) == (h, h+.5, h, h+.5), f"bin times {i}")
        ck(s["UNID"] == "Total over all Units" and s["SID"] == "Total over all Systems", f"system labels {i}")
        for name, value in s.items():
            if name in ("UNID", "SID", "STINT", "ETINT"):
                continue
            target = None if name in null_sys or (name == "SYDT" and h != 10) else expected_sys.get(name, 0)
            ck(value is None if target is None else near(value, target), f"system {name} bin {i}")
        for name, value in t.items():
            if name in ("STINT", "ETINT"):
                continue
            target = None if name in null_stock or (name in transient_stock and h != 10) else (1 if name in transient_stock else expected_stock.get(name, 0))
            ck(value is None if target is None else near(value, target), f"stock {name} bin {i}")
    ck(sys[-1]["NSYRY"] == 1 and stock[-1]["PNB"] == 1 and stock[-1]["NBO"] == 0, "terminal report")
    base_sys, base_stock = records(control_report["SystemResults"]), records(control_report["StockTotalResults"])
    ck(near(sys[20]["SYDT"], base_sys[20]["SYDT"] - 1) and
       near(stock[20]["WT"], base_stock[20]["WT"] - 1), "one-hour downtime/backorder reduction vs E04")

    result = {"schema": "simlox-e07-v101-independent-review/v1", "passed": not failures,
              "verdict": "GO" if not failures else "NO-GO", "check_count": checks,
              "failure_count": len(failures), "failures": failures,
              "scope": "One fixed-seed item-specific FAST BASE-01/DEPOT-01 link, TFRMS=1 and TTOMS=3, relative to accepted E04 2/2 control.",
              "excluded_diagnostic": "E07 v1.0.0 run completed simulation/report but failed exact ItemStationStructure roundtrip because two null native columns were omitted.",
              "limits": ["One IID, one support link, DFRAC=1; no route selection or fractional sampling.",
                         "No CM/PM/SystemStationStructure precedence, SLOW policy, profile transport, contention, GUI rendering, or cross-engine parity.",
                         "Station-specific stock identity is supplied by native events; StockTotalResults is aggregate."]}
    OUT.write_bytes((json.dumps(result, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks": checks, "failures": failures, "report": str(OUT)}))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
