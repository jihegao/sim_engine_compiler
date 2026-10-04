"""Standard-library, read-only replay of sealed J09.var05 matched native runs."""
from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE = HERE.parent
CASES = CASE.parent
PARENT = CASES / "D03-calendar-pm-v1.0.0"
PARENT_RUN = PARENT / "runs" / "d03-calendar-v100-ssh-20261001-02"
PRECEDENT = CASES / "J09-var04-pm-interval-scale-v1.0.0"
EXCLUDED = CASES / "J09-var05-pm-tat-scale-v1.0.0"
EXCLUDED_RUN = EXCLUDED / "runs" / "j09-var05-scpmt2-v100-ssh-20261004-01"
RUNS = {
    "control": CASE / "runs" / "j09-var05-pmt-control-v101-ssh-20261004-01",
    "scaled": CASE / "runs" / "j09-var05-pmt-scaled-v101-ssh-20261004-01",
}
OUTPUT = HERE / "independent-verdict.json"
checks = 0
failures: list[str] = []


def check(condition: bool, label: str) -> None:
    global checks
    checks += 1
    if not condition:
        failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    text = path.read_text(encoding="utf-8-sig")
    return json.loads(re.sub(r",\s*([}\]])", r"\1", text))


def tables(document: dict, root: str) -> dict:
    return {table["name"]: table for table in document[root]["tables"]}


def rows(table: dict) -> list:
    return [row for instance in table["instances"] for row in instance["rows"]]


def columns(table: dict) -> list[str]:
    return [column["name"] for column in table["columns"]]


def close(actual, expected, tolerance=2e-5) -> bool:
    return isinstance(actual, (int, float)) and math.isclose(actual, expected, rel_tol=0, abs_tol=tolerance)


contract = load(CASE / "contract.json")
diff = load(CASE / "exact-diff.json")
source = {
    "parent": PARENT / "native-input.json",
    "parent_closure": PARENT_RUN / "closure.json",
    "parent_signoff": PARENT / "cli-scope-signoff-2026-09-30.md",
    "precedent_input": PRECEDENT / "scaled-input.json",
    "precedent_closure": PRECEDENT / "runs" / "j09-var04-scpmi2-v100-ssh-20261004-01" / "closure.json",
    "precedent_evidence_index": PRECEDENT / "evidence-index.json",
    "excluded_closure": EXCLUDED_RUN / "closure.json",
    "contract": CASE / "contract.json",
    "exact_diff": CASE / "exact-diff.json",
    "build.py": CASE / "build.py",
    "describe_diff.py": CASE / "describe_diff.py",
}
check(contract["case_id"] == "J09" and contract["variant_id"] == "J09.var05", "contract case identity")
check(contract["parameters"]["expected_report_bins"] == 120, "120-bin contract")
check(sha(source["parent"]) == contract["accepted_parent"]["input_sha256"], "D03 input pin")
check(sha(source["parent_closure"]) == contract["accepted_parent"]["closure_sha256"], "D03 closure pin")
check(sha(source["parent_signoff"]) == contract["accepted_parent"]["signoff_sha256"], "D03 signoff pin")
check(sha(source["excluded_closure"]) == contract["excluded_diagnostic"]["closure_sha256"], "excluded diagnostic closure pin")
check(sha(EXCLUDED / "scaled-input.json") == contract["excluded_diagnostic"]["input_sha256"], "excluded diagnostic source pin")
check(sha(EXCLUDED_RUN / "model.log") == sha(PARENT_RUN / "model.log"), "excluded event log identical to D03")
check(sha(EXCLUDED_RUN / "report-raw.json") == sha(PARENT_RUN / "report-raw.json"), "excluded report identical to D03")
check(sha(source["contract"]) == "6c08527dff828acc27a1f35ed2f3739c3cc5aaadf738d14bdac0c33af4260bc0", "frozen contract SHA")
check(sha(source["exact_diff"]) == contract["exact_diff_sha256"], "frozen exact diff SHA")
check(sha(CASE / "control-input.json") == contract["control_input_sha256"], "control source SHA")
check(sha(CASE / "scaled-input.json") == contract["scaled_input_sha256"], "scaled source SHA")
check(sha(source["precedent_input"]) == "e58a615dca7dca19608cee4546940d3823188559d49c37604ffbe6d064777486", "scale schema precedent source")
check(sha(source["precedent_closure"]) == "e13eccaca8f8f145d0138005556f82eb313ce5503881494c83a146749dabaf8d", "scale precedent closure")
check(sha(source["precedent_evidence_index"]) == "888ba0e9e96be769d85d8cf26adb165162aa502eb6c41382db03f959c3741329", "scale precedent index")

