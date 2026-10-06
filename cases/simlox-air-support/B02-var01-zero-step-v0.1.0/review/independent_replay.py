"""Independent, read-only replay of the sealed B02.var01 zero-step run.

Uses only standard-library parsers and frozen source/raw files. It does not
import either author validator or invoke SIMLOX.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import math
import re
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN_ID = "b02-var01-zero-step-v010-ssh-20261006-01"
RUN = CASE / "runs" / RUN_ID
PARENT = ROOT / "B02-serial-preparation-v1.0.2"
PARENT_RUN = Path(
    r"C:\Users\user\dev\sim_engine_compiler-b02-v102\cases\simlox-air-support"
    r"\B02-serial-preparation-v1.0.2\runs\b02-v102-ssh-20260929-01"
)
PREREQ_RUN = Path(
    r"C:\Users\user\dev\sim_engine_compiler-b01-v101\cases\simlox-air-support"
    r"\B01-fixed-preparation-v1.0.1\runs\b01-v101-ssh-20260929-06"
)
EXPECTED = {
    CASE / "contract.json": "025c61d348fb2bb651fa7ef28fdd5d573bfd227e3256522e7255c0a60116fe39",
    CASE / "native-input.json": "2bc50fd4bc65a2036c85683605bb4eb6201ba0126902d3ffa33eb2106c1a8a46",
    CASE / "validate_native_cli.py": "c0dbe248142fdf2b9c8c285c09c9e08bb73f9c4d588790954f00d200d4a088a5",
    CASE / "validate_native_cli_v011.py": "04e4d553ad1f19e406fe5557371854d6ecc4b985ec2907df44342275850435c1",
    CASE / "review" / "author-validation-v010-no-go.json": "10dd07db55710502d6aa0c4ccd053afef0a8c528d6e4e8b7b6e55e2d7a34277e",
    CASE / "review" / "author-validation-v011.json": "4c76135ee46431ad2fe8ade475309ce986ad285d45a0a52d96a9c3f6e1d01c14",
    RUN / "closure.json": "22ed75df3a56b72ecb83369920f541051872d78911a9e52c77e657e8ad32eeb2",
    PARENT / "native-input.json": "fc9e80de0ac8515f3d3a7fe4a2c9aa916bce23ba5b05e13e2f69857230d9dc34",
    PARENT_RUN / "closure.json": "3bbaffe3460da2195a4084cb3b92e1fc9c605a5d01380619abf92e3cd107f570",
    PREREQ_RUN / "closure.json": "046a7724f053f63e6967e3c3e803f726fd5f4b6322015239cb25a380c6446516",
}


class Audit:
    def __init__(self) -> None:
        self.checks = 0
        self.failures: list[str] = []

    def check(self, label: str, good: bool) -> None:
        self.checks += 1
        if not good:
            self.failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(path: Path, *, native: bool = False) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    if native:
        # SIMLOX default JSON can have trailing commas. The source file is untouched.
        text = re.sub(r",\s*([}\]])", r"\1", text)
    return json.loads(text)


def tables(path: Path, top: str, *, native: bool = False) -> dict:
    return {t["name"]: t for t in parse(path, native=native)[top]["tables"]}


def raw_seals(a: Audit, folder: Path, closure: dict, label: str) -> None:
    for name, record in closure["raw"].items():
        path = folder / name
        a.check(f"{label}/{name}/exists", path.is_file())
        if path.is_file():
            a.check(f"{label}/{name}/size", path.stat().st_size == record["bytes"])
            a.check(f"{label}/{name}/sha", sha(path) == record["sha256"])


def event(a: Audit, lines: list[str], label: str, token: str, time: float) -> None:
    hits = [line for line in lines if token in line]
    a.check(f"event/{label}/count", len(hits) == 1)
    if len(hits) == 1:
        match = re.match(r"Time: (\d+(?:\.\d+)?)\b", hits[0])
        a.check(
            f"event/{label}/time",
            bool(match and math.isclose(float(match.group(1)), time, abs_tol=1e-4)),
        )


def replay() -> dict:
    a = Audit()
    for path, digest in EXPECTED.items():
        a.check(f"pin/{path.name}", path.is_file() and sha(path) == digest)

    child_closure = parse(RUN / "closure.json")
    parent_closure = parse(PARENT_RUN / "closure.json")
    prereq_closure = parse(PREREQ_RUN / "closure.json")
    raw_seals(a, RUN, child_closure, "child")
    raw_seals(a, PARENT_RUN, parent_closure, "parent")
    raw_seals(a, PREREQ_RUN, prereq_closure, "B01")
    a.check("child/raw-count", len(child_closure["raw"]) == 12)
    a.check("parent/raw-count", len(parent_closure["raw"]) == 11)
    a.check("B01/raw-count", len(prereq_closure["raw"]) == 11)
    a.check("closure/run", child_closure["run_id"] == RUN_ID)
    a.check("closure/no-error", child_closure["error"] is None)
    a.check("closure/source-stable", child_closure["source_hashes_before"] == child_closure["source_hashes_after"])
    a.check("closure/input-pin", child_closure["source_hashes_before"]["child_input"] == EXPECTED[CASE / "native-input.json"])
    a.check("closure/contract-pin", child_closure["source_hashes_before"]["child_contract"] == EXPECTED[CASE / "contract.json"])
    a.check("closure/validator-pin", child_closure["source_hashes_before"]["behavior_validator"] == EXPECTED[CASE / "validate_native_cli.py"])
    a.check("closure/invocation-seal", sha(RUN / "invocation.json") == child_closure["invocation_sha256"])

    invocation = parse(RUN / "invocation.json")
    steps = parse(RUN / "steps.json")
    a.check("guard/ssh0", invocation["session_id"] == 0 and invocation["ssh_connection_present"])
    a.check("guard/sshd", "sshd.exe" in invocation["ssh_ancestor_names"])
    a.check("guard/mutex", invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
    gui = invocation["gui"]
    a.check("guard/gui", gui["pid"] == 13340 and gui["session_id"] == 1 and gui["start_unix_ms"] == 1790590196826)
    a.check("steps/order", [s["name"] for s in steps] == ["import", "export", "check_import_export", "calc", "jsonreport"])
    for step in steps:
        a.check(f"step/{step['name']}", step["exit_code"] == 0 and step["status"] == "completed" and step["gui_preserved"])

    old = parse(CASE / "review" / "author-validation-v010-no-go.json")
    new = parse(CASE / "review" / "author-validation-v011.json")
    a.check("validator/original-failure-preserved", old["decision"] == "NO_GO" and old["failures"] == [
        "event/one system preparation task complete: 3 != 1",
        "event/system preparation task complete at h7.333333333333333: False != True",
    ])
    a.check("validator/correction-outcome", new["decision"] == "GO_BOUNDED" and not new["failures"] and new["checks"] == old["checks"])
    before = (CASE / "validate_native_cli.py").read_text(encoding="utf-8").splitlines()
    after = (CASE / "validate_native_cli_v011.py").read_text(encoding="utf-8").splitlines()
    diff = [line for line in difflib.ndiff(before, after) if line.startswith(("- ", "+ "))]
    a.check("validator/diff-six-lines", len(diff) == 8)
    a.check("validator/regex-anchored", any("^Time: \\d+" in line and line.startswith("+ ") for line in diff))
    a.check("validator/native-pin-original", child_closure["source_hashes_before"]["behavior_validator"] == sha(CASE / "validate_native_cli.py"))

    parent = tables(PARENT / "native-input.json", "model")
    child = tables(CASE / "native-input.json", "model")
    a.check("source/table-set", list(parent) == list(child))
    changed = []
    cells = 0
    for name in parent:
        left, right = parent[name], child[name]
        a.check(f"source/{name}/columns", left["columns"] == right["columns"])
        for ii, (li, ri) in enumerate(zip(left["instances"], right["instances"])):
            a.check(f"source/{name}/{ii}/instance", li["instance_name"] == ri["instance_name"])
            for row, (lr, rr) in enumerate(zip(li["rows"], ri["rows"])):
                for col, (lv, rv) in enumerate(zip(lr, rr)):
                    cells += 1
                    if lv != rv:
                        changed.append((name, ii, row, left["columns"][col]["name"], lv, rv))
    a.check("source/185-cells", cells == 185)
    a.check("source/sole-DURN", changed == [("TaskBreakDown", 0, 0, "DURN", 1 / 6, 0)])
    a.check("source/run-copy", (RUN / "input.json").read_bytes() == (CASE / "native-input.json").read_bytes())

    exported = tables(RUN / "roundtrip-raw.json", "model", native=True)
    populated = 0
    for name, authored in child.items():
        if any(instance["rows"] for instance in authored["instances"]):
            populated += 1
            actual = exported[name]
            a.check(f"roundtrip/{name}/columns", [c["name"] for c in authored["columns"]] == [c["name"] for c in actual["columns"]])
            a.check(f"roundtrip/{name}/instances", authored["instances"] == actual["instances"])
    a.check("roundtrip/17-tables", populated == 17)
    a.check("roundtrip/frozen-checker", parse(RUN / "roundtrip-validation.json")["passed"] is True)
    run_log = (RUN / "run.log").read_text(encoding="utf-8")
    a.check("converter/summary", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in run_log)
    a.check("converter/warnings", re.findall(r"warning #(\d+)", run_log) == ["108", "126"])
    a.check("converter/no-other-diagnostics", not re.findall(r"(?:error|note) #\d+", run_log, re.I))
    a.check("converter/SXO-substantive", (RUN / "model.sxo").stat().st_size > 4)

    lines = (RUN / "model.log").read_text(encoding="utf-8").splitlines()
    key_events = [
        ("mission-order", "<TEACH-UNIT> mission ordered: BASIC-MISSION", 7),
        ("allocated-id0", "mission allocates system: <TEACH-AIR-01,0>", 7),
        ("prep-start", "<TEACH-AIR-01,0> preparation started, mission:", 7),
        ("main-start", "  system preparation task 0 on <TEACH-AIR-01,0> started", 7),
        ("seq1-start", "subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> started", 7),
        ("seq1-zero", "subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> starts performing, planned to last for 0 hours", 7),
        ("seq1-end", "subtask 0 seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> completed", 7),
        ("seq2-start", "subtask 1 seqno 2 within system preparation task 0 on <TEACH-AIR-01,0> started", 7),
        ("seq2-third", "subtask 1 seqno 2 within system preparation task 0 on <TEACH-AIR-01,0> starts performing, planned to last for 0.333333 hours", 7),
        ("seq2-end", "subtask 1 seqno 2 within system preparation task 0 on <TEACH-AIR-01,0> completed", 7 + 1 / 3),
        ("main-end", "  system preparation task 0 on <TEACH-AIR-01,0> completed", 7 + 1 / 3),
        ("prep-end", "<TEACH-AIR-01,0> preparation ended, mission:", 7 + 1 / 3),
        ("mission-start", "mission starting, duration: 2 : <TEACH-AIR-01,0>", 8),
        ("mission-task-start", "task starting: <TEACH-AIR-01,0>", 8.5),
        ("mission-task-end", "task completed: <TEACH-AIR-01,0>", 9.5),
        ("mission-success", "mission success:", 10),
        ("mission-complete", "mission completed: <TEACH-AIR-01,0>", 10),
        ("physical-return", "System arrives <TEACH-AIR-01,0>, mission success", 10),
    ]
    for label, token, time in key_events:
        event(a, lines, label, token, time)
    a.check("events/zero-unwanted", all(not any(bad in line for bad in ("mission cancelled", "waits for resources", "planned to last for 0.166667 hours")) for line in lines))
    sequence = [next((i for i, line in enumerate(lines) if token in line), -1) for _, token, _ in key_events]
    a.check("events/serial-order", sequence == sorted(sequence) and min(sequence) >= 0)

    base_report = tables(PARENT_RUN / "report-raw.json", "report", native=True)
    child_report = tables(RUN / "report-raw.json", "report", native=True)
    a.check("report/table-set", set(base_report) == set(child_report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    expected_changes = {
        (14, "NSYMP"): (1.0, 2 / 3),
        (14, "NSYMR"): (0.0, 1 / 3),
        (14, "NPSUC"): (0.0, 1.0),
        (15, "NPSUC"): (1.0, 0.0),
    }
    observed_changes = set()
    for name in sorted(base_report):
        left, right = base_report[name], child_report[name]
        lcols = [c["name"] for c in left["columns"]]
        rcols = [c["name"] for c in right["columns"]]
        a.check(f"report/{name}/columns", lcols == rcols)
        lr = left["instances"][0]["rows"]
        rr = right["instances"][0]["rows"]
        a.check(f"report/{name}/row-count", len(lr) == len(rr) == (72 if name.endswith("Results") else 1))
        for row_i, (lrow, rrow) in enumerate(zip(lr, rr)):
            for col_i, (lv, rv) in enumerate(zip(lrow, rrow)):
                field = lcols[col_i]
                gate = expected_changes.get((row_i, field)) if name == "SystemResults" else None
                if gate:
                    observed_changes.add((row_i, field))
                    a.check(f"report/{name}/{row_i}/{field}/parent", math.isclose(lv, gate[0], abs_tol=1e-6))
                    a.check(f"report/{name}/{row_i}/{field}/child", math.isclose(rv, gate[1], abs_tol=1e-6))
                else:
                    a.check(f"report/{name}/{row_i}/{field}/equal", lv == rv)
    a.check("report/four-changes", observed_changes == set(expected_changes))
    sys = child_report["SystemResults"]
    cols = [c["name"] for c in sys["columns"]]
    rows = sys["instances"][0]["rows"]
    a.check("report/half-hour-grid", all(math.isclose(r[cols.index("STINT")], i / 2) and math.isclose(r[cols.index("ETINT")], (i + 1) / 2) for i, r in enumerate(rows)))
    for field, target in (("NSYRY", 33), ("NSYMP", 1 / 3), ("NSYMR", 2 / 3), ("NSYMO", 2)):
        total = sum((r[cols.index(field)] or 0) * (r[cols.index("ETINT")] - r[cols.index("STINT")]) for r in rows)
        a.check(f"report/integral/{field}", math.isclose(total, target, abs_tol=1e-6))
    a.check("report/terminal-ready", rows[-1][cols.index("NSYRY")] == 1)
    return {
        "schema": "b02-var01-zero-step-independent-replay/v1",
        "decision": "GO_BOUNDED" if not a.failures else "NO_GO",
        "checks": a.checks,
        "failures": a.failures,
        "run_id": RUN_ID,
        "contract_sha256": EXPECTED[CASE / "contract.json"],
        "closure_sha256": EXPECTED[RUN / "closure.json"],
        "scope": "One fixed-seed two-subtask preparation with instantaneous SEQ1; v0.1.0 author NO_GO remains preserved and v0.1.1 changes a false-positive completion pattern only.",
        "limits": [
            "The source Tasks.DESCR still says 10+20-minute; numeric SEQ1 duration is zero.",
            "MissionPreparation.DURN 0.75 is overridden by the linked breakdown.",
            "No resource competition, repeated mission, alternate seed, GUI visual, or general zero-duration inference.",
        ],
    }


if __name__ == "__main__":
    result = replay()
    target = CASE / "review" / "independent-verdict.json"
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"decision": result["decision"], "checks": result["checks"], "failures": result["failures"]}))
    raise SystemExit(0 if result["decision"] == "GO_BOUNDED" else 1)
