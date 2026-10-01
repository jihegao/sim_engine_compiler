"""Independent read-only replay of the sealed G01.var01 v1.0.1 native run."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
AIR = CASE.parent
RUN = CASE / "runs" / "g01-var01-v101-ssh-20261001-01"
OLD = AIR / "G01-var01-lru-sru-v1.0.0"
OLD_RUN = OLD / "runs" / "g01-var01-v100-ssh-20261001-01"
PARENT = AIR / "E01-local-spare-explicit-replacement-v1.0.0" / "native-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
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


def tables(path: Path, key: str) -> dict:
    return {t["name"]: t for t in load(path)[key]["tables"]}


def rows(t: dict) -> list:
    return [r for i in t["instances"] for r in i["rows"]]


def records(t: dict) -> list[dict]:
    keys = [c["name"] for c in t["columns"]]
    return [dict(zip(keys, r)) for r in rows(t)]


def near(a, b, tol=1e-5) -> bool:
    return isinstance(a, (float, int)) and abs(a - b) <= tol


def event(log: str, when: str, phrase: str) -> bool:
    return any(s.startswith(f"Time: {when} ") and phrase in s for s in log.splitlines())


def main() -> None:
    contract = load(CASE / "contract.json")
    source = CASE / "native-input.json"
    ck(sha(PARENT) == contract["parent"]["input_sha256"], "accepted E01 parent hash")
    ck(sha(source) == contract["native_input_sha256"], "frozen child hash")
    ck(sha(MANUAL) == contract["source"]["manual_pdf_sha256"], "manual hash")
    ck(sha(DICTIONARY) == contract["source"]["installed_dictionary_sha256"], "dictionary hash")
    p, c = tables(PARENT, "model"), tables(source, "model")
    ck(set(c) == set(p), "same source tables")
    ck({n for n in c if c[n] != p[n]} == set(contract["delta"]["tables"]), "exact six-table parent delta")
    item = records(c["Item"])
    structure = records(c["ItemStructure"])
    repair = records(c["ItemRepair"])
    replacement = records(c["ItemReplacement"])
    stock_source = records(c["StockAllocation"])
    ck([(r["IID"], r["FRT"], r["OPID"], r["TYPE"], r["CRIT"]) for r in item] ==
       [("TEACH-LRU-01", 300000, "OPHOURS", "LRU", 1),
        ("TEACH-SRU-01", 300000, "OPHOURS", "SRU", 1)], "matched parent/child failure rates and types")
    ck([(r["IID"], r["MID"], r["QTYPM"], r["ENVF"]) for r in structure] ==
       [("TEACH-LRU-01", "TEACH-AIR-01", 1, 1),
        ("TEACH-SRU-01", "TEACH-LRU-01", 1, 1)], "two-level hierarchy")
    ck([(r["IID"], r["STID"], r["DIRPT"], r["SURPT"]) for r in repair] ==
       [("TEACH-LRU-01", "BASE-01", 1, 1.5),
        ("TEACH-SRU-01", "BASE-01", 1, 0)], "local LRU SURP/SRU DIRP")
    ck([(r["MID"], r["IID"], r["STID"], r["SURPT"]) for r in replacement] ==
       [("TEACH-LRU-01", "TEACH-SRU-01", "BASE-01", .75)], "explicit SRU replacement")
    old_tables = tables(OLD / "native-input.json", "model")
    ck({n for n in c if c[n] != old_tables[n]} == {"ItemRepair"} and
       records(old_tables["ItemRepair"])[0]["SURPT"] == .75 and
       repair[0]["SURPT"] == 1.5, "v1.0.1 isolates general SURPT 0.75-to-1.5")
    ck([(r["IID"], r["STID"], r["STSIZ"]) for r in stock_source] ==
       [("TEACH-LRU-01", "BASE-01", 1), ("TEACH-SRU-01", "BASE-01", 1)], "one local spare of each type")
    ck(c["SystemRepair"] == p["SystemRepair"] and c["TaskBreakDown"] == p["TaskBreakDown"] and
       c["OperationProfile"] == p["OperationProfile"], "inherited system task and mission schedule")

    inv, closure = load(RUN / "invocation.json"), load(RUN / "closure.json")
    ck(inv["run_id"] == closure["run_id"] == RUN.name and closure["error"] is None, "run identity/closure")
    ck(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation seal")
    ck(inv["input_sha256"] == sha(source) == sha(RUN / "input.json") and
       inv["parent_sha256"] == sha(PARENT) and inv["contract_sha256"] == sha(CASE / "contract.json"), "run source pins")
    ck(inv["session_id"] == 0 and inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"], "session0 SSH")
    ck(inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and
       inv["gui"]["session_id"] > 0, "mutex/GUI identity")
    ck(inv["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"], "source stable")
    pinned = {"input": source, "parent": PARENT, "contract": CASE / "contract.json",
              "builder": CASE / "build.py", "checker": CASE / "check_roundtrip.py",
              "runner_script": CASE / "run_native_ssh.ps1"}
    for key, path in pinned.items():
        ck(inv["source_hashes_before"].get(key) == sha(path), f"frozen {key}")
    ck(inv["source_hashes_before"]["simlox_exe"] == "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0", "runtime hash")
    for name, meta in closure["raw"].items():
        path = RUN / name
        ck(path.is_file() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"], f"raw {name}")
    steps = load(RUN / "steps.json")
    ck([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], "five recorded steps")
    for step in steps:
        ck(step["exit_code"] == 0 and step["status"] == "completed" and step["gui_preserved"] and step["error"] is None, f"step {step['name']}")
    export = tables(RUN / "roundtrip-raw.json", "model")
    populated = {n for n, t in c.items() if rows(t)}
    ck(len(populated) == 21, "21 populated business tables")
    for name in populated:
        ck(name in export and export[name]["columns"] == c[name]["columns"] and rows(export[name]) == rows(c[name]), f"roundtrip {name}")
    runlog = (RUN / "run.log").read_text(errors="replace")
    ck("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and "warning #108" in runlog, "conversion status")
    ck((RUN / "model.sxo").stat().st_size > 100000, "valid SXO")

    log = (RUN / "model.log").read_text(errors="replace")
    ck(sha(RUN / "model.log") == sha(OLD_RUN / "model.log") and
       sha(RUN / "report-raw.json") == sha(OLD_RUN / "report-raw.json"), "observed timing and reports unchanged from v1.0.0")
    ck(event(log, "9.8829", "critical random failure added") and
       event(log, "9.8829", "<BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted:"), "first critical failure/abort")
    ck("subitem failed: <TEACH-LRU-01,0,2> connection path: TEACH-AIR-01 - TEACH-AIR-01 - TEACH-LRU-01" in log and
       event(log, "10.1667", "<TEACH-LRU-01,0,BASE-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,2> from position <TEACH-AIR-01,BASE-01,0> subitem failed: <TEACH-SRU-01,0,3>"), "LRU then nested SRU identity")
    ck(event(log, "10", "<TEACH-LRU-01,0,BASE-01,0> Item demand arrives from pos <TEACH-AIR-01,BASE-01,0>") and
       event(log, "10", "Take replacement item <TEACH-LRU-01,0,1> from stock"), "system demand and LRU spare issue")
    ck(event(log, "10", "remove subitem subtask 0 seqno 1 within system SURP task 0") and
       event(log, "10.1667", "remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> completed") and
       event(log, "10.1667", "fit subitem subtask 1 seqno 2 within system SURP task 0") and
       event(log, "10.5", "system SURP task 0 on <TEACH-AIR-01,0> completed"), "10-minute remove and 20-minute fit")
    ck(event(log, "10.5", "System ready <TEACH-AIR-01,0>"), "aircraft ready after LRU swap")
    ck(event(log, "10.1667", "item SURP task 1 on <TEACH-LRU-01,0,2> started") and
       event(log, "10.1667", "<TEACH-SRU-01,0,BASE-01,0> Item demand arrives from pos <TEACH-LRU-01,0,BASE-01,0>") and
       event(log, "10.1667", "Take replacement item <TEACH-SRU-01,0,0> from stock"), "LRU repair demands stocked SRU")
    ck(event(log, "10.1667", "remove subitem subtask 2 seqno 0 within item SURP task 1") and
       event(log, "10.5417", "remove subitem subtask 2 seqno 0 within item SURP task 1 on <TEACH-LRU-01,0,2> completed") and
       event(log, "10.5417", "fit subitem subtask 3 seqno 1 within item SURP task 1") and
       event(log, "10.9167", "item SURP task 1 on <TEACH-LRU-01,0,2> completed"), "LRU/SRU 0.75-hour replacement")
    ck(event(log, "10.9167", "Put back replacement item <TEACH-LRU-01,0,2> to stock"), "repaired LRU returns")
    ck(event(log, "10.5417", "<TEACH-SRU-01,0,BASE-01,0> Item requiring maintenance arrives <TEACH-SRU-01,0,3>") and
       event(log, "10.5417", "item DIRP task 2 on <TEACH-SRU-01,0,3> started") and
       event(log, "10.5417", "starts performing, planned to last for 1 hours") and
       event(log, "11.5417", "item DIRP task 2 on <TEACH-SRU-01,0,3> completed") and
       event(log, "11.5417", "Put back replacement item <TEACH-SRU-01,0,3> to stock"), "SRU direct repair one hour")
    ck(event(log, "22", "<BASIC-MISSION,TEACH-UNIT,0,0,1> mission success:") and
       event(log, "34", "<BASIC-MISSION,TEACH-UNIT,0,0,2> mission success:"), "later two missions succeed")
    ck(log.count("Backorder added") == 0 and "transport task" not in log, "no backorder/forwarding")
    levels = {typ: [int(m.group(1)) for m in re.finditer(
        rf"Stock at: <{typ},0,BASE-01,0> Level: (\d+)", log)]
        for typ in ("TEACH-LRU-01", "TEACH-SRU-01")}
    ck(levels == {"TEACH-LRU-01": [1, 0, 1], "TEACH-SRU-01": [1, 0, 1]}, "separate LRU/SRU stock conservation")
    ck(log.count("Take replacement item <TEACH-LRU-01") == 1 and
       log.count("Take replacement item <TEACH-SRU-01") == 1, "one issue of each item")
    ck(event(log, "34", "systems ready: 1 :<TEACH-AIR-01,0>"), "terminal aircraft ready")

    report = tables(RUN / "report-raw.json", "report")
    ck(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "report tables")
    summary = records(report["ResultSummary"])[0]
    ck(summary["NREP"] == 1 and summary["RTIUP"] == 36 and all(near(summary[k], v) for k, v in
       {"MTMF": 1, "MSTF": 1, "MSUF": 2/3, "STMF": 1}.items()), "report summary")
    system = records(report["SystemResults"])
    stock = records(report["StockTotalResults"])
    ck(len(system) == len(stock) == 72, "72 half-hour System and Stock bins")
    for i, (s, t) in enumerate(zip(system, stock)):
        h = i / 2
        prep = int(7 <= h < 8 or 19 <= h < 20 or 31 <= h < 32)
        mission = int(8 <= h < 10 or 20 <= h < 22 or 32 <= h < 34)
        ready = int(h < 7 or 10.5 <= h < 19 or 22 <= h < 31 or 34 <= h)
        expected_system = {"NSYRY": ready, "NSYMA": prep + mission, "NSYMO": mission,
                           "NSYMR": prep, "NSYUA": int(h == 10), "NSYA": ready + prep + mission,
                           "FTMO": mission, "NSYRP": int(h == 10), "NREPT": int(h == 10.5),
                           "NFAIL": int(h == 9.5), "STACC": mission,
                           "SYDT": .5 if h == 10 else None, "NSYDT": int(h == 10)}
        expected_stock = {"PNB": 1, "NDF": int(h == 10), "NWT": int(h == 10)}
        ck((s["STINT"], s["ETINT"], t["STINT"], t["ETINT"]) == (h, h+.5, h, h+.5), f"bin times {i}")
        ck(s["UNID"] == "Total over all Units" and s["SID"] == "Total over all Systems", f"report labels {i}")
        for name, value in s.items():
            if name in ("UNID", "SID", "STINT", "ETINT"):
                continue
            target = expected_system.get(name, 0)
            ck(value is None if target is None else near(value, target), f"system {name} bin {i}")
        for name, value in t.items():
            if name in ("STINT", "ETINT"):
                continue
            target = None if name in {"NBOU", "WTS"} or (name in {"ROS", "ROST", "WT", "WTT"} and h != 10) else expected_stock.get(name, 0)
            ck(value is None if target is None else near(value, target), f"stock {name} bin {i}")
    ck(system[-1]["NSYRY"] == 1 and stock[-1]["PNB"] == 1 and stock[-1]["NBO"] == 0, "terminal report state")

    result = {"schema": "simlox-g01-var01-v101-independent-review/v1", "passed": not failures,
              "verdict": "GO" if not failures else "NO-GO", "check_count": checks,
              "failure_count": len(failures), "failures": failures,
              "stock_level_sequences": levels,
              "scope": "One fixed-seed local aircraft→LRU→SRU exchange, with general SURPT=1.5 versus item-specific SURPT=0.75, plus SRU direct repair and 72-bin reports.",
              "limits": ["The critical aircraft failure line first labels the LRU; the SRU is identified when that LRU enters item repair.",
                         "This one matching item-specific replacement demonstrates the 0.75-hour duration despite a 1.5-hour general time; it does not cover other subitems or station/group priority.",
                         "No ASSY, alternative quantities, additional levels, stockout, forwarding, other seeds, GUI rendering or cross-engine parity."]}
    OUT.write_bytes((json.dumps(result, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks": checks, "failures": failures, "report": str(OUT)}))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
