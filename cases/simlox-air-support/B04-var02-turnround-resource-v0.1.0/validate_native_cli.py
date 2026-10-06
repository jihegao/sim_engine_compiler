"""Bounded author gate for B04.var02 sufficient turnround crew."""

import hashlib
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
from validate_native import remove_trailing_commas  # noqa: E402

RUN_ID = "b04-var02-turn-resource-v010-ssh-20261006-01"
INPUT_SHA = "0d799bc6b2d4f8184db0bc33ddbffcaa51a822478b746fab3d4be9d942ee34d5"
PARENT_REPORT = HERE.parent / "B04-var05-turnround-breakdown-v0.1.0" / "runs" / "b04-var05-turnbreak-v010-ssh-20261006-01" / "report-raw.json"
PARENT_REPORT_SHA = "df1c6055ce7cd32dea0e02112ab752bc34ec2484311e7d0baa44b04910a1c87a"
AIRCRAFT = "<TEACH-AIR-01,0>"
MISSION = re.compile(r"^Time: ([0-9.]+) <BASIC-MISSION,TEACH-UNIT,0,0,([01])> (mission allocates system|mission preassigns a system|mission starting|mission success|mission completed|mission cancelled)[,:] ?(.*)$", re.M)
PERSON = re.compile(r"^Time: ([0-9.]+) <TEACH-AIR-01,0> (preparation started|preparation ended|turnround started|turnround ended), mission: <BASIC-MISSION,TEACH-UNIT,0,0,([01])>", re.M)
SUBTASK = re.compile(r"^Time: ([0-9.]+)  subtask \d+ seqno (\d+) within system (preparation|turnround) task \d+ on <TEACH-AIR-01,0> (started|starts performing, planned to last for ([0-9.]+) hours|completed)$", re.M)
ORDERED = re.compile(r"^Time: ([0-9.]+) <TEACH-UNIT> mission ordered: BASIC-MISSION$", re.M)
CREATED = re.compile(r"^Time: ([0-9.]+) <BASIC-MISSION,TEACH-UNIT,0,0,([01])> mission created: ?$", re.M)
ACTIVATED = re.compile(r"^Time: ([0-9.]+) <BASIC-MISSION,TEACH-UNIT,0,0,([01])> mission activated, systems requested: 1$", re.M)
ARRIVES = re.compile(r"^Time: ([0-9.]+) <TEACH-AIR-01,BASE-01,0> System arrives <TEACH-AIR-01,0>, mission success, ?$", re.M)
TURN_RESOURCE = re.compile(r"^Time: ([0-9.]+)  subtask \d+ seqno 1 within system turnround task \d+ on <TEACH-AIR-01,0> (requests resources|resource availability test|books resources|starts performing, planned to last for [0-9.]+ hours|completed|frees resources)$", re.M)
RESOURCE_BOOK = re.compile(r"^Time: ([0-9.]+)  <P-CREW at <BASE-01,0>> allocated to maintenance task: 1  available now: 0$", re.M)
RESOURCE_FREE = re.compile(r"^Time: ([0-9.]+)  <P-CREW at <BASE-01,0>> deallocated from  maintenance task: 1  available now: 1$", re.M)
RESOURCE_OK = re.compile(r"^  Availability test on  <P-CREW at <BASE-01,0>> request for: 1 OK ?$", re.M)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def close(actual, expected, label, problems, tolerance=0.00011):
    if not math.isclose(actual, expected, rel_tol=0, abs_tol=tolerance):
        problems.append(f"{label}: expected {expected}, got {actual}")


def rows(report, name):
    table = next(table for table in report["report"]["tables"] if table["name"] == name)
    return [column["name"] for column in table["columns"]], [row for inst in table["instances"] for row in inst["rows"]]


def full_ledger_compare(report, problems):
    if sha(PARENT_REPORT) != PARENT_REPORT_SHA:
        problems.append("accepted parent report raw SHA differs")
        return
    parent = json.loads(remove_trailing_commas(PARENT_REPORT.read_bytes()))
    for table_name, expected_rows, expected_cols in (
        ("ResultSummary", 1, 11),
        ("SystemResults", 72, 40),
        ("StockTotalResults", 72, 16),
    ):
        parent_cols, parent_rows = rows(parent, table_name)
        actual_cols, actual_rows = rows(report, table_name)
        if parent_cols != actual_cols or len(parent_cols) != expected_cols:
            problems.append(f"{table_name} full column topology differs")
            continue
        if len(parent_rows) != expected_rows or len(actual_rows) != expected_rows:
            problems.append(f"{table_name} full row count differs")
            continue
        for row_index, (want, got) in enumerate(zip(parent_rows, actual_rows)):
            for column, target, value in zip(parent_cols, want, got):
                if target != value:
                    problems.append(f"{table_name}[{row_index}].{column}: expected {target!r}, got {value!r}")
    parent_cols, parent_rows = rows(parent, "ProblemDescription")
    actual_cols, actual_rows = rows(report, "ProblemDescription")
    if (parent_cols, parent_rows) != (actual_cols, actual_rows):
        problems.append("ProblemDescription report differs from accepted parent")


