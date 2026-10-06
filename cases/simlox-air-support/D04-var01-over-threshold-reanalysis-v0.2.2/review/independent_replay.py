"""Independent read-only replay of sealed D04.var01 OPHOURS=2 evidence.

Uses only frozen sources and native raw files; does not import either author checker.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parent
V020 = ROOT / "D04-var01-over-threshold-v0.2.0"
V021 = ROOT / "D04-var01-over-threshold-reanalysis-v0.2.1"
PARENT = ROOT / "D04-flight-hour-pm-v1.0.0"
SIBLING = ROOT / "D04-var01-threshold-not-reached-v0.1.1"
D03 = ROOT / "D03-calendar-pm-v1.0.0"
RUN = V020 / "runs" / "d04-var01-op2-v020-ssh-20261006-01"
PARENT_RUN = PARENT / "runs" / "d04-flight-v100-ssh-20260930-01"
SIBLING_RUN = SIBLING / "runs" / "d04-var01-op4-v011-ssh-20261006-01"
OUTPUT = PACKAGE / "review" / "independent-verdict.json"
PYTHON = Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe")
MANUAL = Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf")
EXE = Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native(path: Path) -> dict:
    # The default native report has trailing commas. Normalize only parser memory.
    return json.loads(re.sub(r",\s*([}\]])", r"\1", path.read_text(encoding="utf-8-sig")))


def table_rows(doc: dict, root_key: str, name: str) -> list[dict]:
    matches = [t for t in doc[root_key]["tables"] if t["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"{name}: expected exactly one table, found {len(matches)}")
    t = matches[0]
    cols = [c["name"] for c in t["columns"]]
    if len(cols) != len(set(cols)):
        raise ValueError(f"{name}: duplicate column")
    values = [r for inst in t["instances"] for r in inst["rows"]]
    if any(len(r) != len(cols) for r in values):
        raise ValueError(f"{name}: nonrectangular row")
    return [dict(zip(cols, r)) for r in values]


def source_cells(doc: dict) -> dict:
    result = {}
    for t in doc["model"]["tables"]:
        cols = [c["name"] for c in t["columns"]]
        for ii, inst in enumerate(t["instances"]):
            for ri, row in enumerate(inst["rows"]):
                if len(row) != len(cols):
                    raise ValueError(f"nonrectangular authored {t['name']}")
                for col, value in zip(cols, row):
                    key = (t["name"], ii, ri, col)
                    if key in result:
                        raise ValueError(f"duplicate authored cell {key}")
                    result[key] = value
    return result


def timed_lines(log: str, fragment: str) -> list[float]:
    return [float(m.group(1)) for line in log.splitlines()
            if (m := re.match(r"^Time: ([\d.]+) (.*)$", line)) and fragment in m.group(2)]


def run() -> dict:
    count = 0
    failures = []

    def ck(label: str, actual, expected) -> None:
        nonlocal count
        count += 1
        if actual != expected:
            failures.append({"check": label, "actual": repr(actual)[:400], "expected": repr(expected)[:400]})

    def pinned(label: str, path: Path, expected: str) -> None:
        ck(label + " SHA", sha(path), expected)

    contract = load(PACKAGE / "contract.json")
    pinned("v022 contract", PACKAGE / "contract.json", "13677a298f2a45c1c3e2e01bb4d2451f1f9a78f3d2b789742ed2545ec3d24bbe")
    ck("v022 read-only version", contract["version"], "0.2.2-readonly-candidate")
    pinned("original contract", V020 / "contract.json", contract["sealed_run"]["contract_sha256"])
    pinned("original source", V020 / "native-input.json", contract["sealed_run"]["input_sha256"])
    pinned("original closure", RUN / "closure.json", contract["sealed_run"]["closure_sha256"])
    pinned("v020 frozen validator", V020 / "validate_native_cli.py", contract["preserved_failed_v020"]["validator_sha256"])
    pinned("v020 failed trace", V020 / "review" / "failed-author-serialization-2026-10-06.txt", contract["preserved_failed_v020"]["failure_log_sha256"])
    pinned("v021 contract", V021 / "contract.json", contract["preserved_failed_v021"]["contract_sha256"])
    pinned("v021 checker", V021 / "validate_readonly.py", contract["preserved_failed_v021"]["checker_sha256"])
    pinned("v021 failed verdict", V021 / "review" / "author-readonly-validation-2026-10-06.json", contract["preserved_failed_v021"]["author_verdict_sha256"])
    pinned("v020 prelaunch GO", V020 / "review" / "independent-prelaunch-go-2026-10-06.md", "6f57a99e174ac066fb4ced1049a4ac9aa179b04eb506c762a643e74ef2153df1")

    trace = (V020 / "review" / "failed-author-serialization-2026-10-06.txt").read_text()
    ck("original failure is tuple-key serialization", "TypeError: keys must be str, int, float, bool or None, not tuple" in trace, True)
    prior = load(V021 / "review" / "author-readonly-validation-2026-10-06.json")
    ck("v021 failed 7067/7068", (prior["passed"], prior["checks_count"], sum(x["passed"] for x in prior["checks"])), (False, 7068, 7067))
    ck("v021 sole failed check", [x["name"] for x in prior["checks"] if not x["passed"]], ["sibling closure SHA"])
    old = (V021 / "validate_readonly.py").read_bytes()
    new = (PACKAGE / "validate_readonly.py").read_bytes()
    short = b"98d30d678431fb8ce6661b2cac2b5a3681b226bca32a8076c7eac8899e18dea"
    ck("one old sibling literal", old.count(short), 1)
    ck("v022 checker one-literal correction", new, old.replace(short, short + b"0"))
    ck("v022 sibling closure literal", sha(SIBLING_RUN / "closure.json"), contract["accepted_sibling_closure_sha256"])
    author = load(PACKAGE / "review" / "author-readonly-validation-2026-10-06.json")
    ck("v022 author report is separately marked pass", (author["passed"], author["checks_count"]), (True, 7068))

    closure = load(RUN / "closure.json")
    invocation = load(RUN / "invocation.json")
    ck("child closure status/run", (closure["error"], closure["run_id"], closure["publication_state"]),
       (None, RUN.name, "not_published"))
    ck("child invocation seal", sha(RUN / "invocation.json"), closure["invocation_sha256"])
    ck("before/after source hashes", closure["source_hashes_before"], closure["source_hashes_after"])
    ck("invocation source seal", invocation["source_hashes_before"], closure["source_hashes_before"])
    source_paths = {
        "input": V020 / "native-input.json", "parent": PARENT / "native-input.json",
        "parent_signoff": PARENT / "cli-scope-signoff-2026-09-30.md", "parent_closure": PARENT_RUN / "closure.json",
        "sibling_input": SIBLING / "native-input.json", "sibling_signoff": SIBLING / "cli-scope-signoff-2026-10-06.md",
        "sibling_index": SIBLING / "evidence-index.json", "sibling_closure": SIBLING_RUN / "closure.json",
        "d03_input": D03 / "native-input.json", "d03_signoff": D03 / "cli-scope-signoff-2026-09-30.md",
        "contract_review": V020 / "review" / "independent-contract-go-2026-10-06.md",
        "negative_control": V020 / "review" / "negative-control-accepted-parent.json",
        "manual_pdf": MANUAL, "contract": V020 / "contract.json", "builder": V020 / "build.py",
        "checker": V020 / "check_roundtrip.py", "diff_checker": V020 / "check_parent_diff.py",
        "validator": V020 / "validate_native_cli.py", "python": PYTHON,
        "runner_script": V020 / "run_native_ssh.ps1", "simlox_exe": EXE,
    }
    ck("source seal key set", set(closure["source_hashes_before"]), set(source_paths))
    for name, path in source_paths.items():
        pinned("frozen " + name, path, closure["source_hashes_before"][name])
    ck("copied child input", sha(RUN / "input.json"), sha(V020 / "native-input.json"))
    ck("child source and original runner", (closure["source_hashes_before"]["input"], closure["source_hashes_before"]["runner_script"]),
       ("35866de7c9414c9dc39e75416c3464ec00b1d6c5d2f987749c428323dc57e092",
        "874fcca2487d103303d85b44b68e3e6310c8b21c63ed7861b109cfac555f11bc"))

    for role, folder, expected_sha in (
        ("child", RUN, contract["sealed_run"]["closure_sha256"]),
        ("parent", PARENT_RUN, "3cae72c375ef7a7c8dc63d785a33e97e9bd6103655fc28971abf5a0ccb24df45"),
        ("sibling", SIBLING_RUN, contract["accepted_sibling_closure_sha256"]),
    ):
        pinned(role + " closure", folder / "closure.json", expected_sha)
        item = load(folder / "closure.json")
        ck(role + " raw count", len(item["raw"]), 12)
        for filename, seal in item["raw"].items():
            path = folder / filename
            ck(role + " " + filename + " size", path.stat().st_size, seal["bytes"])
            pinned(role + " " + filename, path, seal["sha256"])

    old_cells = source_cells(native(PARENT / "native-input.json"))
    new_cells = source_cells(native(V020 / "native-input.json"))
    ck("221 authored cell keys", (len(old_cells), set(old_cells)), (221, set(new_cells)))
    ck("sole PMINT delta", {k: (old_cells[k], new_cells[k]) for k in old_cells if old_cells[k] != new_cells[k]},
       {("MaterielPM", 0, 0, "PMINT"): (3.0, 2.0)})
    ck("historical OP3 ID and label retained", (old_cells[("MaterielPM",0,0,"PMID")],
       old_cells[("MaterielPM",0,0,"DESCR")], new_cells[("MaterielPM",0,0,"PMID")],
       new_cells[("MaterielPM",0,0,"DESCR")]),
       ("OP3", "Three-operation-hour service", "OP3", "Three-operation-hour service"))

    ck("SSH0 and sshd", (invocation["session_id"], invocation["ssh_connection_present"],
       "sshd.exe" in invocation["ssh_ancestor_names"]), (0, True, True))
    gui = invocation["gui"]
    ck("protected GUI identity", (gui["pid"], gui["session_id"], gui["start_utc"]),
       (13340, 1, "2026-09-28T10:09:56.8261381Z"))
    ck("global mutex", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
    steps = load(RUN / "steps.json")
    ck("ordered five steps", [x["name"] for x in steps],
       ["import", "export", "check_import_export", "calc", "jsonreport"])
    for step in steps:
        ck("step complete/GUI " + step["name"],
           (step["status"], step["exit_code"], step["gui_preserved"]), ("completed", 0, True))
    roundtrip = load(RUN / "roundtrip-validation.json")
    ck("roundtrip 18 tables", (roundtrip["passed"], len(roundtrip["authored_row_containing_tables"])), (True, 18))
    converter = (RUN / "run.log").read_text(encoding="utf-8-sig")
    ck("converter 0/2/0", "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in converter, True)
    ck("converter warning IDs", sorted(re.findall(r"\(warning #(\d+)\)", converter)), ["108", "126"])
    ck("converter has no error", re.findall(r"\(error #(\d+)\)", converter), [])

    child_log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    parent_log = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig")
    sibling_log = (SIBLING_RUN / "model.log").read_text(encoding="utf-8-sig")
    def prefix(log: str) -> list[str]:
        return [line for line in log.splitlines() if (m := re.match(r"^Time: ([\d.]+) ", line)) and float(m.group(1)) < 10]
    ck("all events before h10 match D04", prefix(child_log), prefix(parent_log))
    ck("mission physical starts", timed_lines(child_log, "mission starting, duration:"), [8.0, 40.0])
    ck("mission success", timed_lines(child_log, "mission success:"), [10.0, 41.0])
    ck("mission completion on aircraft ID0", timed_lines(child_log, "mission completed: <TEACH-AIR-01,0>"), [10.0, 41.0])
    ck("mission identity lines", re.findall(r"mission starting, duration: ([12]) : <TEACH-AIR-01,0>", child_log), ["2", "1"])
    ck("no canceled/failed mission", bool(re.search(r"mission (?:cancelled|aborted|failed)", child_log)), False)
    task_start = re.findall(r"^Time: ([\d.]+)  system PM task (\d+) on <TEACH-AIR-01,0> started$", child_log, re.M)
    task_end = re.findall(r"^Time: ([\d.]+)  system PM task (\d+) on <TEACH-AIR-01,0> completed$", child_log, re.M)
    sub_start = re.findall(r"^Time: ([\d.]+)  subtask (\d+) seqno (\d+) within system PM task (\d+) on <TEACH-AIR-01,0> started$", child_log, re.M)
    sub_end = re.findall(r"^Time: ([\d.]+)  subtask (\d+) seqno (\d+) within system PM task (\d+) on <TEACH-AIR-01,0> completed$", child_log, re.M)
    ck("sole system PM h10–11", (task_start, task_end), ([("10", "0")], [("11", "0")]))
    ck("sole subtask h10–11", (sub_start, sub_end),
       ([("10", "0", "1", "0")], [("11", "0", "1", "0")]))
    ck("PM ID OP3 historical label", "Time: 10  system PM task 0 on <TEACH-AIR-01,0> PMID: OP3" in child_log, True)
    ck("second return has no PM", "Time: 41 <TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,0>, mission success, \n no failures \n no PMTasks" in child_log, True)
    ck("sibling has no PM task", "system PM task 0 on <TEACH-AIR-01,0> started" in sibling_log, False)
    ck("no item demand/fault", bool(re.search(r"item demand|failed item|system failure", child_log, re.I)), False)

    report = native(RUN / "report-raw.json")
    p_report = native(PARENT_RUN / "report-raw.json")
    system, p_system = table_rows(report, "report", "SystemResults"), table_rows(p_report, "report", "SystemResults")
    stock, p_stock = table_rows(report, "report", "StockTotalResults"), table_rows(p_report, "report", "StockTotalResults")
    summary, p_summary = table_rows(report, "report", "ResultSummary"), table_rows(p_report, "report", "ResultSummary")
    ck("report shapes", (len(system), len(p_system), len(stock), len(p_stock), len(summary), len(p_summary)),
       (120, 120, 120, 120, 1, 1))
    ck("report widths", (len(system[0]), len(stock[0]), len(summary[0])), (40, 16, 11))
    # Event-derived PM shift: h10–11 receives the parent's h41–42 PM state;
    # h41–42 receives its pre-PM ready state. All other fields and bins stay fixed.
    changed = {
        20: {"NSYRY":0,"NSYUA":1,"NSYA":0,"NSYPM":1,"NPMS":1,"SYDT":1,"NSYDT":1},
        21: {"NSYRY":0,"NSYUA":1,"NSYA":0,"NSYPM":1},
        22: {"NPMT":1},
        82: {"NSYRY":1,"NSYUA":0,"NSYA":1,"NSYPM":0,"NPMS":0,"SYDT":None,"NSYDT":0},
        83: {"NSYRY":1,"NSYUA":0,"NSYA":1,"NSYPM":0},
        84: {"NPMT":0},
    }
    actual_changed = {}
    for i, (row, baseline) in enumerate(zip(system, p_system)):
        ck(f"System row {i} field set", set(row), set(baseline))
        ck(f"System row {i} time grid", (row["STINT"], row["ETINT"]), (i * .5, (i + 1) * .5))
        for field, old_value in baseline.items():
            expected = changed.get(i, {}).get(field, old_value)
            ck(f"System row {i} {field}", row[field], expected)
            if row[field] != old_value:
                actual_changed[(i, field)] = (old_value, row[field])
    ck("exact 24 System changes", len(actual_changed), 24)
    ck("changed System row set", {i for i, _ in actual_changed}, set(changed))
    for i, (row, baseline) in enumerate(zip(stock, p_stock)):
        ck(f"Stock row {i} field set", set(row), set(baseline))
        ck(f"Stock row {i} time grid", (row["STINT"], row["ETINT"]), (i * .5, (i + 1) * .5))
        for field, expected in baseline.items():
            ck(f"Stock row {i} {field}", row[field], expected)
    ck("summary field set", set(summary[0]), set(p_summary[0]))
    for field, expected in p_summary[0].items():
        ck("summary " + field, summary[0][field], expected)
    for field, expected in (("NSYRY",54.0),("NSYA",59.0),("NSYMO",3.0),("NSYPM",1.0)):
        ck("integral " + field, sum(r[field] * .5 for r in system), expected)
    ck("one PM marker each", (sum(r["NPMS"] for r in system), sum(r["NPMT"] for r in system)), (1,1))
    ck("PM start/completion bins", (system[20]["NPMS"],system[22]["NPMT"],system[82]["NPMS"],system[84]["NPMT"]), (1,1,0,0))
    ck("terminal ready and no PM", (system[-1]["NSYRY"],system[-1]["NSYPM"],system[-1]["NSYMO"]), (1,0,0))
    ck("no stock backorder/failure", all(r["NBO"] == r["NDF"] == r["NDD"] == 0 for r in stock), True)

    return {
        "schema": "simlox-d04-var01-v022-independent-replay/v1",
        "verdict": "GO_BOUNDED" if not failures else "NO_GO",
        "checks_count": count,
        "checks_passed": count - len(failures),
        "failures": failures,
        "run_id": RUN.name,
        "child_closure_sha256": sha(RUN / "closure.json"),
        "v021_failed_verdict_sha256": sha(V021 / "review" / "author-readonly-validation-2026-10-06.json"),
        "v022_corrected_checker_sha256": sha(PACKAGE / "validate_readonly.py"),
        "source_delta": "one MaterielPM.PMINT cell, OPHOURS 3 to 2",
        "report_system_changed_cells": len(actual_changed),
        "limits": ["one sealed seed-1 aircraft and schedule", "original v020/v021 author failures remain excluded",
                   "no direct PM counter trace", "no second full post-repair PM cycle", "no GUI visual or cross-engine claim"],
    }


def main() -> int:
    try:
        result = run()
    except Exception as exc:
        result = {"schema":"simlox-d04-var01-v022-independent-replay/v1", "verdict":"NO_GO",
                  "checks_count":0, "checks_passed":0,
                  "failures":[{"check":"replay exception", "actual":f"{type(exc).__name__}: {exc}", "expected":"none"}]}
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k:result.get(k) for k in ("verdict","checks_count","checks_passed","failures")}, ensure_ascii=False))
    return 0 if result["verdict"] == "GO_BOUNDED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
