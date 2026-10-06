"""Predeclared read-only native behavior gate for the two C06.var03 arms."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import sys

from check_roundtrip import INPUT_SHA, parse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "C06-alternative-resource-v1.0.0" / "runs" / "c06-primary-0-artf-2-20260930-01"
PARENT_REPORT_SHA = "55385e93470fd9730c87162ef33c532f6f5673b5cfd25512924e63afd83b0fcc"
REPORT_TABLES = {"ProblemDescription": (1, 1), "ResultSummary": (1, 11),
                 "SystemResults": (72, 40), "StockTotalResults": (72, 16),
                 "ResourceResults": (72, 16), "ResourceResultsTotal": (1, 14)}
RUN_IDS = {"factor1": "c06-var03-v101-factor1-ssh-20261007-01",
           "factor3": "c06-var03-v101-factor3-ssh-20261007-01"}


class Gate:
    def __init__(self):
        self.count = 0
        self.failures = []

    def check(self, condition, label):
        self.count += 1
        if not condition:
            self.failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table_map(doc: dict) -> dict:
    result = {}
    for t in doc["report"]["tables"]:
        assert t["name"] not in result
        assert len(t["instances"]) == 1
        result[t["name"]] = t
    return result


def near(actual, expected, tolerance=3e-5):
    if isinstance(actual, (int, float)) and not isinstance(actual, bool) and isinstance(expected, (int, float)) and not isinstance(expected, bool):
        return math.isfinite(actual) and abs(actual - expected) <= tolerance
    return type(actual) is type(expected) and actual == expected


def overlap(a, b, start, end):
    return max(0.0, min(b, end) - max(a, start))


def expected_system(parent: dict, arm: str) -> list[list]:
    t = parent["SystemResults"]
    cols = [c["name"] for c in t["columns"]]
    rows = [r.copy() for r in t["instances"][0]["rows"]]
    if arm == "factor1":
        return rows
    for i, row in enumerate(rows):
        a, b = i * .5, (i + 1) * .5
        values = {
            "NSYRY": 2 * (overlap(a, b, 0, 7.5) + overlap(a, b, 9.5, 36)) / .5,
            "NSYMA": 2 * overlap(a, b, 7.5, 9.5) / .5,
            "NSYMO": 2 * overlap(a, b, 8.5, 9.5) / .5,
            "NSYMP": 2 * overlap(a, b, 7.5, 8.5) / .5,
            "FTMO": overlap(a, b, 8.5, 9.5) / .5,
            "STACC": 2 * overlap(a, b, 8.5, 9.5) / .5,
            "NPSTA": 2 if i == 15 else 0,
            "NPSUC": 2 if i == 17 else 0,
        }
        for col, value in values.items():
            row[cols.index(col)] = value
    return rows


def expected_resource(parent: dict, arm: str) -> tuple[list[list], list[list]]:
    t = parent["ResourceResults"]
    cols = [c["name"] for c in t["columns"]]
    rows = [r.copy() for r in t["instances"][0]["rows"]]
    end = 8.5 if arm == "factor3" else 8 + 1/6
    for i, row in enumerate(rows):
        for col in ("NR", "NRA", "NRN"):
            row[cols.index(col)] = 4
        row[cols.index("NRUM")] = 4 * overlap(i * .5, (i+1)*.5, 7.5, end) / .5
    total = [r.copy() for r in parent["ResourceResultsTotal"]["instances"][0]["rows"]]
    total_cols = [c["name"] for c in parent["ResourceResultsTotal"]["columns"]]
    for col in ("NR", "NRA", "NRN"):
        total[0][total_cols.index(col)] = 4
    total[0][total_cols.index("NRUM")] = 4 * (end - 7.5) / 36
    return rows, total


def assert_event(g: Gate, lines: list[str], time: float, token: str, count: int, label: str, tolerance=1e-4):
    matched = []
    for line in lines:
        m = re.match(r"Time:\s*([0-9.eE+-]+)\s", line)
        if m and abs(float(m.group(1)) - time) <= tolerance and token in line:
            matched.append(line)
    g.check(len(matched) == count, f"{label}: {len(matched)} != {count}")


def check_events(g: Gate, run: Path, arm: str):
    lines = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace").splitlines()
    end = 8.5 if arm == "factor3" else 8 + 1/6
    finish = end + 1
    duration = 1.0 if arm == "factor3" else 2/3
    assert_event(g, lines, 7.5, "mission ordered: BASIC-MISSION", 1, "mission order")
    assert_event(g, lines, 7.5, "mission created:", 1, "mission created")
    assert_event(g, lines, 7.5, "mission activated, systems requested: 2", 1, "request two")
    for aircraft in (0, 1):
        owner = f"<TEACH-AIR-01,{aircraft}>"
        assert_event(g, lines, 7.5, f"mission allocates system: {owner}", 1, f"allocate {aircraft}")
        assert_event(g, lines, 7.5, f"{owner} preparation started", 1, f"prep start {aircraft}")
        assert_event(g, lines, end, f"{owner} preparation ended", 1, f"prep end {aircraft}")
        assert_event(g, lines, finish, f"{owner} turnround ended", 1, f"ready {aircraft}")
        assert_event(g, lines, 7.5, f"on {owner} starts performing, planned to last for", 1, f"work {aircraft}")
        work = [line for line in lines if f"on {owner} starts performing, planned to last for" in line]
        g.check(len(work) == 1 and any(abs(float(x) - duration) < 1e-5 for x in re.findall(r"last for\s+([0-9.]+)", work[0])), f"planned duration {aircraft}")
        assert_event(g, lines, end,
                     f"subtask {aircraft} seqno 1 within system preparation task {aircraft} on {owner} completed",
                     1, f"subtask completion {aircraft}")
    for rid, expected in (("P-CREW", "failed"), ("P-AUX", "failed"), ("P-ALT", "OK"), ("P-AUXALT", "OK")):
        g.check(sum((f"<{rid} at <BASE-01,0>>" in line and "Availability test" in line and expected in line) for line in lines) == 2,
                f"typed availability {rid}/{expected}")
    for rid in ("P-ALT", "P-AUXALT"):
        assert_event(g, lines, 7.5, f"<{rid} at <BASE-01,0>> allocated to maintenance task: 1", 2, f"booking {rid}")
        assert_event(g, lines, end, f"<{rid} at <BASE-01,0>> deallocated from  maintenance task: 1", 2, f"release {rid}")
    for rid in ("P-CREW", "P-AUX"):
        g.check(not any(f"<{rid} at <BASE-01,0>> allocated to maintenance task" in line for line in lines),
                f"primary unexpectedly booked {rid}")
    assert_event(g, lines, end, "mission starting, duration: 1", 1, "mission launch")
    assert_event(g, lines, finish, "mission success:", 1, "mission success")
    assert_event(g, lines, finish, "mission completed:", 1, "mission completion")
    for unwanted in ("mission cancelled", "mission aborted", "backorder", "failure occurs"):
        g.check(not any(unwanted in line.lower() for line in lines), f"unexpected {unwanted}")


def check_report(g: Gate, run: Path, arm: str):
    g.check(sha(PARENT / "report-raw.json") == PARENT_REPORT_SHA, "accepted report pin")
    original = table_map(parse(PARENT / "report-raw.json"))
    actual = table_map(parse(run / "report-raw.json"))
    g.check(set(actual) == set(REPORT_TABLES), "six selected report tables")
    expected = {name: [r.copy() for r in original[name]["instances"][0]["rows"]] for name in REPORT_TABLES}
    expected["ProblemDescription"][0][0] = (
        f"C06.var03 two alternative resource requirements; second ARTF {1 if arm == 'factor1' else 3}; first ARTF 2")
    expected["SystemResults"] = expected_system(original, arm)
    expected["ResourceResults"], expected["ResourceResultsTotal"] = expected_resource(original, arm)
    checked_cells = 0
    for name, (nrows, ncols) in REPORT_TABLES.items():
        if name not in actual:
            continue
        t = actual[name]
        reference = original[name]
        g.check(t["columns"] == reference["columns"], f"{name} columns")
        rows = t["instances"][0]["rows"]
        g.check(len(rows) == nrows, f"{name} row count")
        for i, want in enumerate(expected[name]):
            if i >= len(rows):
                break
            got = rows[i]
            g.check(len(got) == ncols, f"{name} row {i} width")
            for j, value in enumerate(want):
                if j >= len(got):
                    break
                g.check(near(got[j], value), f"{name}[{i},{j}] {got[j]!r} != {value!r}")
                checked_cells += 1
    g.check(checked_cells == 5210, f"checked report cells {checked_cells}")
    for name in ("SystemResults", "StockTotalResults", "ResourceResults"):
        if name not in actual:
            continue
        cols = [c["name"] for c in actual[name]["columns"]]
        rows = actual[name]["instances"][0]["rows"]
        for i, row in enumerate(rows):
            g.check(near(row[cols.index("STINT")], i*.5) and near(row[cols.index("ETINT")], (i+1)*.5),
                    f"{name} contiguous interval {i}")


def validate(run: Path, arm: str) -> dict:
    g = Gate()
    g.check(run.name == RUN_IDS[arm], "reserved run ID")
    g.check(sha(HERE / f"{arm}-input.json") == INPUT_SHA[arm], "frozen source input")
    g.check(sha(run / "input.json") == INPUT_SHA[arm], "copied run input")
    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    g.check(invocation["run_id"] == RUN_IDS[arm] and invocation["session_id"] == 0,
            "invocation identity/session")
    g.check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1
            and invocation["gui"]["start_unix_ms"] == 1790590196826, "protected GUI")
    g.check(invocation["source_hashes_before"][f"{arm}_input"] == INPUT_SHA[arm], "invocation source pin")
    rt = json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
    g.check(rt.get("passed") is True and rt.get("authored_row_tables") == 20, "exact 20-table roundtrip")
    log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    g.check("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in log,
            "converter 0/2/0")
    g.check(sorted(re.findall(r"(?:warning|Warning)\s*#(\d+)", log)) == ["108", "126"],
            "only warnings 108/126")
    check_events(g, run, arm)
    check_report(g, run, arm)
    return {"schema": "c06-var03-v101-author-validation/v1", "arm": arm,
            "run_id": RUN_IDS[arm], "decision": "GO_BOUNDED" if not g.failures else "NO_GO",
            "checks": g.count, "passed": g.count-len(g.failures), "failures": g.failures,
            "scope": "single fixed two-aircraft two-requirement native seed"}


if __name__ == "__main__":
    try:
        result = validate(Path(sys.argv[1]), sys.argv[2])
    except Exception as exc:
        result = {"schema": "c06-var03-v101-author-validation/v1", "decision": "NO_GO",
                  "checks": 1, "passed": 0, "failures": [f"{type(exc).__name__}: {exc}"]}
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["decision"] == "GO_BOUNDED" else 1)