def check_resource_ledger(report, problems):
    names, resource = rows(report, "ResourceResults")
    expected_names = ["RID", "STID", "STINT", "ETINT", "NR", "NRMO", "NRMA",
                      "NRUM", "NRLA", "NRW", "NRA", "NRN", "NRF", "NRRI", "NRRT", "NRRO"]
    if names != expected_names or len(resource) != 72:
        problems.append("ResourceResults 72x16 topology differs")
        return len(resource)
    index = {name: i for i, name in enumerate(names)}
    for i, row in enumerate(resource):
        if row[index["RID"]] != "Total over all Resources" or row[index["STID"]] != "Total over all Stations":
            problems.append(f"ResourceResults[{i}] identity differs")
        close(row[index["STINT"]], i / 2, f"ResourceResults[{i}].STINT", problems, 1e-8)
        close(row[index["ETINT"]], (i + 1) / 2, f"ResourceResults[{i}].ETINT", problems, 1e-8)
        expected = {"NR": 1, "NRMO": 0, "NRMA": 0,
                    "NRUM": 1 / 3 if i in (47, 53) else 0,
                    "NRLA": 0, "NRW": 0, "NRA": 1, "NRN": 1,
                    "NRF": 0, "NRRI": 0, "NRRT": 0, "NRRO": 0}
        for name, want in expected.items():
            close(row[index[name]], want, f"ResourceResults[{i}].{name}", problems, 1e-6)
    close(sum(row[index["NRUM"]] / 2 for row in resource), 1 / 3,
          "ResourceResults used person-hours", problems, 1e-6)
    return len(resource)