parent = tables(load(source["parent"]), "model")
control = tables(load(CASE / "control-input.json"), "model")
scaled = tables(load(CASE / "scaled-input.json"), "model")
check(len(parent) == 31 and len(control) == len(scaled) == 32, "31 parent / 32 paired source tables")
check(set(control) == set(scaled) == set(parent) | {"ScaleFactors"}, "appended ScaleFactors only")
for name in sorted(parent):
    if name != "PMLocation":
        check(parent[name] == control[name] == scaled[name], f"unchanged parent table {name}")
pm_parent = rows(parent["PMLocation"])
pm_control = rows(control["PMLocation"])
pm_scaled = rows(scaled["PMLocation"])
pm_cols = columns(parent["PMLocation"])
check(columns(control["PMLocation"]) == pm_cols == columns(scaled["PMLocation"]), "PMLocation schema unchanged")
check(len(pm_parent) == len(pm_control) == len(pm_scaled) == 1, "single PMLocation row")
tid = pm_cols.index("TID")
pmt = pm_cols.index("PMT")
check(pm_parent[0][tid] == "PM-CAL24" and pm_control[0][tid] is None and pm_scaled[0][tid] is None, "only PM task reference cleared")
check(pm_control[0][pmt] == pm_scaled[0][pmt] == 1, "one-hour authored PMT")
for j, column in enumerate(pm_cols):
    if column != "TID":
        check(pm_parent[0][j] == pm_control[0][j] == pm_scaled[0][j], f"PMLocation {column} retained")
check(control["TaskBreakDown"] == scaled["TaskBreakDown"] == parent["TaskBreakDown"], "task definitions remain but unreferenced")
check(columns(control["ScaleFactors"]) == ["SCFRT", "SCRPT", "SCLDT", "SCPMI", "SCPMT", "SCTRT"], "six authored scale fields")
check(rows(control["ScaleFactors"]) == [[1, 1, 1, 1, 1, 1]], "control scale row")
check(rows(scaled["ScaleFactors"]) == [[1, 1, 1, 1, 2, 1]], "scaled SCPMT2 row")
check(diff["parent_input_sha256"] == sha(source["parent"]) and diff["control_input_sha256"] == sha(CASE / "control-input.json") and diff["scaled_input_sha256"] == sha(CASE / "scaled-input.json"), "exact diff source pins")
check(diff["control_delta"]["field"] == "TID" and diff["scaled_delta"]["field"] == "SCPMT" and diff["other_changes"] == [], "declared two-stage discriminator")
check(sum(bool(rows(t)) for t in control.values()) == sum(bool(rows(t)) for t in scaled.values()) == 19, "19 row-containing source tables each")


def event_lines(run: Path) -> list[tuple[float, str]]:
    result = []
    for line in (run / "model.log").read_text(encoding="utf-8-sig").splitlines():
        match = re.match(r"^Time:\s*([0-9.]+)\s+(.*)$", line)
        if match:
            result.append((float(match.group(1)), match.group(2).strip()))
    return result


def containing(events: list[tuple[float, str]], fragment: str) -> list[float]:
    return [time for time, line in events if fragment in line]


def exact(events: list[tuple[float, str]], text: str) -> list[float]:
    return [time for time, line in events if line == text]


