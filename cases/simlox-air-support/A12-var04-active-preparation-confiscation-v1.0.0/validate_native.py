"""Author replay of A12.var04 sealed active-preparation transfer pair."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, validate as check_roundtrip

HERE = Path(__file__).resolve().parent
RUNS = {"early-high": "a12-var04-early-high-20260930-01", "late-high": "a12-var04-late-high-20260930-01"}
SHAS = {"early-high": "de69780b98779f8cf76f61f391bd4ecae97fe0f660fd6b8f26a5e61384174551",
        "late-high": "499e2b056b72cda8d4ada7918e65c692e06a3d2b5b8c852e2cba9a8177e6c88e"}
A0, A1, B2 = "<TEACH-AIR-01,0>", "<TEACH-AIR-01,1>", "<TEACH-AIR-02,2>"
BASIC, SECOND = "<BASIC-MISSION,TEACH-UNIT,0,0,0>", "<SECOND-MISSION,TEACH-UNIT,0,0,1>"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def expect(actual: object, target: object, name: str) -> None:
    if actual != target:
        raise ValueError(f"{name}: {actual!r} != {target!r}")


def near(actual: float, target: float, name: str, tolerance: float = 1e-4) -> None:
    if abs((actual or 0) - target) > tolerance:
        raise ValueError(f"{name}: {actual!r} != {target!r}")


def line(log: str, time: str, actor: str, phrase: str) -> None:
    pattern = rf"^Time: {re.escape(time)} {re.escape(actor)} {re.escape(phrase)}(?:$|[,: ])"
    if len(re.findall(pattern, log, re.M)) != 1:
        raise ValueError(f"missing/duplicate event {time} {actor} {phrase}")


def table(report: dict, name: str) -> tuple[list[str], list[list]]:
    t = next(x for x in report["report"]["tables"] if x["name"] == name)
    return [x["name"] for x in t["columns"]], [row for i in t["instances"] for row in i["rows"]]


def level(a: float, b: float, intervals: list[tuple[float, float, float]]) -> float:
    return sum(max(0.0, min(b, end) - max(a, start)) * count / (b-a) for start, end, count in intervals)


def one(variant: str) -> dict:
    run = HERE / "runs" / RUNS[variant]
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    expect(closure["error"], None, "closure")
    expect(closure["source_hashes_before"], closure["source_hashes_after"], "stable source")
    expect(sha(run / "invocation.json"), closure["invocation_sha256"], "invocation seal")
    expect(invocation["variant"], variant, "variant")
    expect(invocation["input_sha256"], SHAS[variant], "input")
    expect(invocation["session_id"], 0, "session")
    expect(invocation["gui"]["pid"], 13340, "GUI PID")
    expect(invocation["gui"]["session_id"], 1, "GUI session")
    expect(invocation["queue_mutex"], r"Global\SimloxIssue18NativeQueue", "queue")
    sources = {"input": HERE / f"{variant}-input.json", "parent": HERE.parent / "A12-mission-priority-contention-v1.0.0" / "basic-high-input.json",
               "contract": HERE / "contract.json", "builder": HERE / "build.py", "checker": HERE / "check_roundtrip.py",
               "runner_script": HERE / "run_native_ssh.ps1"}
    for name, path in sources.items():
        expect(sha(path), closure["source_hashes_before"][name], f"source {name}")
    for name, record in closure["raw"].items():
        expect((run / name).stat().st_size, record["bytes"], f"bytes {name}")
        expect(sha(run / name), record["sha256"], f"hash {name}")
    expect([s["name"] for s in steps], ["import", "export", "calc", "jsonreport", "check_import_export"], "steps")
    if any(s["status"] != "completed" or s["exit_code"] != 0 or not s["gui_preserved"] for s in steps):
        raise ValueError("step failed or GUI changed")
    rt = check_roundtrip(run)
    if not rt["passed"] or len(rt["populated_tables"]) != 16:
        raise ValueError(f"roundtrip: {rt}")
    calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    if "Input conversion completed. Errors: 0, Warnings: 3, Notes: 0" not in calc or "Total execution time:" not in calc:
        raise ValueError("conversion/calc completion differs")
    expect(sorted(map(int, re.findall(r"warning #(\d+)", calc))), [108, 126, 126], "warnings")
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    line(log, "7", "<TEACH-UNIT>", "mission ordered: BASIC-MISSION")
    line(log, "7.25", "<TEACH-UNIT>", "mission ordered: SECOND-MISSION")
    for aircraft in (A0, B2):
        line(log, "7", BASIC, f"mission allocates system: {aircraft}")
        line(log, "7", aircraft, f"preparation started, mission: {BASIC}")
    line(log, "7.25", SECOND, f"mission allocates system: {A1}")
    line(log, "7.25", A1, f"preparation started, mission: {SECOND}")
    line(log, "7.75", A1, f"preparation ended, mission: {SECOND}")
    if variant == "early-high":
        for aircraft in (A0, B2):
            line(log, "7.5", aircraft, f"preparation ended, mission: {BASIC}")
        line(log, "8", BASIC, "mission starting")
        line(log, "10", BASIC, "mission success")
        line(log, "10", BASIC, "mission completed")
        line(log, "8.08333", SECOND, "mission cancelled")
        line(log, "8.08333", A1, f"turnround ended, mission: {SECOND}")
        prep = [(7, 7.5, 2), (7.25, 7.75, 1)]
        assigned = [(7, 10, 2), (7.25, 8.0833333333, 1)]
        operation = [(8, 10, 2)]
        winner, loser, cancel = "BASIC-MISSION", "SECOND-MISSION", 8.08333
    else:
        line(log, "7.25", BASIC, f"mission gives away system: {B2}")
        line(log, "7.25", SECOND, f"mission preassigns a system: {B2}")
        line(log, "7.25", "", f"subtask 1 seqno 0 within system preparation task 1 on {B2} ordered to stop")
        line(log, "7.25", "", f"system preparation task 1 on {B2} stopped")
        line(log, "7.25", B2, f"preparation ended, mission: {BASIC}")
        line(log, "7.25", B2, f"turnround started, mission: {BASIC} reduction factor: 0.5")
        line(log, "7.25", B2, f"turnround ended, mission: {BASIC}")
        line(log, "7.25", SECOND, f"mission allocates system: {B2}")
        line(log, "7.25", B2, f"preparation started, mission: {SECOND}")
        line(log, "7.75", B2, f"preparation ended, mission: {SECOND}")
        line(log, "7.5", A0, f"preparation ended, mission: {BASIC}")
        line(log, "7.83333", BASIC, "mission cancelled")
        line(log, "7.83333", A0, f"turnround ended, mission: {BASIC}")
        line(log, "8.25", SECOND, "mission starting")
        line(log, "10.25", SECOND, "mission success")
        line(log, "10.25", SECOND, "mission completed")
        prep = [(7, 7.5, 1), (7, 7.25, 1), (7.25, 7.75, 2)]
        assigned = [(7, 7.8333333333, 1), (7, 10.25, 1), (7.25, 10.25, 1)]
        operation = [(8.25, 10.25, 2)]
        winner, loser, cancel = "SECOND-MISSION", "BASIC-MISSION", 7.83333
    if len(re.findall(r" mission starting, duration:", log)) != 1 or len(re.findall(r" mission cancelled:", log)) != 1:
        raise ValueError("mission outcome counts differ")
    report = parse_native(run / "report-raw.json")
    cols, rows = table(report, "ResultSummary")
    expect(len(rows), 1, "summary rows")
    summary = dict(zip(cols, rows[0]))
    expect(summary["NREP"], 1, "repetitions")
    expect(summary["RTIUP"], 36, "horizon")
    for field in ("MTMF", "MSTF", "MSUF", "STMF"):
        near(summary[field], 0.5, f"summary {field}")
    sc, systems = table(report, "SystemResults")
    tc, stocks = table(report, "StockTotalResults")
    expect(len(systems), 72, "system bins")
    expect(len(stocks), 72, "stock bins")
    si = {field: sc.index(field) for field in ("STINT", "ETINT", "NSYRY", "NSYMA", "NSYMP", "NSYMO", "NSYMT", "NFAIL", "NPMT")}
    ti = {field: tc.index(field) for field in ("STINT", "ETINT", "NBO", "NBOU", "NDF", "NDD", "NDR", "NDP", "NWT")}
    for i, row in enumerate(systems):
        a, b = i*.5, (i+1)*.5
        near(row[si["STINT"]], a, f"system bin start {i}")
        near(row[si["ETINT"]], b, f"system bin end {i}")
        av = level(a, b, assigned)
        near(row[si["NSYMA"]], av, f"assigned {i}")
        near(row[si["NSYRY"]], 3-av, f"ready {i}")
        near(row[si["NSYMP"]], level(a, b, prep), f"preparing {i}")
        near(row[si["NSYMO"]], level(a, b, operation), f"operation {i}")
        for field in ("NSYMT", "NFAIL", "NPMT"):
            near(row[si[field]], 0, f"{field} {i}")
    for i, row in enumerate(stocks):
        near(row[ti["STINT"]], i*.5, f"stock start {i}")
        near(row[ti["ETINT"]], (i+1)*.5, f"stock end {i}")
        for field in ("NBO", "NBOU", "NDF", "NDD", "NDR", "NDP", "NWT"):
            near(row[ti[field]], 0, f"stock {field} {i}")
    expect(systems[-1][si["NSYRY"]], 3, "terminal ready")
    return {"variant": variant, "run_id": RUNS[variant], "closure_sha256": sha(run / "closure.json"), "winner": winner,
            "loser": loser, "cancel_hour": cancel, "preparation_aircraft_hours": 1.5 if variant == "early-high" else 1.75,
            "mission_aircraft_hours": 4.0, "system_bins": 72, "stock_bins": 72, "terminal_ready": 3}


def main() -> int:
    try:
        result = {"schema": "simlox-a12-var04-active-prep-confiscation-v100-author-validation/v1", "passed": True,
                  "variants": {variant: one(variant) for variant in RUNS}}
    except (OSError, ValueError, KeyError, TypeError, IndexError, StopIteration) as exc:
        result = {"schema": "simlox-a12-var04-active-prep-confiscation-v100-author-validation/v1", "passed": False,
                  "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
