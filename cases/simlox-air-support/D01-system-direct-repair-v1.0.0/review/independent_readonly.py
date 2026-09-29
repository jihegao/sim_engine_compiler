"""Independent read-only replay of D01 native evidence and A02 control.

No author builder, checker, validator or native executable is imported or run.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path, PureWindowsPath
import re
import sys


CASE = Path(__file__).resolve().parents[1]
RUN = CASE / "runs" / "d01-v100-ssh-20260929-01"
PARENT = CASE.parent / "A02-single-aircraft-repeated-missions" / "native-input.json"
CONTROL = Path(r"C:\Users\user\Documents\Codex\2026-09-27\simlox-case-library-a01-a02-v1\repo\data\local\simlox-case-library\v1\A02\a02-bound-final-20260927-03\report-raw.json")
PARENT_SHA = "84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8"
CHILD_SHA = "d418c811f2e1a9ad047af19038a3d0881d404adf0919d2e52dab70e6100ee450"
CONTROL_REPORT_SHA = "a7227687988841c074b28b524792af7d856cd674840169bf15c210f2d2cd4739"
AIRCRAFT = "<TEACH-AIR-01,0>"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def document(path: Path, native: bool = False):
    raw = path.read_text(encoding="utf-8-sig")
    if not native:
        return json.loads(raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        out = []
        quoted = escaped = False
        for i, char in enumerate(raw):
            if quoted:
                out.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
                out.append(char)
            elif char == "," and raw[i + 1 :].lstrip().startswith(("]", "}")):
                continue
            else:
                out.append(char)
        return json.loads("".join(out))


def table_map(doc: dict, root: str) -> dict[str, dict]:
    found = {}
    for table in doc[root]["tables"]:
        name = table["name"]
        if name in found:
            raise ValueError(f"duplicate table: {name}")
        found[name] = table
    return found


def rows(table: dict) -> list[dict]:
    names = [column["name"] for column in table["columns"]]
    result = []
    for instance in table["instances"]:
        for values in instance["rows"]:
            if len(values) != len(names):
                raise ValueError(f"nonrectangular table: {names}")
            result.append(dict(zip(names, values)))
    return result


def number_normalized(value):
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, dict):
        return {key: number_normalized(item) for key, item in value.items()}
    return value


def business(table: dict) -> Counter:
    return Counter(
        json.dumps(number_normalized(record), sort_keys=True, ensure_ascii=False)
        for record in rows(table)
        if any(value not in (None, "") for value in record.values())
    )


def utc(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.utcoffset() == timezone.utc.utcoffset(parsed) else None


def verify() -> dict:
    errors = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    invocation = document(RUN / "invocation.json")
    closure = document(RUN / "closure.json")
    steps = document(RUN / "steps.json")
    contract = document(CASE / "contract.json")
    delta = document(CASE / "parent-diff.json")
    check(sha(PARENT) == PARENT_SHA and sha(CASE / "native-input.json") == sha(RUN / "input.json") == CHILD_SHA, "source/parent fingerprints differ")
    check(contract.get("parent", {}).get("input_sha256") == PARENT_SHA and contract.get("native_input_sha256") == CHILD_SHA, "contract source fingerprints differ")
    check(delta.get("schema") == "simlox-parent-table-diff/v1" and delta.get("parent_case") == "A02" and delta.get("case_id") == "D01", "parent-diff case identity differs")
    signoff = CASE.parent / "A02-single-aircraft-repeated-missions" / "cli-scope-signoff-2026-09-29.md"
    signoff_text = signoff.read_text(encoding="utf-8")
    check(PARENT_SHA in signoff_text and CONTROL_REPORT_SHA in signoff_text and "reusable_published" in signoff_text, "accepted A02 signoff or control binding differs")
    check(invocation.get("schema") == "simlox-d01-v100-native-candidate/ssh-cli-v1" and closure.get("schema") == "simlox-d01-v100-native-closure/v1", "run schema differs")
    check(invocation.get("case_id") == "D01" and invocation.get("case_version") == "1.0.0-candidate" and invocation.get("run_id") == RUN.name == closure.get("run_id"), "case/run identity differs")
    check(invocation.get("input_sha256") == CHILD_SHA and invocation.get("parent_sha256") == PARENT_SHA, "invocation source fingerprints differ")
    check(invocation.get("execution_mode") == "ssh_cli_v1" and invocation.get("session_id") == 0 and invocation.get("ssh_connection_present") is True, "session-0 SSH provenance differs")
    check("sshd.exe" in [str(name).lower() for name in invocation.get("ssh_ancestor_names", [])], "sshd ancestor absent")
    check(invocation.get("queue_mutex") == r"Global\SimloxIssue18NativeQueue", "host-wide queue identity differs")
    gui = invocation.get("gui", {})
    check(gui.get("pid") == 13340 and type(gui.get("session_id")) is int and gui["session_id"] > 0 and utc(gui.get("start_utc")) is not None, "GUI process identity differs")
    check(closure.get("error") is None and invocation.get("publication_state") == closure.get("publication_state") == "not_published", "run error/publication scope differs")
    check(closure.get("invocation_sha256") == sha(RUN / "invocation.json"), "invocation seal differs")
    paths = {
        "input": CASE / "native-input.json",
        "parent": PARENT,
        "contract": CASE / "contract.json",
        "builder": CASE / "build.py",
        "checker": CASE / "check_roundtrip.py",
        "python": Path(invocation["planned_check"]["executable"]),
        "runner_script": CASE / "run_native_ssh.ps1",
        "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    }
    before = invocation.get("source_hashes_before", {})
    check(before == closure.get("source_hashes_before") == closure.get("source_hashes_after"), "before/after source hash records differ")
    for key, path in paths.items():
        check(path.is_file() and sha(path) == before.get(key), f"current source hash differs: {key}")
    check(invocation.get("contract_sha256") == before.get("contract") and invocation.get("runner_script_sha256") == before.get("runner_script") and invocation.get("simlox_exe_sha256") == before.get("simlox_exe"), "invocation component hashes differ")
    raw = closure.get("raw", {})
    actual_files = {p.name for p in RUN.iterdir() if p.is_file()} - {"invocation.json", "closure.json"}
    check(set(raw) == actual_files, "closure raw artifact set differs")
    for name, seal in raw.items():
        path = RUN / name
        check(path.is_file() and path.stat().st_size == seal.get("bytes") and sha(path) == seal.get("sha256"), f"raw artifact seal differs: {name}")
    original = PureWindowsPath(invocation.get("original_run_dir", ""))
    check(original.is_absolute() and original.name == RUN.name, "original Windows run path differs")
    expected_args = {
        "import": f'-silent -jimport "{original / "input.json"}" -save "{original / "model.sxi"}" -log "{original / "import.log"}" -close',
        "export": f'"{original / "model.sxi"}" -silent -jexport "{original / "roundtrip-raw.json"}" -log "{original / "export.log"}" -close',
        "calc": f'"{original / "model.sxi"}" -silent -threads 1 -calc -log "{original / "run.log"}" -close',
        "jsonreport": f'"{original / "model.sxo"}" -silent -jsonreport "{original / "report-raw.json"}" -log "{original / "report-export.log"}" -close',
    }
    check([(x.get("name"), x.get("arguments")) for x in invocation.get("planned_commands", [])] == list(expected_args.items()), "planned command arguments differ")
    check([step.get("name") for step in steps] == [*expected_args, "check_import_export"], "executed step order differs")
    previous = utc(invocation.get("created_utc"))
    for step in steps:
        name = step.get("name")
        start, end = utc(step.get("started_utc")), utc(step.get("completed_utc"))
        check(start is not None and end is not None and start <= end and (previous is None or previous <= start), f"step timestamp order differs: {name}")
        previous = end
        check(step.get("status") == "completed" and step.get("exit_code") == 0 and step.get("gui_preserved") is True and step.get("error") is None, f"step failed or GUI not preserved: {name}")
        if name in expected_args:
            check(step.get("arguments") == expected_args[name], f"executed arguments differ: {name}")

    parent = table_map(document(PARENT), "model")
    source = table_map(document(RUN / "input.json"), "model")
    changed = sorted(name for name in parent.keys() | source.keys() if parent.get(name) != source.get(name))
    check(changed == ["ProblemDescription", "System", "SystemRepair"] == sorted(delta.get("changed_tables", {})), "A02-to-D01 table delta differs")
    for name, record in delta["changed_tables"].items():
        check(rows(parent[name]) == record["before_rows"] and rows(source[name]) == record["after_rows"], f"parent-diff row witness differs: {name}")
    check(all(parent[name]["columns"] == source[name]["columns"] for name in parent), "inherited schema changed")
    system = rows(source["System"])
    repair = rows(source["SystemRepair"])
    check(len(system) == 1 and system[0]["SID"] == "TEACH-AIR-01" and system[0]["OPID"] == "OPHOURS" and system[0]["FRT"] == 300000, "system failure rate/OPID differs")
    check(len(repair) == 1 and all(repair[0].get(k) == v for k, v in {"SID": "TEACH-AIR-01", "STID": "BASE-01", "DIRPT": .5, "SURPT": 0, "DIRPF": 1, "SURPF": 1}.items()), "system direct repair configuration differs")
    check(len(rows(source["Item"])) == len(rows(source["ItemStructure"])) == 0, "direct-repair-only scope has items")
    check({record["STID"]: record["TYPE"] for record in rows(source["Station"])}.get("BASE-01") == "WS", "repair station is not WS")
    profile = rows(source["OperationProfile"])
    check(sorted(record["STIM"] for record in profile) == [8, 20, 32], "three fixed mission opportunities differ")
    control_row = rows(source["Control"])[0]
    check(control_row["NREPS"] == 1 and control_row["SIMPE"] == 36 and control_row["RSEED"] == "1" and control_row["RCINT"] == .5, "run control differs")
    exported = table_map(document(RUN / "roundtrip-raw.json", native=True), "model")
    changed_business = [name for name in source.keys() | exported.keys() if business(source.get(name, {"columns": [], "instances": []})) != business(exported.get(name, {"columns": [], "instances": []}))]
    check(not changed_business, f"import/export business rows differ: {sorted(changed_business)}")
    check(sum(bool(rows(t)) for t in source.values()) == 14, "row-containing source table count differs")
    check("Import completed!" in (RUN / "import.log").read_text(encoding="utf-8-sig", errors="replace") and "Export completed!" in (RUN / "export.log").read_text(encoding="utf-8-sig", errors="replace"), "import/export completion markers absent")
    check("Generating Json-report" in (RUN / "report-export.log").read_text(encoding="utf-8-sig", errors="replace"), "report export marker absent")
    run_log = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    warnings = re.findall(r"warning #(\d+)", run_log)
    check("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in run_log and Counter(warnings) == Counter(("108", "126")), "conversion counts/warnings differ")
    check("Starting simulation..." in run_log and "Saving results ..." in run_log, "simulation completion markers absent")

    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    timed = []
    for line in log.splitlines():
        match = re.match(r"^Time:\s*([0-9.eE+-]+)\s+(.*)$", line)
        if match:
            timed.append((float(match.group(1)), match.group(2)))
    def event(time: float, text: str) -> int:
        return sum(abs(t - time) < 1e-8 and text in body for t, body in timed)
    failures = [(t, body) for t, body in timed if "critical random failure added" in body]
    failure_times = [time for time, _ in failures]
    check(len(failures) == 2 and all(math.isclose(x, y, abs_tol=1e-4) for x, y in zip(failure_times, (9.8829, 33.8602))), f"critical failure times/count differ: {failure_times}")
    check(all(AIRCRAFT in body for _, body in failures), "critical failure aircraft identity differs")
    for index, notice, launch, end, outcome in ((0, 7, 8, 10, "abort"), (1, 19, 20, 22, "success"), (2, 31, 32, 34, "abort")):
        tag = f"<BASIC-MISSION,TEACH-UNIT,0,0,{index}>"
        check(event(notice, "<TEACH-UNIT> mission ordered: BASIC-MISSION") == 1, f"mission order differs: {index}")
        check(event(notice, f"{tag} mission created:") == 1 and event(notice, f"{tag} mission allocates system: {AIRCRAFT}") == 1, f"mission creation/assignment differs: {index}")
        check(event(launch, f"{tag} mission starting, duration: 2 : {AIRCRAFT}") == 1, f"mission launch differs: {index}")
        if outcome == "abort":
            when = failure_times[0 if index == 0 else 1]
            check(event(when, f"{tag} mission aborted:") == 1 and event(end, f"{tag} aborted mission completed:") == 1, f"mission abort/return differs: {index}")
            check(event(end, f"<TEACH-AIR-01,BASE-01,0> System arrives {AIRCRAFT},") == 1, f"failed aircraft return differs: {index}")
        else:
            check(event(end, f"{tag} mission success:") == 1 and event(end, f"{tag} mission completed: {AIRCRAFT}") == 1, "middle mission success differs")
            check(event(end, f"<TEACH-AIR-01,BASE-01,0> System arrives {AIRCRAFT}, mission success,") == 1, "middle mission return differs")
    check(sum(" mission aborted:" in body for _, body in timed) == 2 and sum(" mission success:" in body for _, body in timed) == 1, "mission outcome counts differ")
    for task, start in ((0, 10), (1, 34)):
        label = f"system DIRP task {task} on {AIRCRAFT}"
        subtask = f"direct repair subtask {task} seqno 0 within {label}"
        task_starts = sum(abs(t - start) < 1e-8 and body.strip() == f"{label} started" for t, body in timed)
        task_ends = sum(abs(t - start - .5) < 1e-8 and body.strip() == f"{label} completed" for t, body in timed)
        check(task_starts == task_ends == 1, f"direct repair task TAT differs: {task}")
        check(event(start, f"{subtask} starts performing, planned to last for 0.5 hours") == 1 and event(start + .5, f"{subtask} completed") == 1, f"direct repair subtask differs: {task}")
        check(event(start, f"<TEACH-AIR-01,BASE-01,0> System to repair {AIRCRAFT}") == 1, f"local direct repair location differs: {task}")
        check(event(start + .5, f"<TEACH-AIR-01,BASE-01,0> Maintained system arrives {AIRCRAFT}") == 1 and event(start + .5, f"<TEACH-UNIT at <BASE-01,0>> systems ready: 1 :{AIRCRAFT}") == 1, f"repair recovery differs: {task}")
    started_tasks = [body.strip() for _, body in timed if re.fullmatch(r"system DIRP task \d+ on <TEACH-AIR-01,0> started", body.strip())]
    completed_tasks = [body.strip() for _, body in timed if re.fullmatch(r"system DIRP task \d+ on <TEACH-AIR-01,0> completed", body.strip())]
    check(started_tasks == [f"system DIRP task {task} on {AIRCRAFT} started" for task in (0, 1)] and completed_tasks == [f"system DIRP task {task} on {AIRCRAFT} completed" for task in (0, 1)], "extra/missing direct repair task events")

    report = table_map(document(RUN / "report-raw.json", native=True), "report")
    control = table_map(document(CONTROL, native=True), "report")
    check(sha(CONTROL) == CONTROL_REPORT_SHA, "published A02 control report hash differs")
    summary, base_summary = rows(report["ResultSummary"]), rows(control["ResultSummary"])
    check(len(summary) == len(base_summary) == 1, "ResultSummary row count differs")
    check(all(summary[0].get(k) == v for k, v in {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MSTF": 1, "MTMF": 1, "STMF": 1}.items()), "ResultSummary fixed metrics differ")
    check(math.isclose(summary[0].get("MSUF", -1), 1 / 3, abs_tol=1e-7) and base_summary[0].get("MSUF") == 1, "success fraction differs from one of three versus A02 three of three")
    check(all(summary[0][key] == base_summary[0][key] for key in summary[0] if key != "MSUF"), "other ResultSummary metrics differ from A02")
    ledger, base_ledger = rows(report["SystemResults"]), rows(control["SystemResults"])
    check(len(ledger) == len(base_ledger) == 72 and len(rows(report["StockTotalResults"])) == 72, "half-hour interval count differs")
    check(sum(row.get("NFAIL") or 0 for row in base_ledger) == 0 and sum(row.get("NREPT") or 0 for row in base_ledger) == 0, "A02 control is not no-fault/no-repair")
    expected_changes = {
        9.5: {"NFAIL": (0, 1)},
        10.0: {"NSYRY": (1, 0), "NSYUA": (0, 1), "NSYA": (1, 0), "NSYRP": (0, 1), "SYDT": (None, .5), "NSYDT": (0, 1)},
        10.5: {"NREPT": (0, 1)},
        33.5: {"NFAIL": (0, 1)},
        34.0: {"NSYRY": (1, 0), "NSYUA": (0, 1), "NSYA": (1, 0), "NSYRP": (0, 1), "SYDT": (None, .5), "NSYDT": (0, 1)},
        34.5: {"NREPT": (0, 1)},
    }
    observed_changes = {}
    for i, (base, actual) in enumerate(zip(base_ledger, ledger)):
        start, end = i / 2, (i + 1) / 2
        check(actual.get("STINT") == base.get("STINT") == start and actual.get("ETINT") == base.get("ETINT") == end, f"SystemResults grid differs at {i}")
        check(actual.get("UNID") == "Total over all Units" and actual.get("SID") == "Total over all Systems", f"SystemResults total identity differs at {i}")
        difference = {key: (base.get(key), actual.get(key)) for key in base.keys() | actual.keys() if base.get(key) != actual.get(key)}
        if difference:
            observed_changes[start] = difference
        check(actual.get("NPSTA") == 0 and actual.get("NPMT") == 0, f"unexpected preparation/PM at {i}")
    check(observed_changes == expected_changes, f"D01 SystemResults differ from A02 outside two failure/repair windows: {observed_changes}")
    check(sum(row.get("NFAIL") or 0 for row in ledger) == 2 and sum(row.get("NREPT") or 0 for row in ledger) == 2, "failure/repair counts differ")
    check(sum((row.get("NSYRP") or 0) * .5 for row in ledger) == 1 and sum((row.get("NSYMO") or 0) * .5 for row in ledger) == 6, "repair/mission interval hours differ")
    check(ledger[-1]["NSYRY"] == ledger[-1]["NSYA"] == 1 and ledger[-1]["NSYRP"] == ledger[-1]["NSYUA"] == 0, "terminal system not ready")
    check(rows(report["ProblemDescription"]) == rows(source["ProblemDescription"]), "report description differs")

    return {
        "schema": "simlox-d01-v100-independent-readonly/v1",
        "review_date": "2026-09-29",
        "run_id": RUN.name,
        "passed": not errors,
        "differences": errors,
        "evidence": {
            "parent_input_sha256": sha(PARENT),
            "child_input_sha256": sha(RUN / "input.json"),
            "invocation_sha256": sha(RUN / "invocation.json"),
            "closure_sha256": sha(RUN / "closure.json"),
            "report_sha256": sha(RUN / "report-raw.json"),
            "model_log_sha256": sha(RUN / "model.log"),
            "a02_control_report_sha256": sha(CONTROL),
            "changed_tables": changed,
            "warning_codes": warnings,
            "critical_failure_hours": failure_times,
            "mission_outcomes": ["aborted", "successful", "aborted"],
            "direct_repair_windows": [[10, 10.5], [34, 34.5]],
            "result_intervals": len(ledger),
            "system_result_change_hours_vs_a02": sorted(observed_changes),
            "terminal_ready": ledger[-1]["NSYRY"],
        },
        "scope": "independent_cli_behavior_review",
        "publication_state": "not_published",
        "limitations": [
            "Failure times are run-specific observations under seed 1 and this executable, not portable scheduled inputs.",
            "The 0.5-hour DIRPT is a local direct-repair turnaround; no item replacement, stock, explicit task resource, PM, failure-mode, GUI-only or cross-engine behavior is accepted.",
            "SystemResults uses half-hour bins: it records a failure in each final mission interval and six nominal mission-operation hours, while exact 9.8829/33.8602 abort times come from the event log.",
            "GUI preservation, active-session gating and queue ownership rely on the source-bound runner and sealed step records; GUI window content was not independently sampled.",
        ],
    }


def main() -> int:
    try:
        result = verify()
    except Exception as exc:
        result = {"schema": "simlox-d01-v100-independent-readonly/v1", "run_id": RUN.name, "passed": False, "differences": [f"review exception: {type(exc).__name__}: {exc}"], "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
