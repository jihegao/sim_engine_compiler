"""Independent read-only replay of G01.var06 indexed stockout evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

CASE = Path(__file__).resolve().parent.parent
AIR = CASE.parent
RUN = CASE / "runs/g01-var06-stockout-v100-ssh-20261001-01"
PARENT_CASE = AIR / "G01-var06-similar-vs-identical-v1.0.1"
PARENT = PARENT_CASE / "native-similar.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
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
    return [r for instance in table["instances"] for r in instance["rows"]]


def records(table: dict) -> list[dict]:
    keys = [c["name"] for c in table["columns"]]
    return [dict(zip(keys, row)) for row in rows(table)]


def near(actual, target, eps=2e-4) -> bool:
    return isinstance(actual, (float, int)) and abs(actual-target) < eps


def event(log: str, hour: str, token: str) -> bool:
    return any(line.startswith(f"Time: {hour} ") and token in line for line in log.splitlines())


def overlap(start: float, end: float, h: float) -> float:
    return max(0.0, min(end, h+.5)-max(start, h))/.5


def main() -> None:
    contract = load(CASE / "contract.json")
    diff = load(CASE / "exact-diff.json")
    source = CASE / "native-input.json"
    ck(sha(PARENT) == contract["parent"]["input_sha256"], "accepted similar parent SHA")
    ck((PARENT_CASE / "cli-scope-signoff-2026-10-01.md").is_file(), "parent signoff present")
    ck(sha(MANUAL) == contract["source"]["manual_pdf_sha256"], "installed manual SHA")
    ck(sha(source) == contract["native_input_sha256"], "child input SHA")
    p, c = tables(PARENT, "model"), tables(source, "model")
    changed = {n for n in p if c.get(n) != p[n]}
    ck(set(p) == set(c) and changed == set(contract["delta"]["tables"]) == set(diff["changed_tables"]),
       "exact three-table delta")
    ck(diff["parent_sha256"] == sha(PARENT) and diff["child_sha256"] == sha(source) and
       diff["unchanged_tables"] == len(p)-3, "diff fingerprints")
    for name in p:
        if name in changed:
            ck(diff["changes"][name]["before"] == rows(p[name]) and
               diff["changes"][name]["after"] == rows(c[name]) and
               p[name]["columns"] == c[name]["columns"], f"exact delta {name}")
        else:
            ck(c[name] == p[name], f"invariant source table {name}")
    item = records(c["Item"])[0]
    structure = records(c["ItemStructure"])[0]
    stock = records(c["StockAllocation"])[0]
    repair = records(c["ItemRepair"])[0]
    ck(item["IID"] == "TEACH-LRU-01" and item["NSIMI"] == 2 and
       structure["QTYPM"] == 1 and structure["IID"] == "TEACH-LRU-01", "unchanged similar-item geometry")
    ck(stock["IID"] == "TEACH-LRU-01" and stock["STID"] == "BASE-01" and
       stock["STSIZ"] == 1 and records(p["StockAllocation"])[0]["STSIZ"] == 2,
       "per-index stock reduction")
    ck(repair["IID"] == "TEACH-LRU-01" and repair["DIRPT"] == 30 and
       records(p["ItemRepair"])[0]["DIRPT"] == 1, "30-hour direct repair")
    ck(all(c[name] == p[name] for name in ("System", "OperationProfile", "MissionType",
                                          "Item", "ItemStructure", "SystemRepair", "TaskBreakDown")),
       "rates, missions and task topology inherited")
    ck(len([n for n, t in c.items() if rows(t)]) == 20, "20 populated source tables")

    inv, closure, steps = (load(RUN / f) for f in ("invocation.json", "closure.json", "steps.json"))
    ck(inv["run_id"] == closure["run_id"] == RUN.name and inv["branch_kind"] == "stockout" and
       closure["error"] is None, "run identity and closure")
    ck(closure["invocation_sha256"] == sha(RUN / "invocation.json"), "invocation seal")
    ck(inv["input_sha256"] == sha(source) == sha(RUN / "input.json") and
       inv["parent_sha256"] == sha(PARENT) and
       inv["contract_sha256"] == sha(CASE / "contract.json"), "run source pins")
    ck(inv["execution_mode"] == "ssh_cli_v1" and inv["session_id"] == 0 and
       inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"], "session0 SSH")
    ck(inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
       inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1, "queue/GUI guard")
    ck(inv["source_hashes_before"] == closure["source_hashes_before"] ==
       closure["source_hashes_after"], "source stable during run")
    for key, path in {"input": source, "parent": PARENT, "contract": CASE / "contract.json",
                      "builder": CASE / "build.py", "checker": CASE / "check_roundtrip.py",
                      "runner_script": CASE / "run_native_ssh.ps1"}.items():
        ck(inv["source_hashes_before"].get(key) == sha(path), f"source seal {key}")
    ck(inv["source_hashes_before"]["simlox_exe"] ==
       "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0", "native runtime seal")
    for name, meta in closure["raw"].items():
        path = RUN / name
        ck(path.is_file() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"],
           f"raw seal {name}")
    ck([s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"],
       "five guarded steps")
    for step in steps:
        ck(step["exit_code"] == 0 and step["status"] == "completed" and
           step["gui_preserved"] and step["error"] is None, f"step {step['name']}")
    export = tables(RUN / "roundtrip-raw.json", "model")
    for name, table in c.items():
        if rows(table):
            ck(name in export and export[name]["columns"] == table["columns"] and
               rows(export[name]) == rows(table), f"native row roundtrip {name}")
    runlog = (RUN / "run.log").read_text(errors="replace")
    ck("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in runlog and
       "warning #108" in runlog and "error #" not in runlog.lower(), "zero conversion errors")
    ck((RUN / "model.sxo").stat().st_size > 100000, "usable result SXO")

    log = (RUN / "model.log").read_text(errors="replace")
    ck("Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,0>" in log and
       "Stock at: <TEACH-LRU-01,1,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,1,1>" in log and
       log.count("Stock initiated") == 2, "one opening spare in each similarity index")
    ck(event(log, "8.94145", "critical random failure added") and
       "subitem failed: <TEACH-LRU-01,1,2>" in log and
       event(log, "9.44145", "Take replacement item <TEACH-LRU-01,1,1> from stock") and
       "Stock at: <TEACH-LRU-01,1,BASE-01,0> Level: 0 Items:" in log,
       "first index1 failure exhausts index1 stock")
    ck(event(log, "9.60812", "item DIRP task 1 on <TEACH-LRU-01,1,2> started") and
       event(log, "9.60812", "planned to last for 30 hours") and
       not event(log, "10.6081", "item DIRP task 1 on <TEACH-LRU-01,1,2> completed"),
       "first removed index1 item under 30h repair")
    ck(event(log, "9.94145", "system SURP task 0 on <TEACH-AIR-01,0> completed") and
       event(log, "9.94145", "systems ready: 1 :<TEACH-AIR-01,0>"), "first system restored")
    ck(event(log, "21.4698", "critical random failure added") and
       "subitem failed: <TEACH-LRU-01,1,3>" in log and
       event(log, "21.9698", "Item demand arrives from pos <TEACH-AIR-01,BASE-01,0> item requiring maintenance is <TEACH-LRU-01,1,3>"),
       "second index1 failure and demand")
    ck(event(log, "21.9698", "<TEACH-LRU-01,1,BASE-01,0> Backorder added") and
       "Backorders at: <TEACH-LRU-01,1,BASE-01,0> Nbr: 1" in log and
       event(log, "22.1365", "fit subitem subtask 4 seqno 2 within system SURP task 2 on <TEACH-AIR-01,0> wait for subitem"),
       "index1 backorder and fit task wait")
    ck("Stock at: <TEACH-LRU-01,0,BASE-01,0> Level: 1 Items:<TEACH-LRU-01,0,0>" in log and
       "Take replacement item <TEACH-LRU-01,0,0>" not in log and
       "Take replacement item <TEACH-LRU-01,1,0>" not in log,
       "index0 spare remains unissued while index1 waits")
    ck(event(log, "22.1365", "item DIRP task 3 on <TEACH-LRU-01,1,3> started") and
       event(log, "22.1365", "planned to last for 30 hours") and
       "Put back replacement item <TEACH-LRU-01,1," not in log,
       "both direct repairs outlast horizon")
    ck(event(log, "31", "<BASIC-MISSION,TEACH-UNIT,0,0,2> mission waiting:") and
       event(log, "32.3333", "<BASIC-MISSION,TEACH-UNIT,0,0,2> mission cancelled:") and
       "mission success:" not in log and log.count("mission aborted:") == 2,
       "two aborts then waiting third mission cancellation")
    ck(not event(log, "36", "systems ready: 1") and
       not re.search(r"(?m)^Time: [0-9.]+  system SURP task 2 on <TEACH-AIR-01,0> completed$", log) and
       log.count("Backorder added") == 1 and "Backorder removed" not in log,
       "terminal aircraft unavailable and backorder persists")

    report = tables(RUN / "report-raw.json", "report")
    ck(set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"},
       "report table set")
    summary = records(report["ResultSummary"])[0]
    ck(summary["NREP"] == 1 and summary["RTIUP"] == 36 and
       all(near(summary[k], value) for k, value in
           {"MTMF": .5685423612594604, "STMF": .5685423612594604,
            "MSTF": 2/3, "MSUF": 0}.items()), "summary factors")
    system, stock_rows = records(report["SystemResults"]), records(report["StockTotalResults"])
    ck(len(system) == len(stock_rows) == 72, "72 half-hour System and Stock bins")
    missions = [(8, 9.44145), (20, 21.9698)]
    preps = [(7, 8), (19, 20)]
    repairs = [(9.44145, 9.94145), (21.9698, 22.1365)]
    waits = [(22.1365, 36)]
    ready = [(0, 7), (9.94145, 19)]
    for i, (s, t) in enumerate(zip(system, stock_rows)):
        h = i/2
        mission = sum(overlap(a, b, h) for a, b in missions)
        prep = sum(overlap(a, b, h) for a, b in preps)
        repair = sum(overlap(a, b, h) for a, b in repairs)
        wait = sum(overlap(a, b, h) for a, b in waits)
        ry = sum(overlap(a, b, h) for a, b in ready)
        wanted_s = {"NSYRY": ry, "NSYMA": prep+mission, "NSYMO": mission,
                    "NSYMR": prep, "NSYUA": repair+wait, "NSYA": ry+prep+mission,
                    "FTMO": mission, "NSYRP": repair, "NSYWI": wait,
                    "NREPT": int(h == 9.5), "NFAIL": int(h in (8.5, 21)),
                    "STACC": mission, "SYDT": .5 if h == 9 else None,
                    "NSYDT": int(h == 9)}
        nbo = overlap(21.9698, 36, h)
        wanted_t = {"NBO": nbo, "PNB": 1-nbo, "NDF": int(h in (9, 21.5)),
                    "NWT": int(h == 9), "ROS": 1 if h == 21.5 else 0,
                    "ROST": 1 if h == 21.5 else 0,
                    "WT": 0 if h == 9 else None, "WTT": 0 if h == 9 else None}
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
                      (key in ("ROS", "ROST", "WT", "WTT") and h not in (9, 21.5))
                      else wanted_t.get(key, 0))
            ck(value is None if target is None else near(value, target), f"stock {key} bin {i}")
    ck(system[-1]["NSYUA"] == 1 and system[-1]["NSYWI"] == 1 and
       system[-1]["NSYRY"] == 0 and stock_rows[-1]["NBO"] == 1 and
       stock_rows[-1]["PNB"] == 0, "terminal waiting/backorder report")
    result = {"schema": "simlox-g01-var06-index-stockout-independent-review/v1",
              "passed": not failures, "verdict": "GO" if not failures else "NO-GO",
              "check_count": checks, "failure_count": len(failures), "failures": failures,
              "observed": {"index_0_spare_id": 0, "index_1_initial_spare_id": 1,
                           "index_1_failed_ids": [2, 3], "index_1_backorder_at": 21.9698,
                           "direct_repair_hours": 30, "terminal_backorders": 1,
                           "terminal_aircraft_ready": 0},
              "scope": "One fixed-seed 36-hour native run with concurrent index-1 shortage and unused index-0 spare; no cross-index issue observed.",
              "limits": ["The direct repair duration and per-index stock size changed together from the accepted similar parent; mission outcome is not an isolated NSIMI effect.",
                         "No attempted manual substitution is exposed, but the simultaneous shortage, index-0 spare, typed backorder and wait make this a direct native non-substitution observation for this configuration.",
                         "No broader inventory policy, different station, additional seed or beyond-horizon repair outcome is established."]}
    OUT.write_bytes((json.dumps(result, indent=2)+"\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks": checks, "failures": failures}))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
