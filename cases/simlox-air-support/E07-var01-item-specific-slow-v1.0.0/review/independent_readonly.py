"""Independent, read-only replay of the E07.var01 sealed native CLI evidence.

Uses only the Python standard library. It never imports author scripts or runs SIMLOX.
It writes only the adjacent deterministic review JSON.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE = HERE.parent
AIR = CASE.parent
RUN = CASE / "runs" / "e07-item-slow-v100-ssh-20261002-01"
PARENT = AIR / "E07-item-specific-transport-v1.0.1"
PARENT_RUN = PARENT / "runs" / "e07-item-route-v101-20261001-01"
SUPPORT = AIR / "E04-upstream-transport-fast-v1.0.0" / "native-input.json"
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
DICT = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
OUT = HERE / "independent-readonly-2026-10-02.json"
checks: list[str] = []
failures: list[dict] = []


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # SIMLOX -jsonreport emits a trailing comma after its last table.
        if path.name != "report-raw.json":
            raise
        return json.loads(re.sub(r",(\s*[}\]])", r"\1", raw))


def check(label: str, good: bool, detail=None):
    checks.append(label)
    if not good:
        failures.append({"check": label, "detail": detail})


def near(actual, expected, tolerance=0.00015):
    return actual is not None and abs(float(actual) - expected) <= tolerance


def table(model: dict, name: str) -> dict:
    found = [t for t in model["tables"] if t["name"] == name]
    assert len(found) == 1, (name, len(found))
    return found[0]


def rows(t: dict):
    return [(i["instance_name"], r) for i in t["instances"] for r in i["rows"]]


def columns(t: dict):
    return [c["name"] for c in t["columns"]]


def series(t: dict, field: str):
    c = columns(t)
    return [(float(r[c.index("STINT")]), float(r[c.index("ETINT")]), r[c.index(field)]) for _, r in rows(t)]


def at(log: str, pattern: str):
    return [float(x) for x in re.findall(r"Time: ([0-9.]+) " + pattern, log)]


def single_time(log: str, pattern: str):
    values = at(log, pattern)
    return values[0] if len(values) == 1 else None


def integrate(a: float, b: float, intervals: list[tuple[float, float]]) -> float:
    return sum(max(0.0, min(b, hi) - max(a, lo)) for lo, hi in intervals) / (b - a)


def main():
    contract = load(CASE / "contract.json")
    parent_file = PARENT / "native-input.json"
    source_file = CASE / "native-input.json"
    parent = load(parent_file)
    source = load(source_file)
    check("parent source SHA", sha(parent_file) == contract["direct_parent"]["input_sha256"])
    check("support source SHA", sha(SUPPORT) == contract["support_prerequisite"]["input_sha256"])
    check("child source SHA", sha(source_file) == contract["input_sha256"])
    check("installed manual SHA", sha(MANUAL) == contract["source"]["manual_pdf_sha256"])
    check("installed dictionary SHA", sha(DICT) == contract["source"]["dictionary_sha256"])

    # Reconstruct the only behavioral cell independently of the author's builder.
    expected = copy.deepcopy(parent)
    pd = table(expected["model"], "ProblemDescription")
    pd["instances"][0]["rows"][0][0] = table(source["model"], "ProblemDescription")["instances"][0]["rows"][0][0]
    ist = table(expected["model"], "ItemStationStructure")
    opol = columns(ist).index("OPOL")
    check("parent item policy FAST", rows(ist) == [("", ["TEACH-LRU-01", "BASE-01", "DEPOT-01", 1.0, 3.0, None, None, 1.0, "FAST", None, None, None])])
    ist["instances"][0]["rows"][0][opol] = "SLOW"
    check("exact parent-derived child model", expected == source)
    check("general link stays FAST 2h/2h", rows(table(source["model"], "StationStructure"))[0][1][2:9] == [2.0, 2.0, None, None, 1.0, "FAST", None])
    diff = load(CASE / "exact-diff.json")
    check("declared exact-diff source pins", diff["parent_sha256"] == sha(parent_file) and diff["input_sha256"] == sha(source_file))
    check("declared changed tables", set(diff["changed_tables"]) == {"ItemStationStructure", "ProblemDescription"})

    inv = load(RUN / "invocation.json")
    closure = load(RUN / "closure.json")
    steps = load(RUN / "steps.json")
    check("run identity", inv["run_id"] == closure["run_id"] == RUN.name)
    check("session-0 SSH ancestry", inv["execution_mode"] == "ssh_cli_v1" and inv["session_id"] == 0 and inv["ssh_connection_present"] and "sshd.exe" in inv["ssh_ancestor_names"])
    check("host queue mutex", inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
    check("GUI PID/session/start pinned", inv["gui"] == {"pid": 13340, "session_id": 1, "start_utc": "2026-09-28T10:09:56.8261381Z"})
    check("five successful guarded steps", [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps))
    check("invocation SHA sealed", closure["invocation_sha256"] == sha(RUN / "invocation.json"))
    source_paths = {"input": source_file, "parent": parent_file, "support": SUPPORT, "table_dictionary": DICT, "manual": MANUAL,
                    "contract": CASE / "contract.json", "builder": CASE / "build.py", "exact_diff": CASE / "exact-diff.json",
                    "diff_checker": CASE / "describe_diff.py", "checker": CASE / "check_roundtrip.py", "runner_script": CASE / "run_native_ssh.ps1"}
    for role, path in source_paths.items():
        digest = sha(path)
        check("source seal " + role, inv["source_hashes_before"].get(role) == digest and closure["source_hashes_before"].get(role) == digest and closure["source_hashes_after"].get(role) == digest)
    check("source seal dictionaries equal", closure["source_hashes_before"] == closure["source_hashes_after"] == inv["source_hashes_before"])
    check("closure successful", closure["error"] is None)
    check("exact twelve raw seals", len(closure["raw"]) == 12)
    for name, seal in sorted(closure["raw"].items()):
        path = RUN / name
        check("raw seal " + name, path.exists() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
    check("run copy of input exact", (RUN / "input.json").read_bytes() == source_file.read_bytes())
    check("nonempty SXI/SXO", (RUN / "model.sxi").stat().st_size > 1000 and (RUN / "model.sxo").stat().st_size > 1000)

    native = load(RUN / "roundtrip-raw.json")["model"]
    source_tables = {t["name"]: t for t in source["model"]["tables"] if rows(t)}
    native_tables = {t["name"]: t for t in native["tables"]}
    check("22 row-containing source tables", len(source_tables) == 22)
    check("three authored all-null placeholder tables", {name for name, t in source_tables.items() if all(all(v is None for v in row) for _, row in rows(t))} == {"ControlParameters", "GlobalParameters", "OperationParameter"})
    for name, src in sorted(source_tables.items()):
        dst = native_tables.get(name)
        check("native roundtrip " + name, dst is not None and columns(dst) == columns(src) and rows(dst) == rows(src))
    placeholders = {name: native_tables.get(name) for name, src in ((t["name"], t) for t in source["model"]["tables"]) if not rows(src)}
    check("ten native-populated all-null placeholder tables", len(placeholders) == 10 and all(t is not None and rows(t) and all(v is None for _, row in rows(t) for v in row) for t in placeholders.values()), sorted(placeholders))
    runlog = (RUN / "run.log").read_text(encoding="utf-8", errors="replace")
    check("conversion exact diagnostic", "Errors: 0, Warnings: 1, Notes: 0" in runlog and "warning #108" in runlog and "Starting simulation" in runlog)

    log = (RUN / "model.log").read_text(encoding="utf-8", errors="replace")
    plog = (PARENT_RUN / "model.log").read_text(encoding="utf-8", errors="replace")
    # All requests and completions name physical item instances.
    patterns = {
        "failure": r"<TEACH-AIR-01,0> critical random failure added",
        "abort": r"<BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted",
        "base_demand": r"<TEACH-LRU-01,0,BASE-01,0> Item demand arrives from pos",
        "base_backorder": r"<TEACH-LRU-01,0,BASE-01,0> Backorder added",
        "remove_done": r" remove subitem subtask 0 seqno 1 within system SURP task 0 on <TEACH-AIR-01,0> completed",
        "fault_up_start": r" transport request <<TEACH-LRU-01,0,1>,<TEACH-LRU-01,0,BASE-01,0>,<TEACH-LRU-01,0,DEPOT-01,0>> started",
        "fault_depot": r"<TEACH-LRU-01,0,DEPOT-01,0> Item requiring maintenance arrives <TEACH-LRU-01,0,1>",
        "depot_demand": r"<TEACH-LRU-01,0,DEPOT-01,0> Item demand arrives from pos",
        "depot_issue": r"<TEACH-LRU-01,0,DEPOT-01,0> Take replacement item <TEACH-LRU-01,0,0> from stock",
        "spare_down_start": r" transport request <<TEACH-LRU-01,0,0>,<TEACH-LRU-01,0,DEPOT-01,0>,<TEACH-LRU-01,0,BASE-01,0>> started",
        "spare_base": r"<TEACH-LRU-01,0,BASE-01,0> Replacement item arrives <TEACH-LRU-01,0,0>",
        "backorder_removed": r"<TEACH-LRU-01,0,BASE-01,0> Backorder removed",
        "item_repair_start": r"<TEACH-LRU-01,0,DEPOT-01,0> Start repair of item <TEACH-LRU-01,0,1>",
        "item_repair_finish": r"<TEACH-LRU-01,0,DEPOT-01,0> Finished repair of item <TEACH-LRU-01,0,1>",
        "item_restock": r"<TEACH-LRU-01,0,DEPOT-01,0> Put back replacement item <TEACH-LRU-01,0,1> to stock",
        "fit_done": r" fit subitem subtask 1 seqno 2 within system SURP task 0 on <TEACH-AIR-01,0> completed",
        "system_ready": r"<TEACH-AIR-01,BASE-01,0> System ready <TEACH-AIR-01,0>",
    }
    times = {name: single_time(log, pattern) for name, pattern in patterns.items()}
    for name, expected_time in {"failure": 9.8829, "abort": 9.8829, "base_demand": 10, "base_backorder": 10,
                                "remove_done": 10.1667, "fault_up_start": 10.1667, "fault_depot": 13.1667,
                                "depot_demand": 13.1667, "depot_issue": 13.1667, "spare_down_start": 13.1667,
                                "spare_base": 14.1667, "backorder_removed": 14.1667,
                                "item_repair_start": 13.1667, "item_repair_finish": 14.1667,
                                "item_restock": 14.1667, "fit_done": 14.5}.items():
        check("event " + name, near(times[name], expected_time), times[name])
    check("faulty up transport three hours", near(times["fault_depot"] - times["fault_up_start"], 3))
    check("spare down transport one hour", near(times["spare_base"] - times["spare_down_start"], 1))
    check("one-hour same-item depot repair", near(times["item_repair_finish"] - times["item_repair_start"], 1))
    check("no early depot issue", len(at(log, patterns["depot_issue"])) == 1 and near(times["depot_issue"], times["fault_depot"]))
    check("replacement fits after base arrival", near(times["fit_done"] - times["spare_base"], 1/3))
    check("event backorder waiting 4h 10m", re.search(r"Backorder removed, waiting time was 4\.16667", log) is not None)
    check("same aircraft ready at 14.5", 14.5 in at(log, patterns["system_ready"]))
    check("later missions start and succeed", at(log, r"<BASIC-MISSION,TEACH-UNIT,0,0,[12]> mission starting") == [20.0, 32.0] and at(log, r"<BASIC-MISSION,TEACH-UNIT,0,0,[12]> mission success") == [22.0, 34.0])
    check("single critical failure and abort", at(log, patterns["failure"]) == at(log, patterns["abort"]) == [9.8829])
    check("physical stock instance conservation", log.count("Take replacement item <TEACH-LRU-01,0,0> from stock") == 1 and log.count("Put back replacement item <TEACH-LRU-01,0,1> to stock") == 1)
    check("FAST parent issues on local demand", at(plog, patterns["depot_issue"]) == [10.0])
    check("FAST parent ready earlier", 11.3333 in at(plog, patterns["system_ready"]))
    check("FAST and SLOW same failure and later outcomes", at(plog, patterns["failure"]) == at(log, patterns["failure"]) and at(plog, r"<BASIC-MISSION,TEACH-UNIT,0,0,[12]> mission success") == [22.0, 34.0])

    report = {t["name"]: t for t in load(RUN / "report-raw.json")["report"]["tables"]}
    preport = {t["name"]: t for t in load(PARENT_RUN / "report-raw.json")["report"]["tables"]}
    check("report four tables", set(report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    summary = dict(zip(columns(report["ResultSummary"]), rows(report["ResultSummary"])[0][1]))
    psummary = dict(zip(columns(preport["ResultSummary"]), rows(preport["ResultSummary"])[0][1]))
    check("report summary 1 abort/2 successes", summary == psummary and near(summary["NREP"], 1) and near(summary["RTIUP"], 36) and near(summary["MTMF"], 1) and near(summary["MSTF"], 1) and near(summary["MSUF"], 2/3) and near(summary["STMF"], 1), summary)
    sysrows = series(report["SystemResults"], "NSYRY")
    stockrows = series(report["StockTotalResults"], "NBO")
    check("72 aligned System/Stock bins", len(sysrows) == len(stockrows) == 72 and all(near(sysrows[i][0], i/2, 1e-7) and near(sysrows[i][1], (i+1)/2, 1e-7) and near(stockrows[i][0], i/2, 1e-7) and near(stockrows[i][1], (i+1)/2, 1e-7) for i in range(72)))
    ready = [(0, 7), (14.5, 19), (22, 31), (34, 36)]
    # The aborted aircraft remains on its flight/return until hour 10.
    operating = [(8, 10), (20, 22), (32, 34)]
    backorder = [(10, 14.1667)]
    for field, intervals in [("NSYRY", ready), ("NSYMO", operating)]:
        for k, (a, b, value) in enumerate(series(report["SystemResults"], field)):
            check(f"{field} event-derived bin {k}", near(value, integrate(a, b, intervals), 0.00025), [a, b, value])
    for field, intervals in [("NBO", backorder)]:
        for k, (a, b, value) in enumerate(series(report["StockTotalResults"], field)):
            check(f"{field} event-derived bin {k}", near(value, integrate(a, b, intervals), 0.00025), [a, b, value])
    for k, ((a, b, nbo), (_, _, pnb)) in enumerate(zip(stockrows, series(report["StockTotalResults"], "PNB"))):
        check(f"PNB complementary backorder bin {k}", near(float(nbo or 0) + float(pnb or 0), 1, 0.00025), [a, b, nbo, pnb])
    for field, event_time in [("NFAIL", 9.8829), ("NREPT", 14.5)]:
        values = series(report["SystemResults"], field)
        check(field + " single event bin", [(a,b,v) for a,b,v in values if v] == [(9.5,10.0,1)] if field == "NFAIL" else [(a,b,v) for a,b,v in values if v] == [(14.5,15.0,1)])
    check("reported 4h10m stock wait", near(next(v for _,_,v in series(report["StockTotalResults"], "WT") if v is not None), 4.166667, 0.00001))
    check("terminal ready one / no backorder", near(sysrows[-1][2], 1) and near(series(report["StockTotalResults"], "PNB")[-1][2], 1) and near(stockrows[-1][2], 0))
    check("FAST parent same report summary", rows(report["ResultSummary"]) == rows(preport["ResultSummary"]))
    check("SLOW longer backorder integral", sum(float(v or 0)*0.5 for _,_,v in stockrows) > sum(float(v or 0)*0.5 for _,_,v in series(preport["StockTotalResults"], "NBO")))

    # Completion and waiting states are disjoint and exhaust the repair turnaround.
    for field, intervals in [("NSYRP", [(10, 10.1667), (14.1667, 14.5)]),
                             ("NSYWI", [(10.1667, 14.1667)]),
                             ("NSYUA", [(10, 14.5)])]:
        for k, (a, b, value) in enumerate(series(report["SystemResults"], field)):
            check(f"{field} event-derived bin {k}", near(value, integrate(a, b, intervals), 0.00025), [a, b, value])
    parent_closure = load(PARENT_RUN / "closure.json")
    check("accepted FAST parent input seal", parent_closure["raw"]["input.json"]["sha256"] == sha(parent_file) == sha(PARENT_RUN / "input.json"))
    check("accepted FAST parent report seal", parent_closure["raw"]["report-raw.json"]["sha256"] == sha(PARENT_RUN / "report-raw.json"))
    check("accepted FAST parent invocation seal", parent_closure["invocation_sha256"] == sha(PARENT_RUN / "invocation.json"))

    result = {
        "schema": "independent-e07-var01-readonly/v1",
        "reviewer": "a17_static_reviewer",
        "verdict": "GO: bounded item-specific SLOW CLI observation" if not failures else "NO-GO",
        "checks_passed": len(checks) - len(failures), "checks_total": len(checks), "failures": failures,
        "source_sha256": sha(source_file), "raw_report_sha256": sha(RUN / "report-raw.json"),
        "parent_source_sha256": sha(parent_file), "parent_raw_report_sha256": sha(PARENT_RUN / "report-raw.json"),
        "raw_seals_checked": len(closure["raw"]), "parent_seals_checked": 3, "source_row_tables": 22, "source_all_null_placeholders": 3,
        "native_added_all_null_placeholders": 10, "event_times_hours": times,
        "summary": summary,
        "backorder_hours_slow": sum(float(v or 0)*0.5 for _,_,v in stockrows),
        "backorder_hours_fast": sum(float(v or 0)*0.5 for _,_,v in series(preport["StockTotalResults"], "NBO")),
        "limits": ["Single fixed-seed, single repairable LRU and link; observed demand timing does not establish population behavior or FIFO ordering.",
                   "General StationStructure remains FAST; this tests only the item-specific SLOW override.",
                   "StockTotalResults is an aggregate bin-average ledger; PNB is treated as complementary to NBO, not as physical on-hand inventory. Physical identities and same-time order come from the native event log.",
                   "No inference about discardables, policy profiles, other override precedence, GUI display, or cross-engine parity."],
    }
    OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": result["verdict"], "checks": f"{result['checks_passed']}/{result['checks_total']}", "failures": failures[:8], "script_sha256": sha(Path(__file__)), "report_sha256": sha(OUT)}, indent=2))


if __name__ == "__main__":
    main()
