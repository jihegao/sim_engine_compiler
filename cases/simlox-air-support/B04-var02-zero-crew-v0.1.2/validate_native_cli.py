"""Strict author gate for one B04.var02 zero-crew turnround child."""

import hashlib
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tools"))
from validate_native import remove_trailing_commas  # noqa: E402

RUN_ID = "b04-var02-zero-crew-v012-ssh-20261007-01"
INPUT_SHA = "fa7b9040fced6267aa5781cb0761df41b803c0cccaf8c218a2aa0c1de01b24bb"
PARENT_REPORT = HERE.parent / "B04-var02-turnround-resource-v0.1.1" / "runs" / "b04-var02-turn-resource-v011-ssh-20261006-01" / "report-raw.json"
PARENT_REPORT_SHA = "b7125fabb23ff4e4684da45a710cffae96dfd22ec11dea772103bcaacdcedef7"
TIME = re.compile(r"^Time: ([0-9.]+) (.*)$", re.M)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def close(actual, expected, label, errors, tolerance=1e-5):
    if not isinstance(actual, (int, float)) or not math.isclose(actual, expected, rel_tol=0, abs_tol=tolerance):
        errors.append(f"{label}: expected {expected!r}, got {actual!r}")


def table(report, name):
    matches = [t for t in report["report"]["tables"] if t["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"missing/duplicate report table {name}")
    t = matches[0]
    return [c["name"] for c in t["columns"]], [r for inst in t["instances"] for r in inst["rows"]]


def events(raw):
    return [(float(m.group(1)), m.group(2).strip(), m.start()) for m in TIME.finditer(raw)]


def matching(items, text):
    return [event for event in items if text in event[1]]


def validate_events(raw, errors):
    found = events(raw)
    if any(a[0] > b[0] + 1e-6 for a, b in zip(found, found[1:])):
        errors.append("native event times decrease")
    mission0 = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    mission1 = "<BASIC-MISSION,TEACH-UNIT,0,0,1>"
    aircraft = "<TEACH-AIR-01,0>"
    expected = [
        ("mission ordered: BASIC-MISSION", [20.5, 23.75]),
        (mission0 + " mission starting, duration: 2 : " + aircraft, [21.5]),
        (mission0 + " mission success:", [23.5]),
        (mission0 + " mission completed: " + aircraft, [23.5]),
        (aircraft + " turnround started, mission: " + mission0, [23.5]),
    ]
    for marker, times in expected:
        matches = matching(found, marker)
        if len(matches) != len(times):
            errors.append(f"event {marker!r} count differs: {matches}")
        else:
            for event, time in zip(matches, times):
                close(event[0], time, f"event {marker}", errors, 0.00011)
    if len(matching(found, mission1 + " mission created:")) != 1:
        errors.append("second mission creation differs")
    cancelled = matching(found, mission1 + " mission cancelled:")
    if len(cancelled) != 1 or not 23.75 <= cancelled[0][0] <= 36:
        errors.append("second mission native cancellation absent or outside observation window")
    if matching(found, mission1 + " mission starting") or matching(found, mission1 + " mission success") or matching(found, mission1 + " mission completed"):
        errors.append("zero-crew second mission launched/completed")
    if matching(found, "mission aborted"):
        errors.append("unexpected mission abort")
    turn = [e for e in found if "within system turnround task" in e[1]]
    first = [e for e in turn if "seqno 1" in e[1]]
    if len(first) < 3 or [e[1].split("> ")[-1] for e in first[:3]] != ["started", "requests resources", "resource availability test"]:
        errors.append("first turnround subtask start/request/availability sequence differs")
    for e in first[:3]:
        close(e[0], 23.5, "blocked turnround start/request/test", errors, 0.00011)
    if len(matching(found, "Availability test on  <P-CREW at <BASE-01,0>> request for: 1 failed")) != 0:
        errors.append("availability continuation unexpectedly parsed as timed event")
    if raw.count("Availability test on  <P-CREW at <BASE-01,0>> request for: 1 failed") != 1:
        errors.append("exact one failed P-CREW request absent")
    if any("books resources" in e[1] or "starts performing" in e[1] or "completed" in e[1] or "frees resources" in e[1]
           for e in turn):
        errors.append("blocked turnround performed or completed work")
    if any("seqno 2" in e[1] for e in turn):
        errors.append("second turnround step started despite blocked first step")
    if any("allocated to maintenance task:" in e[1] or "deallocated from  maintenance task:" in e[1] for e in found):
        errors.append("zero crew unexpectedly booked or released")
    if matching(found, aircraft + " turnround ended, mission: " + mission0) or matching(found, "System arrives " + aircraft + ", mission success"):
        errors.append("first turnround ended/aircraft arrived despite blocked crew")
    wait_stops = [e for e in turn if "resource waiting stopped" in e[1]]
    if wait_stops and any(e[0] < 36 - 1e-5 for e in wait_stops):
        errors.append("first turnround resource wait stopped before horizon")
    return {"second_cancel_hour": cancelled[0][0] if len(cancelled) == 1 else None,
            "resource_wait_start_hour": 23.5, "resource_wait_end_hour": 36.0}


def compare_rows(name, got_columns, got_rows, want_columns, want_rows, errors):
    if got_columns != want_columns or len(got_rows) != len(want_rows):
        errors.append(f"{name} topology differs")
        return
    for i, (got, want) in enumerate(zip(got_rows, want_rows)):
        if len(got) != len(want):
            errors.append(f"{name}[{i}] width differs")
            continue
        for column, actual, expected in zip(got_columns, got, want):
            if actual != expected:
                errors.append(f"{name}[{i}].{column}: expected {expected!r}, got {actual!r}")


def validate_report(report, errors):
    expected_names = ["ProblemDescription", "ResultSummary", "SystemResults",
                      "StockTotalResults", "ResourceResults", "ResourceResultsTotal"]
    if [t["name"] for t in report["report"]["tables"]] != expected_names:
        errors.append("report table topology differs")
    if sha(PARENT_REPORT) != PARENT_REPORT_SHA:
        errors.append("accepted parent report SHA differs")
        return
    parent = json.loads(remove_trailing_commas(PARENT_REPORT.read_bytes()))
    for name in ("ProblemDescription", "StockTotalResults"):
        want_columns, want_rows = table(parent, name)
        got_columns, got_rows = table(report, name)
        compare_rows(name, got_columns, got_rows, want_columns, want_rows, errors)
    names, rows = table(report, "ResultSummary")
    expected_summary = [1, 0, 36, 0.5, 0, 0.5, 0, 0.5, 0, 0.5, 0]
    expected_summary_names = ["NREP", "RTILW", "RTIUP", "MTMF", "RSMTMF", "MSTF", "RSMSTF", "MSUF", "RSMSUF", "STMF", "RSSTMF"]
    if names != expected_summary_names or len(rows) != 1:
        errors.append("ResultSummary 1x11 topology differs")
    else:
        for name, got, want in zip(names, rows[0], expected_summary):
            close(got, want, f"ResultSummary.{name}", errors, 1e-6)
    parent_names, parent_rows = table(parent, "SystemResults")
    names, rows = table(report, "SystemResults")
    if names != parent_names or len(rows) != 72 or len(parent_rows) != 72 or len(names) != 40:
        errors.append("SystemResults 72x40 topology differs")
    else:
        for i, row in enumerate(rows):
            if i < 47:
                for name, got, want in zip(names, row, parent_rows[i]):
                    if got != want:
                        errors.append(f"SystemResults[{i}].{name} prefix differs")
            else:
                expected = {name: 0 for name in names if name not in ("UNID", "SID", "STINT", "ETINT")}
                expected.update(NSYMA=1, NSYMT=1, NSYA=1)
                expected.update(UNID="Total over all Units", SID="Total over all Systems", STINT=i / 2, ETINT=(i + 1) / 2)
                for name, got in zip(names, row):
                    want = expected[name]
                    if got != want:
                        errors.append(f"SystemResults[{i}].{name}: expected {want!r}, got {got!r}")
    names, rows = table(report, "ResourceResults")
    expected_resource_names = ["RID", "STID", "STINT", "ETINT", "NR", "NRMO", "NRMA", "NRUM", "NRLA", "NRW", "NRA", "NRN", "NRF", "NRRI", "NRRT", "NRRO"]
    if names != expected_resource_names or len(rows) != 72:
        errors.append("ResourceResults 72x16 topology differs")
    else:
        for i, row in enumerate(rows):
            expected = {name: 0 for name in names if name not in ("RID", "STID", "STINT", "ETINT")}
            expected.update(RID="Total over all Resources", STID="Total over all Stations",
                            STINT=i / 2, ETINT=(i + 1) / 2, NRW=1 if i >= 47 else 0)
            for name, got in zip(names, row):
                close(got, expected[name], f"ResourceResults[{i}].{name}", errors, 1e-6) if isinstance(expected[name], (int, float)) else (
                    errors.append(f"ResourceResults[{i}].{name} identity differs") if got != expected[name] else None)
    names, rows = table(report, "ResourceResultsTotal")
    expected_total_names = ["RID", "STID", "NR", "NRMO", "NRMA", "NRUM", "NRLA", "NRW", "NRA", "NRN", "NRF", "NRRI", "NRRT", "NRRO"]
    if names != expected_total_names or len(rows) != 1:
        errors.append("ResourceResultsTotal 1x14 topology differs")
    else:
        expected = ["Total over all Resources", "Total over all Stations", 0, 0, 0, 0, 0, 25 / 72, 0, 0, 0, 0, 0, 0]
        for name, got, want in zip(names, rows[0], expected):
            if isinstance(want, str):
                if got != want:
                    errors.append(f"ResourceResultsTotal.{name} identity differs")
            else:
                close(got, want, f"ResourceResultsTotal.{name}", errors, 1e-6)
    return {"system_bins": 72, "stock_bins": 72, "resource_bins": 72}


def validate(run):
    errors = []
    if run.name != RUN_ID:
        errors.append("unreviewed run identity")
    if sha(HERE / "native-input.json") != INPUT_SHA or sha(run / "input.json") != INPUT_SHA:
        errors.append("frozen/run input SHA differs")
    roundtrip = json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
    if not roundtrip.get("passed") or roundtrip.get("source_sha256") != INPUT_SHA:
        errors.append("21-table roundtrip absent")
    log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    if "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" not in log or sorted(map(int, re.findall(r"warning #(\d+)", log))) != [108, 126]:
        errors.append("converter diagnostics differ")
    if "Total execution time:" not in log:
        errors.append("simulation completion absent")
    for name in ("model.sxo", "model.log", "report-raw.json", "report-export.log"):
        path = run / name
        if not path.is_file() or path.stat().st_size <= 4:
            errors.append(f"missing/empty {name}")
    if errors:
        return {"passed": False, "problems": errors}
    observed = validate_events((run / "model.log").read_text(encoding="utf-8-sig", errors="replace"), errors)
    report = json.loads(remove_trailing_commas((run / "report-raw.json").read_bytes()))
    observed.update(validate_report(report, errors))
    return {"schema": "simlox-b04-var02-zero-crew-author/v1", "run_id": run.name,
            "passed": not errors, "decision": "GO_BOUNDED" if not errors else "NO_GO",
            "problems": errors, "input_sha256": INPUT_SHA, "observed": observed,
            "scope": "one deterministic zero-capacity turnround; independent raw replay required"}


def main():
    try:
        result = validate(Path(sys.argv[1]))
    except Exception as exc:
        result = {"schema": "simlox-b04-var02-zero-crew-author/v1", "passed": False,
                  "decision": "NO_GO", "problems": [f"checker exception: {type(exc).__name__}: {exc}"]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
