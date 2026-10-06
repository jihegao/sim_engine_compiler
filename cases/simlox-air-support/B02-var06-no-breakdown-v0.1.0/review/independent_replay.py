"""Independent read-only replay of B02.var06 sealed native evidence."""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN_ID = "b02-var06-no-breakdown-v010-ssh-20261006-01"
RUN = CASE / "runs" / RUN_ID
PARENT = ROOT / "B02-serial-preparation-v1.0.2"
B01 = ROOT / "B01-fixed-preparation-v1.0.1"
PARENT_RUN = Path(r"C:\Users\user\dev\sim_engine_compiler-b02-v102\cases\simlox-air-support\B02-serial-preparation-v1.0.2\runs\b02-v102-ssh-20260929-01")
B01_RUN = Path(r"C:\Users\user\dev\sim_engine_compiler-b01-v101\cases\simlox-air-support\B01-fixed-preparation-v1.0.1\runs\b01-v101-ssh-20260929-06")
EXPECTED_CONTRACT = "41b8b74938b0b21d7fb2353cc9d5d40d7eb935bcd249084d146483311a7ededa"
EXPECTED_INPUT = "7596ea50dc770bf9726a0d3300c0c2b0a881b772e57db0c3a079a3629714a939"
EXPECTED_CLOSURE = "4d6e84b6d32da692ff95219a149af547a9e196cf548adf3ad6968d2d8f72250f"
SOURCE_PATHS = {
    "child_input": CASE / "native-input.json",
    "child_contract": CASE / "contract.json",
    "contract_review": CASE / "review" / "independent-contract-go-2026-10-06.md",
    "builder": CASE / "build.py",
    "parent_diff_checker": CASE / "check_parent_diff.py",
    "roundtrip_checker": CASE / "check_roundtrip.py",
    "shared_parser": ROOT / "tools" / "validate_native.py",
    "behavior_validator": CASE / "validate_native_cli.py",
    "runner_script": CASE / "run_native_ssh.ps1",
    "accepted_input": PARENT / "native-input.json",
    "accepted_contract": PARENT / "contract.json",
    "accepted_diff": PARENT / "parent-diff.json",
    "accepted_evidence": PARENT / "evidence-2026-09-29.md",
    "accepted_verdict": PARENT / "review" / "independent-readonly-2026-09-29.json",
    "accepted_closure": PARENT_RUN / "closure.json",
    "prereq_input": B01 / "native-input.json",
    "prereq_contract": B01 / "contract.json",
    "prereq_evidence": B01 / "evidence-2026-09-29.md",
    "prereq_closure": B01_RUN / "closure.json",
    "installed_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "installed_manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "installed_dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    "prelaunch_approval": CASE / "review" / "independent-prelaunch-go.json",
}


class Audit:
    def __init__(self) -> None:
        self.checks = 0
        self.failures: list[str] = []

    def check(self, label: str, predicate: bool) -> None:
        self.checks += 1
        if not predicate:
            self.failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path, native: bool = False) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    if native:
        # SIMLOX's default JSON can have trailing commas; normalize parser copy only.
        text = re.sub(r",\s*([}\]])", r"\1", text)
    return json.loads(text)


def get_tables(path: Path, top: str, native: bool = False) -> dict:
    return {t["name"]: t for t in read_json(path, native)[top]["tables"]}


def check_seals(a: Audit, directory: Path, closure: dict, label: str, count: int) -> None:
    a.check(f"{label}/raw-count", len(closure["raw"]) == count)
    for name, seal in closure["raw"].items():
        path = directory / name
        a.check(f"{label}/{name}/present", path.is_file())
        if path.is_file():
            a.check(f"{label}/{name}/size", path.stat().st_size == seal["bytes"])
            a.check(f"{label}/{name}/sha", sha(path) == seal["sha256"])


def unique_event(a: Audit, lines: list[str], label: str, text: str, hour: float) -> None:
    hits = [line for line in lines if text in line]
    a.check(f"event/{label}/count", len(hits) == 1)
    if len(hits) == 1:
        match = re.match(r"Time: (\d+(?:\.\d+)?)\b", hits[0])
        a.check(f"event/{label}/time", bool(match and math.isclose(float(match.group(1)), hour, abs_tol=1e-5)))