arms: dict[str, dict] = {}
for arm in ["control", "scaled"]:
    run = RUNS[arm]
    expected_input = CASE / f"{arm}-input.json"
    other_input = CASE / ("scaled-input.json" if arm == "control" else "control-input.json")
    invocation = load(run / "invocation.json")
    closure = load(run / "closure.json")
    steps = load(run / "steps.json")
    prefix = f"{arm}: "
    check(invocation["run_id"] == run.name and closure["run_id"] == run.name, prefix + "run identity")
    check(sha(run / "invocation.json") == closure["invocation_sha256"], prefix + "invocation sealed")
    check(invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0, prefix + "session-0 SSH")
    check("sshd.exe" in invocation["ssh_ancestor_names"], prefix + "SSH ancestor")
    check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, prefix + "GUI13340 session1")
    check(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", prefix + "queue mutex")
    check(invocation["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"], prefix + "before/after source stability")
    local_sources = dict(source)
    local_sources["input"] = expected_input
    local_sources["other_arm"] = other_input
    local_sources[f"check_{arm}_roundtrip.py"] = CASE / f"check_{arm}_roundtrip.py"
    local_sources[f"run_{arm}_ssh.ps1"] = CASE / f"run_{arm}_ssh.ps1"
    for key, path in sorted(local_sources.items()):
        check(path.is_file() and sha(path) == closure["source_hashes_before"].get(key), prefix + f"source fingerprint {key}")
    for contract_key, closure_key in [("simlox_exe_sha256", "exe"), ("manual_pdf_sha256", "manual"), ("dictionary_sha256", "dictionary")]:
        check(closure["source_hashes_before"][closure_key] == contract["source"][contract_key], prefix + f"installed {closure_key} pin")
    check(len(closure["raw"]) == 12, prefix + "twelve raw seals")
    for filename, seal in sorted(closure["raw"].items()):
        path = run / filename
        check(path.is_file(), prefix + f"raw present {filename}")
        if path.is_file():
            check(path.stat().st_size == seal["bytes"], prefix + f"raw length {filename}")
            check(sha(path) == seal["sha256"], prefix + f"raw SHA {filename}")
    check(sha(run / "input.json") == sha(expected_input), prefix + "native input frozen source")
    check(closure["error"] is None, prefix + "closure no error")
    check([step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"], prefix + "five guarded steps")
    for step in steps:
        check(step["status"] == "completed" and step["exit_code"] == 0 and step["error"] is None, prefix + f"step {step['name']}")
    for step in steps[:4]:
        check(step["gui_preserved"] is True, prefix + f"GUI after {step['name']}")
    for planned, actual in zip(invocation["planned_commands"], steps):
        check(planned["name"] == actual["name"] and planned["arguments"] == actual["arguments"], prefix + f"planned command {actual['name']}")
    check((run / "model.sxo").stat().st_size > 100000, prefix + "usable SXO")
    run_log = (run / "run.log").read_text(encoding="utf-8-sig")
    check(re.search(r"Errors:\s*0,\s*Warnings:\s*2,\s*Notes:\s*0", run_log) is not None, prefix + "zero-error converter")
    check(re.findall(r"warning #(\d+)", run_log) == ["108", "126"], prefix + "only warnings #108/#126")
    check("Starting simulation" in run_log and "Saving results" in run_log, prefix + "simulation and report output")
    authored_tables = tables(load(expected_input), "model")
    exported_tables = tables(load(run / "roundtrip-raw.json"), "model")
    check(set(authored_tables) == set(exported_tables), prefix + "exported table names")
    for name in sorted(authored_tables):
        authored, exported = authored_tables[name], exported_tables[name]
        authored_cols, exported_cols = columns(authored), columns(exported)
        check(set(authored_cols).issubset(exported_cols), prefix + f"authored columns {name}")
        if rows(authored):
            projected = [[row[exported_cols.index(key)] for key in authored_cols] for row in rows(exported)]
            check(projected == rows(authored), prefix + f"lossless rows {name}")
        else:
            check(not any(any(value is not None for value in row) for row in rows(exported)), prefix + f"no substantive rows {name}")
    scale_export = exported_tables["ScaleFactors"]
    extra_scale_fields = sorted(set(columns(scale_export)) - set(columns(authored_tables["ScaleFactors"])))
    check(len(extra_scale_fields) == 10, prefix + "ten native-added scale fields")
    for key in extra_scale_fields:
        check(all(row[columns(scale_export).index(key)] is None for row in rows(scale_export)), prefix + f"null added scale field {key}")
    arms[arm] = {"run": run, "events": event_lines(run), "report": tables(load(run / "report-raw.json"), "report")}

check(sha(RUNS["control"] / "closure.json") == "e51e54df8128139ac53bf21287832b4d05f20d847f2ec056820646e73a515f78", "control closure pin")
check(sha(RUNS["scaled"] / "closure.json") == "2e7b665a86c7fb57bbcf224fb52db788c1b9631405b5d56dc90a612f75df0d5e", "scaled closure pin")

for arm, starts, ends, duration in [
    ("control", [24, 49], [25, 50], 1),
    ("scaled", [24, 52], [28, 56], 4),
]:
    events = arms[arm]["events"]
    prefix = f"{arm}: "
    for number, (start, end) in enumerate(zip(starts, ends)):
        base = f"system PM task {number} on <TEACH-AIR-01,0>"
        sub = f"subtask {number} seqno 0 within {base}"
        check(exact(events, base + " started") == [start], prefix + f"PM task {number} starts")
        check(exact(events, base + " PMID: CAL24") == [start], prefix + f"PM task {number} identity")
        check(exact(events, sub + " started") == [start], prefix + f"fallback subtask {number} starts")
        check(exact(events, sub + f" starts performing, planned to last for {duration} hours") == [start], prefix + f"fallback subtask {number} duration")
        check(exact(events, sub + " requests resources: no resources needed") == [start], prefix + f"PM subtask {number} no resource")
        check(exact(events, sub + " completed") == [end], prefix + f"fallback subtask {number} completes")
        check(exact(events, base + " completed") == [end], prefix + f"PM task {number} completes")
    check(sum("system PM task" in line and line.endswith(" started") and line.startswith("system PM task") for _, line in events) == 2, prefix + "exactly two PM tasks")
    for fragment, expected in [
        ("mission ordered: BASIC-MISSION", [7, 19, 31]),
        ("mission starting, duration: 2", [8, 20, 32]),
        ("mission success:", [10, 22, 34]),
        ("mission completed:", [10, 22, 34]),
    ]:
        check(containing(events, fragment) == expected, prefix + f"mission {fragment}")
    check(not any("mission cancelled:" in line or "mission aborted:" in line for _, line in events), prefix + "no terminal mission cancellation/abort")
    check(containing(events, "nbr ready decreased at unit:") == sorted([7, 19, 31] + starts), prefix + "ready decrements")
    check(containing(events, "nbr ready increased at unit:") == sorted([0, 10, 22, 34] + ends), prefix + "ready increments")
    check(events[-1][1].endswith("systems ready: 1 :<TEACH-AIR-01,0>"), prefix + "terminal ready")

control_report = arms["control"]["report"]
scaled_report = arms["scaled"]["report"]
parent_report = tables(load(PARENT_RUN / "report-raw.json"), "report")
check(set(control_report) == set(scaled_report) == {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"}, "paired report schema")
check(rows(control_report["ResultSummary"]) == rows(scaled_report["ResultSummary"]) == rows(parent_report["ResultSummary"]), "summary parity with accepted D03")
summary = dict(zip(columns(control_report["ResultSummary"]), rows(control_report["ResultSummary"])[0]))
check(summary["NREP"] == 1 and summary["MTMF"] == 1 and summary["MSTF"] == 1 and summary["MSUF"] == 1 and summary["STMF"] == 1, "one replication and successful summary factors")
control_stock = rows(control_report["StockTotalResults"])
scaled_stock = rows(scaled_report["StockTotalResults"])
parent_stock = rows(parent_report["StockTotalResults"])
check(len(control_stock) == len(scaled_stock) == len(parent_stock) == 120, "120 stock bins per arm")
for index, (cr, sr, pr) in enumerate(zip(control_stock, scaled_stock, parent_stock)):
    check(cr == sr == pr, f"stock bin {index} parity with parent")
    check(cr[0] == index / 2 and cr[1] == (index + 1) / 2, f"stock bin {index} interval")
    check(cr[2] == 0 and cr[9] == 1 and all(value == 0 for value in cr[10:]), f"stock bin {index} no physical movement")

control_system = rows(control_report["SystemResults"])
scaled_system = rows(scaled_report["SystemResults"])
system_cols = columns(control_report["SystemResults"])
check(system_cols == columns(scaled_report["SystemResults"]) == columns(parent_report["SystemResults"]), "SystemResults columns aligned")
check(len(control_system) == len(scaled_system) == 120, "120 SystemResults bins per arm")


def get(row: list, column: str):
    return row[system_cols.index(column)]


def occupancy(first: float, last: float, start: float, end: float) -> float:
    return max(0.0, min(last, end) - max(first, start)) / (end - start)


for arm, system, windows, starts, ends, duration in [
    ("control", control_system, [(24, 25), (49, 50)], [24, 49], [25, 50], 1),
    ("scaled", scaled_system, [(24, 28), (52, 56)], [24, 52], [28, 56], 4),
]:
    for index, row in enumerate(system):
        start, end = index / 2, (index + 1) / 2
        check(get(row, "STINT") == start and get(row, "ETINT") == end, f"{arm} system bin {index} interval")
        reserved = sum(occupancy(a, b, start, end) for a, b in [(7, 8), (19, 20), (31, 32)])
        flying = sum(occupancy(a, b, start, end) for a, b in [(8, 10), (20, 22), (32, 34)])
        pm = sum(occupancy(a, b, start, end) for a, b in windows)
        expected = {
            "NSYMR": reserved, "NSYMO": flying, "NSYMA": reserved + flying,
            "FTMO": flying, "STACC": flying, "NSYPM": pm, "NSYUA": pm,
            "NSYRY": 1 - reserved - flying - pm, "NSYA": 1 - pm,
        }
        for key, value in expected.items():
            check(close(get(row, key), value), f"{arm} system bin {index} {key} event occupancy")
        check(get(row, "NPMS") == (1 if start in starts else 0), f"{arm} system bin {index} PM start marker")
        check(get(row, "NPMT") == (1 if start in ends else 0), f"{arm} system bin {index} PM completion marker")
        check(get(row, "NSYDT") == (1 if start in starts else 0), f"{arm} system bin {index} downtime-start marker")
        check(get(row, "SYDT") == (duration if start in starts else None), f"{arm} system bin {index} downtime-duration marker")

changed = {"NSYRY", "NSYUA", "NSYA", "NSYPM", "NPMS", "NPMT", "SYDT", "NSYDT"}
for index, (cr, sr) in enumerate(zip(control_system, scaled_system)):
    for column, a, b in zip(system_cols, cr, sr):
        if column not in changed:
            check(a == b, f"system bin {index} unchanged {column}")
check(close(sum(get(row, "NSYPM") * .5 for row in control_system), 2), "control PM 2 aircraft-hours")
check(close(sum(get(row, "NSYPM") * .5 for row in scaled_system), 8), "scaled PM 8 aircraft-hours")
check(close(sum(get(row, "STACC") * .5 for row in control_system), 6), "control flight 6 aircraft-hours")
check(close(sum(get(row, "STACC") * .5 for row in scaled_system), 6), "scaled flight 6 aircraft-hours")
for arm, system in [("control", control_system), ("scaled", scaled_system)]:
    check(get(system[-1], "NSYRY") == 1 and get(system[-1], "NSYPM") == 0, f"{arm} final ready, no PM")

result = {
    "schema": "independent-j09-var05-pmt-fallback-readonly/v1",
    "case": "J09.var05 matched task-free PMT fallback",
    "passed": not failures,
    "verdict": "GO: bounded observed SCPMT=1 versus 2 PMT-fallback contrast" if not failures else "NO-GO: independent replay failure",
    "checks_passed": checks - len(failures),
    "checks_total": checks,
    "failures": failures,
    "evidence": {
        "control_input_sha256": sha(CASE / "control-input.json"),
        "scaled_input_sha256": sha(CASE / "scaled-input.json"),
        "contract_sha256": sha(CASE / "contract.json"),
        "control_closure_sha256": sha(RUNS["control"] / "closure.json"),
        "scaled_closure_sha256": sha(RUNS["scaled"] / "closure.json"),
        "control_report_sha256": sha(RUNS["control"] / "report-raw.json"),
        "scaled_report_sha256": sha(RUNS["scaled"] / "report-raw.json"),
        "control_pm_windows_hours": [[24, 25], [49, 50]],
        "scaled_pm_windows_hours": [[24, 28], [52, 56]],
        "control_pm_system_hours": 2,
        "scaled_pm_system_hours": 8,
        "mission_start_hours": [8, 20, 32],
        "mission_success_hours": [10, 22, 34],
        "report_bins_per_table": 120,
    },
    "limits": [
        "One installed CLI engine, one aircraft, seed 1, task-free PMT fallback, SCPMT 1 versus 2, and a 60-hour horizon.",
        "The SCPMT=2 arm logs four-hour PM work, not a two-hour outcome. The logs do not expose why the factor manifests as four hours; a double-application mechanism is unproven.",
        "The second observed starts at 49 and 52 follow the first completions by 24 hours in these runs; no general PM renewal rule is inferred.",
        "The earlier task-referenced SCPMT=2 diagnostic was unchanged from D03 and remains excluded; the positive observation applies only to this task-free fallback pair.",
        "No claim for other PM tasks, scales, seeds, resource shortage, GUI-only execution, or cross-engine parity.",
    ],
}
OUTPUT.write_bytes((json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
print(f"{result['verdict']}; {result['checks_passed']}/{result['checks_total']} checks")
for item in failures[:20]:
    print("FAIL", item)
if failures:
    raise SystemExit(1)
