"""Independent read-only replay for G02.var04 fixed-seed position PM matrix.

Uses the standard library and frozen source/raw files; imports no author modules.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
PARENT = ROOT / "G02-var01-position-modes-v1.0.0" / "native-input.json"
TEMPLATE = ROOT / "D03-calendar-pm-v1.0.0" / "native-input.json"
OUT = Path(__file__).with_name("independent-readonly-2026-10-02.json")
RUNS = {
    "no-pm": "g02-var04-no-pm-20261002-02",
    "pos-a-only": "g02-var04-pos-a-only-20261002-02",
    "pos-b-only": "g02-var04-pos-b-only-20261002-01",
    "both": "g02-var04-both-20261002-01",
}
SOURCE_PATHS = {
    "parent": PARENT,
    "pm_template": TEMPLATE,
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    "contract": CASE / "contract.json",
    "builder": CASE / "build.py",
    "checker": CASE / "check_roundtrip.py",
    "runner_script": CASE / "run_native_ssh.ps1",
    "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
}
SPEC = {
    "no-pm": [],
    "pos-a-only": [("PM-POS-A", "POS-A", 24.0, 1.0)],
    "pos-b-only": [("PM-POS-B", "POS-B", 36.0, 0.5)],
    "both": [("PM-POS-A", "POS-A", 24.0, 1.0), ("PM-POS-B", "POS-B", 36.0, 0.5)],
}
EXPECTED_PM = {
    "no-pm": [],
    "pos-a-only": [(24.0, 25.0, "PM-POS-A"), (49.0, 50.0, "PM-POS-A")],
    "pos-b-only": [(36.0, 36.5, "PM-POS-B")],
    "both": [(24.0, 25.0, "PM-POS-A"), (36.0, 36.5, "PM-POS-B"), (49.0, 50.0, "PM-POS-A")],
}
checks = []


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path, native=False):
    raw = path.read_text(encoding="utf-8-sig")
    if native: raw = re.sub(r",(?=\s*[}\]])", "", raw)
    return json.loads(raw)


def test(label, value, detail=None):
    checks.append({"name": label, "pass": bool(value), **({"detail": detail} if detail is not None else {})})


def tables(doc, key="model"):
    return {table["name"]: table for table in doc[key]["tables"]}


def all_rows(table):
    return [(inst["instance_name"], row) for inst in table["instances"] for row in inst["rows"]]


def column(table, name):
    return [c["name"] for c in table["columns"]].index(name)


def cell(table, row, name):
    return row[column(table, name)]


def setcell(table, row, name, value):
    row[column(table, name)] = value


def firstrow(table):
    return table["instances"][0]["rows"][0]


def addrow(table, row):
    table["instances"][0]["rows"].append(copy.deepcopy(row))


def construct(parent, template, variant):
    doc = copy.deepcopy(parent)
    t, p = tables(doc), tables(template)
    setcell(t["ProblemDescription"], firstrow(t["ProblemDescription"]), "PDESC", f"G02.var04 position-specific PM {variant}")
    for name, value in (("SIMPE", 60.0), ("RCEND", 60.0), ("ENPM", "Y")):
        setcell(t["Control"], firstrow(t["Control"]), name, value)
    for inst in t["ResultCollection"]["instances"]:
        for row in inst["rows"]: setcell(t["ResultCollection"], row, "RCEND", 60.0)
    if SPEC[variant]: addrow(t["SubTaskType"], firstrow(p["SubTaskType"]))
    for pmid, mid, interval, duration in SPEC[variant]:
        task = copy.deepcopy(firstrow(p["Tasks"]))
        for name, value in (("TID", pmid), ("DESCR", f"Calendar PM at {mid}")): setcell(t["Tasks"], task, name, value)
        addrow(t["Tasks"], task)
        pm = copy.deepcopy(firstrow(p["MaterielPM"]))
        for name, value in (("PMID", pmid), ("DESCR", f"Calendar PM at {mid}"), ("MID", mid), ("PMINT", interval), ("OPID", "CALHOURS")): setcell(t["MaterielPM"], pm, name, value)
        addrow(t["MaterielPM"], pm)
        location = copy.deepcopy(firstrow(p["PMLocation"]))
        for name, value in (("PMID", pmid), ("ID", "TEACH-AIR-01"), ("STID", "BASE-01"), ("PMT", duration), ("TID", pmid)): setcell(t["PMLocation"], location, name, value)
        addrow(t["PMLocation"], location)
        breakdown = copy.deepcopy(firstrow(p["TaskBreakDown"]))
        for name, value in (("TID", pmid), ("DURN", duration)): setcell(t["TaskBreakDown"], breakdown, name, value)
        addrow(t["TaskBreakDown"], breakdown)
    return doc


def metric_rows(table):
    return [row for inst in table["instances"] for row in inst["rows"]]


def pm_events(text):
    started = [(float(time), int(task)) for time, task in re.findall(r"Time: ([0-9.]+)\s+system PM task (\d+) on <TEACH-AIR-01,0> started", text)]
    names = [(float(time), int(task), name) for time, task, name in re.findall(r"Time: ([0-9.]+)\s+system PM task (\d+) on <TEACH-AIR-01,0> PMID: (PM-POS-[AB])", text)]
    ended = [(float(time), int(task)) for time, task in re.findall(r"Time: ([0-9.]+)\s+system PM task (\d+) on <TEACH-AIR-01,0> completed", text)]
    by_name = {(time, task): name for time, task, name in names}
    by_end = {task: time for time, task in ended}
    return [(time, by_end.get(task), by_name.get((time, task))) for time, task in started], (len(started), len(names), len(ended))


def main():
    contract, parent, template = load(CASE / "contract.json"), load(PARENT), load(TEMPLATE)
    test("accepted G02.var01 parent SHA", sha(PARENT) == contract["parent_input_sha256"])
    test("accepted D03 PM template SHA", sha(TEMPLATE) == contract["pm_template_input_sha256"])
    source_shas = {key: sha(path) for key, path in SOURCE_PATHS.items()}
    GUI = None
    outcomes = {}
    raw_count = 0
    for variant, run_id in RUNS.items():
        run = CASE / "runs" / run_id
        source = CASE / f"{variant}-input.json"
        expected = construct(parent, template, variant)
        expected_raw = (json.dumps(expected, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        test(f"{variant} reconstructed source bytes", source.read_bytes() == expected_raw)
        test(f"{variant} contract SHA", sha(source) == contract["input_sha256"][variant])
        test(f"{variant} copied run input", source.read_bytes() == (run / "input.json").read_bytes())

        invocation, closure, steps = (load(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
        test(f"{variant} invocation SHA and ID", closure["invocation_sha256"] == sha(run / "invocation.json") and invocation["run_id"] == closure["run_id"] == run_id and invocation["variant"] == variant)
        test(f"{variant} session0 SSH ancestry", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and invocation["ssh_connection_present"] and "sshd.exe" in invocation["ssh_ancestor_names"])
        test(f"{variant} mutex", invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
        identity = (invocation["gui"]["pid"], invocation["gui"]["session_id"], invocation["gui"]["start_utc"])
        if GUI is None: GUI = identity
        test(f"{variant} GUI continuity", identity == GUI and identity[:2] == (13340, 1) and all(step["gui_preserved"] for step in steps))
        test(f"{variant} five successful native/check steps", [step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"] and all(step["exit_code"] == 0 and step["status"] == "completed" for step in steps))
        test(f"{variant} source unchanged during run", closure["source_hashes_before"] == closure["source_hashes_after"] and closure["error"] is None)
        for key, value in closure["source_hashes_before"].items():
            actual = sha(source) if key == "input" else sha(Path(invocation["planned_check"]["executable"])) if key == "python" else source_shas[key]
            test(f"{variant} sealed source {key}", value == actual)
        raw_count += len(closure["raw"])
        test(f"{variant} 12 raw seals", len(closure["raw"]) == 12)
        for name, seal in closure["raw"].items():
            path = run / name
            test(f"{variant} raw {name}", path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
        test(f"{variant} raw seal completeness", set(closure["raw"]) == {p.name for p in run.iterdir() if p.is_file()} - {"closure.json", "invocation.json"})

        original_tables = tables(load(source))
        exported_tables = tables(load(run / "roundtrip-raw.json", native=True))
        populated = [name for name, table in original_tables.items() if all_rows(table)]
        test(f"{variant} table count", len(populated) == (18 if variant == "no-pm" else 23))
        for name in populated:
            a, b = original_tables[name], exported_tables.get(name)
            test(f"{variant} exact roundtrip {name}", b is not None and [c["name"] for c in a["columns"]] == [c["name"] for c in b["columns"]] and all_rows(a) == all_rows(b))
        log = (run / "run.log").read_text(encoding="utf-8-sig")
        result = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", log)
        test(f"{variant} converter summary", result is not None)
        conversion = tuple(map(int, result.groups())) if result else None
        test(f"{variant} zero errors one classified warning", conversion == (0, 1, 0) and "(warning #108)" in log)
        test(f"{variant} simulation and report exist", (run / "model.sxo").stat().st_size > 1000 and (run / "report-raw.json").stat().st_size > 1000)

        event_text = (run / "model.log").read_text(encoding="utf-8-sig")
        observed, counts = pm_events(event_text)
        test(f"{variant} PM start/PMID/completion linkage", counts == (len(EXPECTED_PM[variant]),) * 3)
        test(f"{variant} exact PM IDs and times", observed == EXPECTED_PM[variant], observed)
        report = tables(load(run / "report-raw.json", native=True), "report")
        system, stock, summary = (report[name] for name in ("SystemResults", "StockTotalResults", "ResultSummary"))
        sr, st = metric_rows(system), metric_rows(stock)
        test(f"{variant} 120 system and stock bins", len(sr) == len(st) == 120)
        test(f"{variant} aligned 0.5h interval grids", all(cell(system, r, "STINT") == cell(stock, s, "STINT") == i * .5 and cell(system, r, "ETINT") == cell(stock, s, "ETINT") == (i + 1) * .5 for i, (r, s) in enumerate(zip(sr, st))))
        pm_starts = [(cell(system, r, "STINT"), cell(system, r, "NPMS")) for r in sr if cell(system, r, "NPMS") not in (None, 0)]
        pm_completes = [(cell(system, r, "STINT"), cell(system, r, "NPMT")) for r in sr if cell(system, r, "NPMT") not in (None, 0)]
        expect_start_bins = [(start, 1) for start, _, _ in EXPECTED_PM[variant]]
        expect_end_bins = [(end, 1) for _, end, _ in EXPECTED_PM[variant]]
        test(f"{variant} NPMS start-bin counts", pm_starts == expect_start_bins, pm_starts)
        test(f"{variant} NPMT completion-bin counts", pm_completes == expect_end_bins, pm_completes)
        integral = sum((cell(system, r, "NSYPM") or 0) * .5 for r in sr)
        expected_hours = sum(end - start for start, end, _ in EXPECTED_PM[variant])
        test(f"{variant} PM aircraft-hours", math.isclose(integral, expected_hours, abs_tol=1e-5), [integral, expected_hours])
        test(f"{variant} no stock demand/backorder", all((cell(stock, r, name) or 0) == 0 for r in st for name in ("NBO", "NDD", "NDR")))
        test(f"{variant} 60h report summary", len(metric_rows(summary)) == 1 and cell(summary, metric_rows(summary)[0], "RTIUP") == 60 and cell(summary, metric_rows(summary)[0], "NREP") == 1)
        test(f"{variant} terminal ready", math.isclose(cell(system, sr[-1], "NSYRY"), 1, abs_tol=1e-4))
        outcomes[variant] = {"run_id": run_id, "source_sha256": sha(source), "report_sha256": sha(run / "report-raw.json"), "event_log_sha256": sha(run / "model.log"), "conversion_errors_warnings_notes": conversion, "pm_events_start_end_id": observed, "NPMT_bins": pm_completes, "NPMS_bins": pm_starts, "pm_aircraft_hours": integral}
    test("48 raw seals", raw_count == 48)
    failed = [c for c in checks if not c["pass"]]
    report = {"schema": "independent-g02-var04-readonly/v1", "reviewer": "a17_static_reviewer", "verdict": "GO bounded fixed-seed position PM CLI evidence" if not failed else "NO-GO", "checks_passed": len(checks) - len(failed), "checks_total": len(checks), "failures": failed, "raw_seals": raw_count, "outcomes": outcomes, "excluded_diagnostics": ["g02-var04-no-pm-20261002-01", "g02-var04-pos-a-only-20261002-01"], "limitations": ["One seed and one native replication per arm; no frequency estimate.", "Inherited explicit failure modes can affect PM timing; observed starts are not universal due-time rules.", "No general QTYPM, ENVF, replacement, GUI, or cross-engine claim."]}
    OUT.write_bytes((json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({"verdict": report["verdict"], "checks": f"{report['checks_passed']}/{report['checks_total']}", "failures": failed, "script_sha256": sha(Path(__file__)), "report_sha256": sha(OUT)}, indent=2))


if __name__ == "__main__": main()