def validate(run):
    problems = []
    if run.name != RUN_ID:
        problems.append("unreviewed run identity")
    if sha(HERE / "native-input.json") != INPUT_SHA or sha(run / "input.json") != INPUT_SHA:
        problems.append("frozen/run input bytes differ")
    roundtrip = json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
    if roundtrip.get("passed") is not True or roundtrip.get("source_sha256") != INPUT_SHA:
        problems.append("full authored-table roundtrip not verified")
    run_log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    if "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" not in run_log:
        problems.append("converter zero-error/two-warning summary differs")
    if sorted(map(int, re.findall(r"warning #(\d+)", run_log))) != [108, 126]:
        problems.append("warning codes differ")
    if "Total execution time:" not in run_log:
        problems.append("simulation completion marker absent")
    for name in ("model.sxo", "model.log", "report-raw.json", "report-export.log"):
        path = run / name
        if not path.is_file() or path.stat().st_size <= 4:
            problems.append(f"missing/empty {name}")
    if problems:
        return {"passed": False, "problems": problems}
    log = (run / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    for label, actual, expected in (
        ("mission ordered", [float(match.group(1)) for match in ORDERED.finditer(log)], [20.5, 23.75]),
        ("mission created", [(int(match.group(2)), float(match.group(1))) for match in CREATED.finditer(log)], [(0, 20.5), (1, 23.75)]),
        ("mission activated", [(int(match.group(2)), float(match.group(1))) for match in ACTIVATED.finditer(log)], [(0, 20.5), (1, 23.75)]),
        ("System arrives after turnround", [float(match.group(1)) for match in ARRIVES.finditer(log)], [24.0, 27.25]),
    ):
        if actual != expected:
            problems.append(f"{label} lifecycle differs: {actual!r}")
    missions = {}
    for match in MISSION.finditer(log):
        time, wave, kind, detail = match.groups()
        missions.setdefault((int(wave), kind), []).append((float(time), detail))
    expected_missions = {
        (0, "mission allocates system"): 20.5,
        (0, "mission starting"): 21.5,
        (0, "mission success"): 23.5,
        (0, "mission completed"): 23.5,
        (1, "mission preassigns a system"): 23.75,
        (1, "mission allocates system"): 24.0,
        (1, "mission starting"): 24.75,
        (1, "mission success"): 26.75,
        (1, "mission completed"): 26.75,
    }
    if set(missions) != set(expected_missions):
        problems.append(f"mission event kinds differ: {sorted(missions)}")
    for key, expected in expected_missions.items():
        entries = missions.get(key, [])
        if len(entries) != 1:
            problems.append(f"mission event count differs: {key}")
            continue
        close(entries[0][0], expected, f"mission {key}", problems)
        if AIRCRAFT not in entries[0][1] and key[1] != "mission success":
            problems.append(f"mission aircraft identity absent: {key}")
    personal = {}
    for match in PERSON.finditer(log):
        time, kind, wave = match.groups()
        personal.setdefault((int(wave), kind), []).append(float(time))
    expected_personal = {
        (0, "preparation started"): 20.5, (0, "preparation ended"): 21.0,
        (0, "turnround started"): 23.5, (0, "turnround ended"): 24.0,
        (1, "preparation started"): 24.0, (1, "preparation ended"): 24.5,
        (1, "turnround started"): 26.75, (1, "turnround ended"): 27.25,
    }
    if set(personal) != set(expected_personal):
        problems.append("preparation/turnround lifecycle kinds differ")
    for key, expected in expected_personal.items():
        values = personal.get(key, [])
        if len(values) != 1:
            problems.append(f"lifecycle count differs: {key}")
        else:
            close(values[0], expected, f"lifecycle {key}", problems)
    subtasks = {}
    durations = {}
    for match in SUBTASK.finditer(log):
        time, seq, task_kind, kind, duration = match.groups()
        event = "perform" if kind.startswith("starts performing") else kind
        key = (task_kind, int(seq), event)
        subtasks.setdefault(key, []).append(float(time))
        if duration is not None:
            durations.setdefault((task_kind, int(seq)), []).append(float(duration))
    expected_subtasks = {
        ("preparation", 1, "started"): [20.5, 24.0],
        ("preparation", 1, "perform"): [20.5, 24.0],
        ("preparation", 1, "completed"): [20.6667, 24.1667],
        ("preparation", 2, "started"): [20.6667, 24.1667],
        ("preparation", 2, "perform"): [20.6667, 24.1667],
        ("preparation", 2, "completed"): [21.0, 24.5],
        ("turnround", 1, "started"): [23.5, 26.75],
        ("turnround", 1, "perform"): [23.5, 26.75],
        ("turnround", 1, "completed"): [23.6667, 26.9167],
        ("turnround", 2, "started"): [23.6667, 26.9167],
        ("turnround", 2, "perform"): [23.6667, 26.9167],
        ("turnround", 2, "completed"): [24.0, 27.25],
    }
    if set(subtasks) != set(expected_subtasks):
        problems.append(f"turnround subtask kinds differ: {sorted(subtasks)}")
    for key, expected in expected_subtasks.items():
        actual = subtasks.get(key, [])
        if len(actual) != 2:
            problems.append(f"subtask count differs: {key}")
        else:
            for index in range(2):
                close(actual[index], expected[index], f"subtask {key}/{index}", problems)
    if set(durations) != {(kind, seq) for kind in ("preparation", "turnround") for seq in (1, 2)}:
        problems.append("subtask planned-duration topology differs")
    for key, expected in {("preparation", 1): 1 / 6, ("preparation", 2): 1 / 3,
                          ("turnround", 1): 1 / 6, ("turnround", 2): 1 / 3}.items():
        actual = durations.get(key, [])
        if len(actual) != 2:
            problems.append(f"subtask planned-duration count differs: {key}")
        else:
            for value in actual:
                close(value, expected, f"subtask planned duration {key}", problems)
    resource_events = [(float(match.group(1)), match.group(2), match.start())
                       for match in TURN_RESOURCE.finditer(log)]
    expected_kinds = ["requests resources", "resource availability test", "books resources",
                      "starts performing, planned to last for 0.166667 hours",
                      "completed", "frees resources"]
    if len(resource_events) != 12 or [event[1] for event in resource_events] != expected_kinds * 2:
        problems.append("two exact turnround crew request/book/work/free cycles absent")
    else:
        for index, (start, end) in enumerate(((23.5, 23.6667), (26.75, 26.9167))):
            cycle = resource_events[index * 6:(index + 1) * 6]
            for time, kind, _ in cycle[:4]:
                close(time, start, f"crew cycle {index} {kind}", problems)
            for time, kind, _ in cycle[4:]:
                close(time, end, f"crew cycle {index} {kind}", problems)
            if not (cycle[0][2] < cycle[1][2] < cycle[2][2] < cycle[3][2] < cycle[4][2] < cycle[5][2]):
                problems.append(f"crew cycle {index} event order differs")
    for regex, expected_times, label in (
        (RESOURCE_BOOK, [23.5, 26.75], "crew allocation"),
        (RESOURCE_FREE, [23.6667, 26.9167], "crew release"),
    ):
        actual = [float(match.group(1)) for match in regex.finditer(log)]
        if len(actual) != 2:
            problems.append(f"{label} count differs: {actual}")
        else:
            for i, value in enumerate(actual):
                close(value, expected_times[i], f"{label}/{i}", problems)
    if len(RESOURCE_OK.findall(log)) != 2 or "request for: 1 NOT OK" in log:
        problems.append("crew availability result differs")
    if "mission cancelled" in log or "mission aborted" in log:
        problems.append("unexpected mission cancellation/abort")
    report = json.loads(remove_trailing_commas((run / "report-raw.json").read_bytes()))
    report_names = [table["name"] for table in report["report"]["tables"]]
    if report_names != ["ProblemDescription", "ResultSummary", "SystemResults",
                        "StockTotalResults", "ResourceResults"]:
        problems.append(f"unexpected report table topology: {report_names}")
    full_ledger_compare(report, problems)
    resource_bins = check_resource_ledger(report, problems)
    summary_columns, summary_rows = rows(report, "ResultSummary")
    if len(summary_rows) != 1:
        problems.append("summary row count differs")
    else:
        summary = dict(zip(summary_columns, summary_rows[0]))
        for name, expected in {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MTMF": 1,
                               "MSTF": 1, "MSUF": 1, "STMF": 1}.items():
            if summary.get(name) != expected:
                problems.append(f"summary {name} differs")
    columns, system = rows(report, "SystemResults")
    stock_columns, stock = rows(report, "StockTotalResults")
    if len(system) != 72 or len(stock) != 72:
        problems.append("full 72-bin System/Stock shape differs")
    else:
        sx = {name: columns.index(name) for name in ("STINT", "ETINT", "NSYRY", "NSYMA", "NSYMO", "NSYMP", "NSYMT", "FTMO", "NFAIL", "NPMS", "NPMT")}
        if system[0][sx["STINT"]] != 0 or system[-1][sx["ETINT"]] != 36:
            problems.append("System time window differs")
        if system[0][sx["NSYRY"]] != 1 or system[-1][sx["NSYRY"]] != 1:
            problems.append("initial/terminal aircraft readiness differs")
        for row in system:
            if abs(row[sx["NSYRY"]] + row[sx["NSYMA"]] - 1) > 1e-9:
                problems.append("one-aircraft ready/assigned balance differs")
            if any(row[sx[name]] for name in ("NFAIL", "NPMS", "NPMT")):
                problems.append("unexpected failure/PM")
        def integral(name):
            return sum((row[sx["ETINT"]] - row[sx["STINT"]]) * (row[sx[name]] or 0)
                       for row in system)
        for name, expected in (("NSYMO", 4), ("FTMO", 4), ("NSYMP", 1), ("NSYMT", 1)):
            close(integral(name), expected, f"System integral {name}", problems, 1e-8)
        stock_ix = {name: stock_columns.index(name) for name in ("NBO", "NBOU", "NDF", "NDD", "NDR", "NDP", "NWT")}
        if any(row[stock_ix[name]] for row in stock for name in stock_ix):
            problems.append("unexpected stock demand, movement or wait")
    return {"schema": "simlox-b04-var02-native-author/v1", "run_id": run.name,
            "passed": not problems, "decision": "GO_BOUNDED" if not problems else "NO_GO",
            "problems": problems, "input_sha256": INPUT_SHA,
            "system_bins": len(system), "stock_bins": len(stock), "resource_bins": resource_bins,
            "scope": "one deterministic sufficient turnround crew; independent full-ledger replay still required"}


def main():
    try:
        result = validate(Path(sys.argv[1]))
    except Exception as exc:
        result = {"schema": "simlox-b04-var02-native-author/v1", "passed": False,
                  "decision": "NO_GO", "problems": [f"checker exception: {type(exc).__name__}: {exc}"]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