def replay() -> dict:
    a = Audit()
    a.check("pin/contract", sha(CASE / "contract.json") == EXPECTED_CONTRACT)
    a.check("pin/input", sha(CASE / "native-input.json") == EXPECTED_INPUT)
    a.check("pin/closure", sha(RUN / "closure.json") == EXPECTED_CLOSURE)
    closure = read_json(RUN / "closure.json")
    parent_closure = read_json(PARENT_RUN / "closure.json")
    b01_closure = read_json(B01_RUN / "closure.json")
    check_seals(a, RUN, closure, "child", 12)
    check_seals(a, PARENT_RUN, parent_closure, "B02", 11)
    check_seals(a, B01_RUN, b01_closure, "B01", 11)
    a.check("closure/run-id", closure["run_id"] == RUN_ID)
    a.check("closure/no-error", closure["error"] is None)
    before = closure["source_hashes_before"]
    a.check("source/before-after", before == closure["source_hashes_after"])
    a.check("source/path-set", set(before) == set(SOURCE_PATHS))
    for key, path in SOURCE_PATHS.items():
        a.check(f"source/{key}/exists", path.is_file())
        if path.is_file():
            a.check(f"source/{key}/sha", sha(path) == before[key])
    a.check("source/child-contract", before["child_contract"] == EXPECTED_CONTRACT)
    a.check("source/child-input", before["child_input"] == EXPECTED_INPUT)
    a.check("closure/invocation", sha(RUN / "invocation.json") == closure["invocation_sha256"])

    invocation = read_json(RUN / "invocation.json")
    steps = read_json(RUN / "steps.json")
    a.check("guard/ssh0", invocation["session_id"] == 0 and invocation["ssh_connection_present"])
    a.check("guard/sshd", "sshd.exe" in invocation["ssh_ancestor_names"])
    a.check("guard/mutex", invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue")
    gui = invocation["gui"]
    a.check("guard/gui", gui["pid"] == 13340 and gui["session_id"] == 1 and gui["start_unix_ms"] == 1790590196826)
    a.check("steps/order", [s["name"] for s in steps] == ["import", "export", "check_import_export", "calc", "jsonreport"])
    for s in steps:
        a.check(f"steps/{s['name']}", s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"])

    parent = get_tables(PARENT / "native-input.json", "model")
    child = get_tables(CASE / "native-input.json", "model")
    a.check("model/table-names", list(parent) == list(child))
    for name in parent:
        left, right = parent[name], child[name]
        if name == "TaskBreakDown":
            a.check("model/TBD/columns", left["columns"] == right["columns"])
            a.check("model/TBD/old-two", len(left["instances"][0]["rows"]) == 2)
            a.check("model/TBD/new-empty", right["instances"][0]["rows"] == [])
            a.check("model/TBD/instance", left["instances"][0]["instance_name"] == right["instances"][0]["instance_name"])
        else:
            a.check(f"model/{name}/identical", left == right)
    a.check("model/run-input-copy", (RUN / "input.json").read_bytes() == (CASE / "native-input.json").read_bytes())

    exported = get_tables(RUN / "roundtrip-raw.json", "model", native=True)
    a.check("roundtrip/table-set", set(exported) == set(child))
    populated = 0
    for name, authored in child.items():
        if any(inst["rows"] for inst in authored["instances"]):
            populated += 1
            native = exported[name]
            a.check(f"roundtrip/{name}/columns", [c["name"] for c in authored["columns"]] == [c["name"] for c in native["columns"]])
            a.check(f"roundtrip/{name}/rows", authored["instances"] == native["instances"])
    a.check("roundtrip/16-authored-populated", populated == 16)
    empty_rows = exported["TaskBreakDown"]["instances"][0]["rows"]
    a.check("roundtrip/TBD-only-null-placeholder", len(empty_rows) <= 1 and all(value is None for row in empty_rows for value in row))
    a.check("roundtrip/frozen-checker-passed", read_json(RUN / "roundtrip-validation.json")["passed"] is True)
    run_log = (RUN / "run.log").read_text(encoding="utf-8")
    a.check("converter/summary", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in run_log)
    a.check("converter/warnings", re.findall(r"warning #(\d+)", run_log) == ["108", "126"])
    a.check("converter/no-errors-notes", not re.search(r"(?:error|note) #\d+", run_log, re.I))
    a.check("converter/substantive-sxo", (RUN / "model.sxo").stat().st_size > 4)

    lines = (RUN / "model.log").read_text(encoding="utf-8").splitlines()
    expected_events = [
        ("mission-order", "<TEACH-UNIT> mission ordered: BASIC-MISSION", 7),
        ("allocate", "mission allocates system: <TEACH-AIR-01,0>", 7),
        ("prep-start", "<TEACH-AIR-01,0> preparation started, mission:", 7),
        ("main-start", "  system preparation task 0 on <TEACH-AIR-01,0> started", 7),
        ("synthetic-start", "subtask 0 seqno 0 within system preparation task 0 on <TEACH-AIR-01,0> started", 7),
        ("synthetic-duration", "subtask 0 seqno 0 within system preparation task 0 on <TEACH-AIR-01,0> starts performing, planned to last for 0.75 hours", 7),
        ("synthetic-end", "subtask 0 seqno 0 within system preparation task 0 on <TEACH-AIR-01,0> completed", 7.75),
        ("main-end", "  system preparation task 0 on <TEACH-AIR-01,0> completed", 7.75),
        ("prep-end", "<TEACH-AIR-01,0> preparation ended, mission:", 7.75),
        ("launch", "mission starting, duration: 2 : <TEACH-AIR-01,0>", 8),
        ("task-start", "task starting: <TEACH-AIR-01,0>", 8.5),
        ("task-end", "task completed: <TEACH-AIR-01,0>", 9.5),
        ("success", "mission success:", 10),
        ("mission-end", "mission completed: <TEACH-AIR-01,0>", 10),
        ("return", "System arrives <TEACH-AIR-01,0>, mission success", 10),
    ]
    for label, token, hour in expected_events:
        unique_event(a, lines, label, token, hour)
    positions = [next((i for i, line in enumerate(lines) if token in line), -1) for _, token, _ in expected_events]
    a.check("event/order", min(positions) >= 0 and positions == sorted(positions))
    a.check("event/no-authored-sequence", not any(re.search(r"subtask \d+ seqno [12] within system preparation", line) for line in lines))
    a.check("event/no-wait-cancel", not any("mission cancelled" in line or "waits for resources" in line for line in lines))
    b01_lines = (B01_RUN / "model.log").read_text(encoding="utf-8").splitlines()
    unique_event(a, b01_lines, "B01-synthetic-precedent", "subtask 0 seqno 0 within system preparation task 0 on <TEACH-AIR-01,0> starts performing, planned to last for 0.5 hours", 7)

    base_report = get_tables(PARENT_RUN / "report-raw.json", "report", native=True)
    child_report = get_tables(RUN / "report-raw.json", "report", native=True)
    a.check("report/table-set", set(base_report) == set(child_report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    changed = set()
    for name in sorted(base_report):
        lt, rt = base_report[name], child_report[name]
        cols = [c["name"] for c in lt["columns"]]
        a.check(f"report/{name}/columns", lt["columns"] == rt["columns"])
        left, right = lt["instances"][0]["rows"], rt["instances"][0]["rows"]
        a.check(f"report/{name}/row-count", len(left) == len(right) == (72 if name.endswith("Results") else 1))
        for row_i, (lrow, rrow) in enumerate(zip(left, right)):
            for col_i, (lv, rv) in enumerate(zip(lrow, rrow)):
                field = cols[col_i]
                if name == "SystemResults" and row_i == 15 and field in {"NSYMP", "NSYMR"}:
                    changed.add(field)
                    old, new = (0, 0.5) if field == "NSYMP" else (1, 0.5)
                    a.check(f"report/{row_i}/{field}/parent", math.isclose(lv, old, abs_tol=1e-6))
                    a.check(f"report/{row_i}/{field}/child", math.isclose(rv, new, abs_tol=1e-6))
                else:
                    a.check(f"report/{name}/{row_i}/{field}/equal", lv == rv)
    a.check("report/two-cell-contrast", changed == {"NSYMP", "NSYMR"})
    sys = child_report["SystemResults"]
    cols = [c["name"] for c in sys["columns"]]
    rows = sys["instances"][0]["rows"]
    a.check("report/72-half-hour-grid", all(math.isclose(r[cols.index("STINT")], i / 2) and math.isclose(r[cols.index("ETINT")], (i + 1) / 2) for i, r in enumerate(rows)))
    for field, expected in (("NSYRY", 33), ("NSYMP", 0.75), ("NSYMR", 0.25), ("NSYMO", 2)):
        value = sum((row[cols.index(field)] or 0) * (row[cols.index("ETINT")] - row[cols.index("STINT")]) for row in rows)
        a.check(f"report/integral/{field}", math.isclose(value, expected, abs_tol=1e-6))
    a.check("report/terminal-ready", rows[-1][cols.index("NSYRY")] == 1)
    return {
        "schema": "simlox-b02-var06-independent-replay/v1",
        "decision": "GO_BOUNDED" if not a.failures else "NO_GO",
        "checks": a.checks,
        "failures": a.failures,
        "run_id": RUN_ID,
        "contract_sha256": EXPECTED_CONTRACT,
        "input_sha256": EXPECTED_INPUT,
        "closure_sha256": EXPECTED_CLOSURE,
        "scope": "One deterministic linked preparation without authored breakdown; scalar DURN 0.75 produces one synthetic seqno-0 lifecycle.",
        "limits": ["Stale Tasks.DESCR refers to 10+20 minutes.", "Unused SubTaskType definitions are retained but do not represent work.", "No general scalar fallback, alternate seed, resources, repeated mission, GUI visual, or cross-engine inference."],
    }


if __name__ == "__main__":
    result = replay()
    target = CASE / "review" / "independent-verdict.json"
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"decision": result["decision"], "checks": result["checks"], "failures": result["failures"]}))
    raise SystemExit(0 if result["decision"] == "GO_BOUNDED" else 1)
