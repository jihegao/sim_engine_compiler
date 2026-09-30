"""Source-bound author replay of the two A12 mission-priority native runs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

from check_roundtrip import parse_native, validate as roundtrip

HERE = Path(__file__).resolve().parent
RUNS = {"basic-high": "a12-basic-high-20260930-01", "second-high": "a12-second-high-20260930-01"}
SOURCE_SHA = {"basic-high": "300f3129b1f5d78018ad00875b545ffc1d7619dde5c3086c7a8bf0abb145094a",
              "second-high": "84e6a73b74502d259588e38ef43415d4e9c2d2f29307622a0fdd5e4c5d2c5135"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def eq(actual: object, expected: object, label: str) -> None:
    if actual != expected:
        raise ValueError(f"{label}: {actual!r} != {expected!r}")


def near(actual: float, expected: float, label: str, tol: float = 1e-4) -> None:
    if abs(actual - expected) > tol:
        raise ValueError(f"{label}: {actual!r} != {expected!r}")


def table(report: dict, name: str) -> tuple[list[str], list[list]]:
    t = next(x for x in report["report"]["tables"] if x["name"] == name)
    return [x["name"] for x in t["columns"]], [row for ins in t["instances"] for row in ins["rows"]]


def expect_line(log: str, pattern: str, label: str) -> None:
    if len(re.findall(pattern, log, re.M)) != 1:
        raise ValueError(f"expected exactly one {label}")


def one(variant: str) -> dict:
    run = HERE / "runs" / RUNS[variant]
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    eq(closure["error"], None, "closure error")
    eq(invocation["variant"], variant, "variant")
    eq(invocation["session_id"], 0, "SSH session")
    eq(invocation["gui"]["pid"], 13340, "GUI PID")
    eq(invocation["gui"]["session_id"], 1, "GUI session")
    eq(invocation["queue_mutex"], r"Global\SimloxIssue18NativeQueue", "queue")
    eq(sha(run / "invocation.json"), closure["invocation_sha256"], "invocation hash")
    eq(closure["source_hashes_before"], closure["source_hashes_after"], "source stability")
    eq(invocation["input_sha256"], SOURCE_SHA[variant], "input hash")
    paths = {"input": HERE / f"{variant}-input.json", "parent": HERE.parent / "A11-mixed-type-minimum-v1.0.0" / "required-input.json",
             "contract": HERE / "contract.json", "builder": HERE / "build.py", "checker": HERE / "check_roundtrip.py",
             "runner_script": HERE / "run_native_ssh.ps1"}
    for key, path in paths.items():
        eq(sha(path), closure["source_hashes_before"][key], f"source {key}")
    for name, record in closure["raw"].items():
        eq((run / name).stat().st_size, record["bytes"], f"raw bytes {name}")
        eq(sha(run / name), record["sha256"], f"raw hash {name}")
    eq([step["name"] for step in steps], ["import", "export", "calc", "jsonreport", "check_import_export"], "steps")
    if any(step["status"] != "completed" or step["exit_code"] != 0 or not step["gui_preserved"] for step in steps):
        raise ValueError("incomplete native step or GUI changed")
    check = roundtrip(run)
    if not check["passed"] or len(check["populated_tables"]) != 16:
        raise ValueError(f"source roundtrip failed: {check}")
    calc = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    if "Input conversion completed. Errors: 0, Warnings: 3, Notes: 0" not in calc or "Total execution time:" not in calc:
        raise ValueError("conversion or calculation completion differs")
    eq(sorted(map(int, re.findall(r"warning #(\d+)", calc))), [108, 126, 126], "warnings")

    high, low = ("BASIC-MISSION", "SECOND-MISSION") if variant == "basic-high" else ("SECOND-MISSION", "BASIC-MISSION")
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    for kind, time, ident in (("mission ordered", "7", high), ("mission ordered", "7", low)):
        expect_line(log, rf"^Time: {time} <TEACH-UNIT> {kind}: {ident}$", f"{ident} {kind}")
    high_tag = rf"<{high},TEACH-UNIT,0,0,0>"
    low_tag = rf"<{low},TEACH-UNIT,0,0,1>"
    for tag, aircraft in ((high_tag, "<TEACH-AIR-01,0>"), (high_tag, "<TEACH-AIR-02,2>"), (low_tag, "<TEACH-AIR-01,1>")):
        expect_line(log, rf"^Time: 7 {tag} mission allocates system: {aircraft}$", f"allocation {tag} {aircraft}")
    for tag, aircraft in ((high_tag, "<TEACH-AIR-01,0>"), (high_tag, "<TEACH-AIR-02,2>"), (low_tag, "<TEACH-AIR-01,1>")):
        expect_line(log, rf"^Time: 7 {aircraft} preparation started, mission: {tag}$", f"prep start {aircraft}")
        expect_line(log, rf"^Time: 7\.5 {aircraft} preparation ended, mission: {tag}$", f"prep end {aircraft}")
    expect_line(log, rf"^Time: 7 {low_tag} mission waiting:  timeout at 7\.83333$", "low waits")
    expect_line(log, rf"^Time: 7\.83333 {low_tag} mission cancelled: $", "low cancels")
    expect_line(log, rf"^Time: 8 {high_tag} mission starting, duration: 2 : <TEACH-AIR-01,0>,<TEACH-AIR-02,2>$", "high starts")
    for kind in ("mission success", "mission completed"):
        expect_line(log, rf"^Time: 10 {high_tag} {kind}:", f"high {kind}")
    expect_line(log, rf"^Time: 7\.83333 <TEACH-AIR-01,1> turnround ended, mission: {low_tag}$", "low aircraft released")
    if len(re.findall(r" mission starting, duration:", log)) != 1 or len(re.findall(r" mission cancelled:", log)) != 1:
        raise ValueError("unexpected mission outcome count")

    report = parse_native(run / "report-raw.json")
    summary_cols, summary_rows = table(report, "ResultSummary")
    eq(len(summary_rows), 1, "summary rows")
    summary = dict(zip(summary_cols, summary_rows[0]))
    for field in ("MTMF", "MSTF", "MSUF", "STMF"):
        near(summary[field], 0.5, f"summary {field}")
    eq(summary["NREP"], 1, "repetitions")
    eq(summary["RTIUP"], 36, "horizon")
    system_cols, systems = table(report, "SystemResults")
    stock_cols, stocks = table(report, "StockTotalResults")
    eq(len(systems), 72, "system bins")
    eq(len(stocks), 72, "stock bins")
    ix = {name: system_cols.index(name) for name in ("STINT", "ETINT", "NSYRY", "NSYMA", "NSYMP", "NSYMO", "NSYMT", "NFAIL", "NPMT")}
    def occupancy(a: float, b: float, intervals: list[tuple[float, float, float]]) -> float:
        return sum(max(0.0, min(b, end) - max(a, start)) * count / (b-a) for start, end, count in intervals)
    for i, row in enumerate(systems):
        start, end = i * 0.5, (i + 1) * 0.5
        near(row[ix["STINT"]], start, f"system start {i}")
        near(row[ix["ETINT"]], end, f"system end {i}")
        assigned = occupancy(start, end, [(7, 7.833333333333333, 3), (7.833333333333333, 10, 2)])
        near(row[ix["NSYMA"]], assigned, f"assigned bin {i}")
        near(row[ix["NSYRY"]], 3-assigned, f"ready bin {i}")
        near(row[ix["NSYMP"]], occupancy(start, end, [(7, 7.5, 3)]), f"prep bin {i}")
        near(row[ix["NSYMO"]], occupancy(start, end, [(8, 10, 2)]), f"operation bin {i}")
        near(row[ix["NSYMT"]], 0, f"turnround bin {i}")
        for field in ("NFAIL", "NPMT"):
            near(row[ix[field]], 0, f"{field} bin {i}")
    sx = {name: stock_cols.index(name) for name in ("STINT", "ETINT", "NBO", "NBOU", "NDF", "NDD", "NDR", "NDP", "NWT")}
    for i, row in enumerate(stocks):
        near(row[sx["STINT"]], i*.5, f"stock start {i}")
        near(row[sx["ETINT"]], (i+1)*.5, f"stock end {i}")
        for field in ("NBO", "NBOU", "NDF", "NDD", "NDR", "NDP", "NWT"):
            near(row[sx[field]] or 0, 0, f"stock {field} bin {i}")
    eq(systems[-1][ix["NSYRY"]], 3, "terminal ready")
    return {"variant": variant, "run_id": RUNS[variant], "closure_sha256": sha(run / "closure.json"), "high": high,
            "low": low, "cancel_hour": 7.83333, "preparation_aircraft_hours": 1.5, "mission_aircraft_hours": 4.0,
            "system_bins": 72, "stock_bins": 72, "terminal_ready": 3, "warnings": [108, 126, 126]}


def main() -> int:
    try:
        result = {"schema": "simlox-a12-priority-contention-v100-author-validation/v1", "passed": True,
                  "variants": {v: one(v) for v in RUNS}}
    except (OSError, ValueError, KeyError, TypeError, IndexError, StopIteration) as exc:
        result = {"schema": "simlox-a12-priority-contention-v100-author-validation/v1", "passed": False,
                  "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
