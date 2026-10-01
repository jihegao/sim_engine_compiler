"""Independent read-only replay of the paired G01.var02 PRU native runs."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

LOCAL_CASE = Path(__file__).resolve().parent.parent
AIR = LOCAL_CASE.parent
CASES = {
    "repair": AIR / "G01-var02-pru-partial-repair-v1.0.0",
    "discard": AIR / "G01-var02-pru-discard-reorder-v1.0.0",
}
RUN_IDS = {
    "repair": "g01-var02-pru-v100-ssh-20261001-02",
    "discard": "g01-var02-pru-discard-v100-ssh-20261001-01",
}
PARENT = AIR / "G01-var03-du-discard-reorder-v1.0.0/native-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
OUT = LOCAL_CASE / "review/independent-readonly-2026-10-01.json"
checks = 0
failures: list[str] = []


def ck(ok: bool, label: str) -> None:
    global checks
    checks += 1
    if not ok:
        failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path):
    return json.loads(re.sub(r",(?=\s*[}\]])", "", path.read_text(encoding="utf-8-sig")))


def tables(path: Path, root: str) -> dict:
    return {t["name"]: t for t in read(path)[root]["tables"]}


def rows(table: dict) -> list:
    return [row for inst in table["instances"] for row in inst["rows"]]


def records(table: dict) -> list[dict]:
    keys = [c["name"] for c in table["columns"]]
    return [dict(zip(keys, row)) for row in rows(table)]


def near(actual, expected, tol=2e-4) -> bool:
    return isinstance(actual, (int, float)) and abs(actual-expected) < tol


def event(log: str, time: str, token: str) -> bool:
    return any(line.startswith(f"Time: {time} ") and token in line for line in log.splitlines())


def overlap(start: float, end: float, h: float) -> float:
    return max(0.0, min(end, h+.5)-max(start, h))/.5


def source_review() -> dict[str, dict]:
    p = tables(PARENT, "model")
    result = {}
    for kind, case in CASES.items():
        contract = read(case / "contract.json")
        path = case / "native-input.json"
        ck(sha(PARENT) == contract["parent"]["input_sha256"], f"{kind} DU parent SHA")
        ck(sha(path) == contract["native_input_sha256"], f"{kind} source SHA")
        ck(sha(MANUAL) == contract["source"]["manual_pdf_sha256"], f"{kind} manual SHA")
        ck(sha(DICTIONARY) == contract["source"]["dictionary_sha256"], f"{kind} dictionary SHA")
        c = tables(path, "model")
        changed = {name for name in p if c.get(name) != p[name]}
        expected = {"ProblemDescription", "Item", "ItemRepair", "ItemStructure",
                    "ItemReorder", "StockAllocation"}
        if kind == "discard":
            expected.add("Control")
        ck(set(p) == set(c) and changed == expected, f"{kind} exact parent table delta")
        for name, table in p.items():
            ck(c[name]["columns"] == table["columns"] and
               (name in expected or c[name] == table), f"{kind} source table {name}")
        ck(records(c["ProblemDescription"])[0]["PDESC"] ==
           "G01.var02 primary PRU partial repair and depot reorder", f"{kind} description")
        item, before = records(c["Item"])[0], records(p["Item"])[0]
        ck({k for k in item if item[k] != before[k]} == {"IID", "DESCR", "TYPE"} and
           item["IID"] == "TEACH-PRU-01" and item["TYPE"] == "PRU" and
           item["DESCR"] == "Partially repairable primary teaching component" and
           item["FRT"] == before["FRT"], f"{kind} PRU item")
        structure, old_structure = records(c["ItemStructure"])[0], records(p["ItemStructure"])[0]
        ck({k for k in structure if structure[k] != old_structure[k]} == {"IID"} and
           structure["IID"] == "TEACH-PRU-01" and structure["MID"] == "TEACH-AIR-01",
           f"{kind} primary topology")
        repair = records(c["ItemRepair"])
        ck(len(repair) == 1 and not rows(p["ItemRepair"]) and
           {k: v for k, v in repair[0].items() if v is not None} ==
           {"IID": "TEACH-PRU-01", "STID": "DEPOT-01", "DIRPT": 1,
            "SURPT": 0, "DIRPF": .5, "SURPF": 1}, f"{kind} depot partial repair row")
        reorder, old_reorder = records(c["ItemReorder"])[0], records(p["ItemReorder"])[0]
        ck({k for k in reorder if reorder[k] != old_reorder[k]} == {"IID", "DISCF"} and
           reorder["IID"] == "TEACH-PRU-01" and reorder["DISCF"] == .5 and
           reorder["LEADT"] == 1, f"{kind} discard fraction/reorder source")
        stock, old_stock = records(c["StockAllocation"]), records(p["StockAllocation"])
        ck(len(stock) == len(old_stock) == 2 and all(
            {k for k in item if item[k] != old[k]} == {"IID"} and
            item["IID"] == "TEACH-PRU-01" and item["STSIZ"] == old["STSIZ"]
            for item, old in zip(stock, old_stock)), f"{kind} base/depot stock source")
        ck(records(c["Control"])[0]["RSEED"] == ("1" if kind == "repair" else "2"),
           f"{kind} fixed seed")
        ck(len([name for name, table in c.items() if rows(table)]) == 22,
           f"{kind} 22 populated tables")
        result[kind] = c
    pair_changed = {name for name in result["repair"] if result["repair"][name] != result["discard"][name]}
    ck(pair_changed == {"Control"} and
       {key for key in records(result["repair"]["Control"])[0] if
        records(result["repair"]["Control"])[0][key] !=
        records(result["discard"]["Control"])[0][key]} == {"RSEED"},
       "pair differs only in RSEED")
    return result


def run_review(kind: str, src: dict) -> tuple[str, dict]:
    case = CASES[kind]
    run = case / "runs" / RUN_IDS[kind]
    inv, closure, steps = (read(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
    ck(inv["run_id"] == closure["run_id"] == run.name and closure["error"] is None,
       f"{kind} run identity/closure")
    ck(closure["invocation_sha256"] == sha(run / "invocation.json"), f"{kind} invocation seal")
    ck(inv["input_sha256"] == sha(case / "native-input.json") == sha(run / "input.json") and
       inv["parent_sha256"] == sha(PARENT) and inv["contract_sha256"] == sha(case / "contract.json"),
       f"{kind} run source pins")
    ck(inv["session_id"] == 0 and inv["execution_mode"] == "ssh_cli_v1" and
       inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"],
       f"{kind} session0 SSH")
    ck(inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
       inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1,
       f"{kind} queue/GUI identity")
    ck(inv["source_hashes_before"] == closure["source_hashes_before"] ==
       closure["source_hashes_after"], f"{kind} source stability")
    for key, path in {"input": case / "native-input.json", "parent": PARENT,
                      "contract": case / "contract.json", "builder": case / "build.py",
                      "checker": case / "check_roundtrip.py", "runner_script": case / "run_native_ssh.ps1"}.items():
        ck(inv["source_hashes_before"].get(key) == sha(path), f"{kind} source seal {key}")
    ck(inv["source_hashes_before"]["simlox_exe"] ==
       "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0",
       f"{kind} runtime seal")
    for name, metadata in closure["raw"].items():
        path = run / name
        ck(path.is_file() and path.stat().st_size == metadata["bytes"] and
           sha(path) == metadata["sha256"], f"{kind} raw seal {name}")
    ck([s["name"] for s in steps] ==
       ["import", "export", "calc", "jsonreport", "check_import_export"],
       f"{kind} five guarded stages")
    for step in steps:
        ck(step["status"] == "completed" and step["exit_code"] == 0 and
           step["gui_preserved"] and step["error"] is None, f"{kind} step {step['name']}")
    export = tables(run / "roundtrip-raw.json", "model")
    for name, table in src.items():
        if rows(table):
            ck(name in export and table["columns"] == export[name]["columns"] and
               rows(table) == rows(export[name]), f"{kind} native roundtrip {name}")
    runlog = (run / "run.log").read_text(errors="replace")
    ck("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and
       "warning #108" in runlog and "error #" not in runlog.lower(), f"{kind} converter")
    ck((run / "model.sxo").stat().st_size > 100000, f"{kind} usable SXO")
    return (run / "model.log").read_text(errors="replace"), tables(run / "report-raw.json", "report")


def event_review(kind: str, log: str) -> None:
    ck("Stock at: <TEACH-PRU-01,0,DEPOT-01,0> Level: 2 Items:<TEACH-PRU-01,0,0>,<TEACH-PRU-01,0,1>" in log and
       "Stock at: <TEACH-PRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-PRU-01,0,2>" in log,
       f"{kind} opening stock IDs")
    if kind == "repair":
        ck(event(log, "9.8829", "critical random failure added") and
           "subitem failed: <TEACH-PRU-01,0,3>" in log and
           event(log, "10", "Take replacement item <TEACH-PRU-01,0,2> from stock"),
           "repair failure and base issue")
        ck(event(log, "10", "remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> starts performing, planned to last for 0.166667 hours") and
           event(log, "10.1667", "fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> starts performing, planned to last for 0.333333 hours") and
           event(log, "10.5", "system SURP task 0 on <TEACH-AIR-01,0> completed"),
           "repair branch system exchange")
        ck(event(log, "10.1667", "transport request <<TEACH-PRU-01,0,3>") and
           event(log, "12.1667", "Item requiring maintenance arrives <TEACH-PRU-01,0,3>") and
           event(log, "12.1667", "item DIRP task 1 on <TEACH-PRU-01,0,3> started") and
           event(log, "13.1667", "item DIRP task 1 on <TEACH-PRU-01,0,3> completed") and
           event(log, "13.1667", "Put back replacement item <TEACH-PRU-01,0,3> to stock"),
           "repair branch failed ID3 repaired at depot")
        ck("Item discarded:" not in log and "reorder task" not in log,
           "repair branch no discard/reorder")
        ck(event(log, "12", "Put back replacement item <TEACH-PRU-01,0,0> to stock") and
           "Stock at: <TEACH-PRU-01,0,DEPOT-01,0> Level: 2 Items:<TEACH-PRU-01,0,1>,<TEACH-PRU-01,0,3>" in log,
           "repair branch depot/base identity and stock")
        ck(log.count("mission success:") == 2 and log.count("mission aborted:") == 1 and
           event(log, "34", "systems ready: 1 :<TEACH-AIR-01,0>"),
           "repair mission outcomes/terminal ready")
        base, depot = [1, 0, 1], [2, 1, 2]
    else:
        ck(event(log, "20.822", "critical random failure added") and
           "subitem failed: <TEACH-PRU-01,0,3>" in log and
           event(log, "21.322", "Take replacement item <TEACH-PRU-01,0,2> from stock") and
           event(log, "21.822", "system SURP task 0 on <TEACH-AIR-01,0> completed"),
           "discard branch first aircraft failure/exchange")
        ck(event(log, "21.4887", "transport request <<TEACH-PRU-01,0,3>") and
           event(log, "23.4887", "Item requiring maintenance arrives <TEACH-PRU-01,0,3>") and
           event(log, "23.4887", "Item discarded: <TEACH-PRU-01,0,3>"),
           "discard branch failed ID3 discarded at depot")
        ck("item DIRP task 1 on <TEACH-PRU-01,0,3>" not in log and
           "Put back replacement item <TEACH-PRU-01,0,3>" not in log,
           "discarded ID3 never repaired or stocked")
        ck(event(log, "23.4887", "reorder task 0 started, reorder time: 1") and
           event(log, "24.4887", "reorder task 0 completed, total time was 1") and
           event(log, "24.4887", "Put back replacement item <TEACH-PRU-01,0,4> to stock"),
           "discard branch one-hour one-unit reorder ID4")
        ck(event(log, "23.322", "Put back replacement item <TEACH-PRU-01,0,0> to stock") and
           "Stock at: <TEACH-PRU-01,0,DEPOT-01,0> Level: 2 Items:<TEACH-PRU-01,0,1>,<TEACH-PRU-01,0,4>" in log,
           "discard branch depot/base replenishment")
        ck(event(log, "32.9882", "critical random failure added") and
           "subitem failed: <TEACH-PRU-01,0,5>" in log and
           event(log, "33.4882", "Take replacement item <TEACH-PRU-01,0,0> from stock") and
           event(log, "33.9882", "system SURP task 1 on <TEACH-AIR-01,0> completed"),
           "discard branch second aircraft failure/exchange")
        ck(event(log, "35.6549", "item DIRP task 2 on <TEACH-PRU-01,0,5> started") and
           event(log, "35.6549", "planned to last for 1 hours") and
           "item DIRP task 2 on <TEACH-PRU-01,0,5> completed" not in log and
           "Put back replacement item <TEACH-PRU-01,0,5>" not in log,
           "later ID5 repair unfinished by horizon")
        ck(event(log, "35.4882", "Put back replacement item <TEACH-PRU-01,0,1> to stock") and
           log.count("mission success:") == 1 and log.count("mission aborted:") == 2 and
           event(log, "33.9882", "systems ready: 1 :<TEACH-AIR-01,0>"),
           "discard later transport/missions/terminal ready")
        base, depot = [1, 0, 1, 0, 1], [2, 1, 2, 1]
    for station, expected in (("BASE-01", base), ("DEPOT-01", depot)):
        levels = [int(x) for x in re.findall(
            rf"Stock at: <TEACH-PRU-01,0,{station},0> Level: (\d+)", log)]
        ck(levels == expected, f"{kind} {station} stock conservation")
    ck("Backorder added" not in log, f"{kind} no backorder")


def report_review(kind: str, report: dict) -> None:
    ck(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"},
       f"{kind} report table set")
    summary = records(report["ResultSummary"])[0]
    factors = ({"MTMF": 1, "MSTF": 1, "MSUF": 2/3, "STMF": 1} if kind == "repair"
               else {"MTMF": .8017075657844543, "MSTF": 1, "MSUF": 1/3,
                     "STMF": .8017075657844543})
    ck(summary["NREP"] == 1 and summary["RTIUP"] == 36 and
       all(near(summary[k], value) for k, value in factors.items()),
       f"{kind} summary factors")
    system = records(report["SystemResults"])
    stock = records(report["StockTotalResults"])
    ck(len(system) == len(stock) == 72, f"{kind} 72 report bins")
    if kind == "repair":
        prep, mission, maintain, ready = (
            [(7, 8), (19, 20), (31, 32)],
            [(8, 10), (20, 22), (32, 34)],
            [(10, 10.5)],
            [(0, 7), (10.5, 19), (22, 31), (34, 36)])
        fail_bins, complete_bins, demand_bins = {9.5}, {10.5}, {10}
    else:
        prep, mission, maintain, ready = (
            [(7, 8), (19, 20), (31, 32)],
            [(8, 10), (20, 21.322), (32, 33.4882)],
            [(21.322, 21.822), (33.4882, 33.9882)],
            [(0, 7), (10, 19), (21.822, 31), (33.9882, 36)])
        fail_bins, complete_bins, demand_bins = {20.5, 32.5}, {21.5, 33.5}, {21, 33}
    for i, (s, t) in enumerate(zip(system, stock)):
        h = i/2
        pr = sum(overlap(a, b, h) for a, b in prep)
        mi = sum(overlap(a, b, h) for a, b in mission)
        mt = sum(overlap(a, b, h) for a, b in maintain)
        ry = sum(overlap(a, b, h) for a, b in ready)
        expected_s = {"NSYRY": ry, "NSYMA": pr+mi, "NSYMO": mi,
                      "NSYMR": pr, "NSYUA": mt, "NSYA": ry+pr+mi,
                      "FTMO": mi, "NSYRP": mt,
                      "NREPT": int(h in complete_bins), "NFAIL": int(h in fail_bins),
                      "STACC": mi, "SYDT": .5 if h in demand_bins else None,
                      "NSYDT": int(h in demand_bins)}
        expected_t = {"PNB": 1, "NDF": int(h in demand_bins), "NWT": int(h in demand_bins)}
        ck((s["STINT"], s["ETINT"], t["STINT"], t["ETINT"]) ==
           (h, h+.5, h, h+.5), f"{kind} bin times {i}")
        ck(s["UNID"] == "Total over all Units" and s["SID"] == "Total over all Systems",
           f"{kind} report labels {i}")
        for name, value in s.items():
            if name in ("UNID", "SID", "STINT", "ETINT"):
                continue
            target = expected_s.get(name, 0)
            ck(value is None if target is None else near(value, target),
               f"{kind} system {name} bin {i}")
        for name, value in t.items():
            if name in ("STINT", "ETINT"):
                continue
            target = (None if name in ("NBOU", "WTS") or
                      (name in ("ROS", "ROST", "WT", "WTT") and h not in demand_bins)
                      else expected_t.get(name, 0))
            ck(value is None if target is None else near(value, target),
               f"{kind} stock {name} bin {i}")
    ck(system[-1]["NSYRY"] == 1 and stock[-1]["PNB"] == 1 and stock[-1]["NBO"] == 0,
       f"{kind} terminal aircraft ready and no backorder")


def main() -> None:
    sources = source_review()
    for kind in CASES:
        log, report = run_review(kind, sources[kind])
        event_review(kind, log)
        report_review(kind, report)
    branch = "repair" if LOCAL_CASE == CASES["repair"] else "discard"
    result = {
        "schema": "simlox-g01-var02-paired-independent-review/v1",
        "local_branch": branch,
        "passed": not failures,
        "verdict": "GO" if not failures else "NO-GO",
        "check_count": checks,
        "failure_count": len(failures),
        "failures": failures,
        "observed": {
            "repair_seed_1": "failed PRU3 transported to depot and directly repaired 12.1667-13.1667; returned to depot stock",
            "discard_seed_2": "failed PRU3 discarded at depot 23.4887; one-unit reorder delivers new PRU4 at 24.4887",
            "seed_2_late_repair": "failed PRU5 starts depot direct repair 35.6549; no completion before 36-hour horizon",
        },
        "scope": "Two fixed seeds under identical PRU source policy except Control.RSEED show repair and discard/reorder paths, with typed physical identities and sealed CLI evidence.",
        "limits": [
            "The two outcomes do not establish a 50/50 frequency law or branch independence.",
            "Seed-2 PRU5 remains under depot repair at hour 36 although the aircraft is ready; do not claim all maintenance complete or full depot stock.",
            "Other fractions, stations, seeds, SPRU, GUI simulation and cross-engine parity remain unverified.",
        ],
    }
    OUT.write_bytes((json.dumps(result, indent=2)+"\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks": checks, "failures": failures,
                      "report": str(OUT)}))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
