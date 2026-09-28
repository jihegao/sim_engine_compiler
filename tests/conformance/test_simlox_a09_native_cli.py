"""A09 native acceptance logic with synthetic raw shapes; no SIMLOX execution."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path, PureWindowsPath
import sys

import pytest


CASE = Path(__file__).resolve().parents[2] / "cases/simlox-air-support/A09-hierarchical-operation-profile"
spec = importlib.util.spec_from_file_location("simlox_a09_native_cli", CASE / "validate_native_cli.py")
assert spec is not None and spec.loader is not None
sys.path.insert(0, str(CASE))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def make_events() -> list[dict]:
    emitted: list[tuple[float, str, str]] = [(0, "ready_increased", "<TEACH-AIR-01,0> nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>")]
    for i, (notice, start, end) in enumerate(zip((7, 19, 31, 43), (8, 20, 32, 44), (10, 22, 34, 46))):
        tag = f"<BASIC-MISSION,TEACH-UNIT,0,0,{10 + i}>"  # deliberately non-A02 ordinals
        emitted.extend([
            (notice, "notification", "<TEACH-UNIT> mission ordered: BASIC-MISSION"),
            (notice, "created", f"{tag} mission created:"),
            (notice, "activated", f"{tag} mission activated, systems requested: 1"),
            (notice, "allocation", f"{tag} mission allocates system: <TEACH-AIR-01,0>"),
            (notice, "preparation_start", f"<TEACH-AIR-01,0> preparation started, mission: {tag}"),
            (notice, "preparation_end", f"<TEACH-AIR-01,0> preparation ended, mission: {tag}"),
            (notice, "ready_decreased", "<TEACH-AIR-01,0> nbr ready decreased at unit: <TEACH-UNIT at <BASE-01,0>>"),
            (start, "start", f"{tag} mission starting, duration: 2 : <TEACH-AIR-01,0>"),
            (start + .5, "task_start", f"{tag} task starting: <TEACH-AIR-01,0>"),
            (end - .5, "task_completion", f"{tag} task completed: <TEACH-AIR-01,0>"),
            (end, "success", f"{tag} mission success:"),
            (end, "completion", f"{tag} mission completed: <TEACH-AIR-01,0>"),
            (end, "ready_increased", "<TEACH-AIR-01,0> nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>"),
        ])
    emitted.sort(key=lambda e: e[0])
    return [{"line": line, "kind": kind, "time_hours_printed": str(time), "body": body}
            for line, (time, kind, body) in enumerate(emitted, 1)]


def report_table(name: str, records: list[dict]) -> dict:
    fields = list(records[0])
    return {"name": name, "columns": [{"name": field} for field in fields],
            "instances": [{"rows": [[row[field] for field in fields] for row in records]}]}


def make_report() -> dict:
    hand = module.CONTRACT["hand_expected_if_native_expansion_matches_hypothesis"]
    intervals = []
    for i in range(96):
        start, end = i * .5, (i + 1) * .5
        flying = int(any(left <= start < right for left, right in zip(hand["start_hours"], hand["end_hours"])))
        allocated = int(any(left <= start < right for left, right in zip(hand["notification_hours"], hand["end_hours"])))
        reserved = int(any(left <= start < right for left, right in zip(hand["notification_hours"], hand["start_hours"])))
        row = {"STINT": start, "ETINT": end, "UNID": "Total over all Units",
               "SID": "Total over all Systems", "NSYA": 1,
               "FTMO": flying, "NSYMO": flying, "NSYMA": allocated,
               "NSYMR": reserved, "NSYRY": 1 - allocated, "SYDT": None}
        row.update({field: 0 for field in module.native.ZERO_SYSTEM_FIELDS})
        intervals.append(row)
    return {"report": {"tables": [
        report_table("ResultSummary", [{"NREP": 1, "RTILW": 0, "RTIUP": 48, "MSTF": 1, "MSUF": 1}]),
        report_table("SystemResults", intervals),
    ]}}


def test_four_waves_accept_business_identity_without_assuming_native_ordinals() -> None:
    errors, tags = module.check_events(make_events())
    assert errors == []
    assert tags == [f"<BASIC-MISSION,TEACH-UNIT,0,0,{i}>" for i in (10, 11, 12, 13)]
    assert module.check_report(make_report()) == []


@pytest.mark.parametrize("kind,change,fragment", [
    ("start", lambda e: e.update(time_hours_printed="8.25"), "start wave times/count"),
    ("completion", lambda e: e.update(body=e["body"].replace("TEACH-AIR-01", "OTHER-AIR")), "completion identity"),
    ("created", lambda e: e.update(body=e["body"].replace("10>", "11>")), "four distinct native mission instance tags"),
    ("preparation_end", lambda e: e.update(time_hours_printed="7.5"), "preparation_end wave times/count"),
    ("ready_decreased", lambda e: e.update(body="wrong ready aircraft"), "aircraft ready_decreased"),
])
def test_event_mutations_fail(kind, change, fragment: str) -> None:
    events = make_events()
    change(next(event for event in events if event["kind"] == kind))
    errors, _ = module.check_events(events)
    assert any(fragment in error for error in errors)


def test_extra_fault_or_missing_wave_fails() -> None:
    events = make_events()
    events.append({"line": 100, "kind": "fault", "time_hours_printed": "47", "body": "critical random failure added"})
    assert any("unexpected fault" in error for error in module.check_events(events)[0])
    events = [event for event in make_events() if not (event["kind"] == "notification" and event["time_hours_printed"] == "43")]
    assert any("notification wave times/count" in error for error in module.check_events(events)[0])


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_event_time_fails(value: float) -> None:
    events = make_events()
    next(event for event in events if event["kind"] == "start")["time_hours_printed"] = str(value)
    assert any("non-finite time" in error for error in module.check_events(events)[0])


@pytest.mark.parametrize("mutation,fragment", [
    (lambda rows: rows[88].update(FTMO=0), "interval 88 FTMO"),
    (lambda rows: rows[0].update(NPSTA=1), "interval 0 unexpected NPSTA"),
    (lambda rows: rows[95].update(ETINT=47.5), "interval 95 grid"),
    (lambda rows: rows.pop(), "expected 96 intervals"),
])
def test_interval_or_mechanism_mutation_fails(mutation, fragment: str) -> None:
    report = make_report()
    table = report["report"]["tables"][1]
    fields = [column["name"] for column in table["columns"]]
    rows = [dict(zip(fields, row)) for row in table["instances"][0]["rows"]]
    mutation(rows)
    table["instances"][0]["rows"] = [[row[field] for field in fields] for row in rows]
    assert any(fragment in error for error in module.check_report(report))


@pytest.mark.parametrize("table_index,row_index,field,fragment", [
    (0, 0, "MSTF", "ResultSummary.MSTF"),
    (0, 0, "RTIUP", "ResultSummary.RTIUP"),
    (1, 88, "STINT", "interval 88 non-finite bounds"),
    (1, 88, "ETINT", "interval 88 non-finite bounds"),
    (1, 88, "FTMO", "interval 88 FTMO"),
    (1, 88, "NSYA", "interval 88 scope/system count"),
    (1, 88, "NPSTA", "interval 88 unexpected NPSTA"),
])
def test_nonfinite_report_number_fails(table_index: int, row_index: int, field: str, fragment: str) -> None:
    report = make_report()
    table = report["report"]["tables"][table_index]
    fields = [column["name"] for column in table["columns"]]
    table["instances"][0]["rows"][row_index][fields.index(field)] = float("nan")
    assert any(fragment in error for error in module.check_report(report))


def provenance(tmp_path: Path) -> tuple[Path, dict, dict, list[dict]]:
    run = tmp_path / "probe-flat"
    run.mkdir()
    raw = {}
    for name in module.RAW_NAMES:
        path = run / name
        path.write_bytes(("raw " + name).encode())
        raw[name] = {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    original = PureWindowsPath(r"C:\a09\probe-flat")
    invocation = {"schema": "simlox-a09-invocation/ssh-cli-v1", "case_id": "A09",
                  "case_version": "1.0.0-candidate", "variant": "flat", "execution_mode": "ssh_cli_v1",
                  "input_sha256": module.CONTRACT["candidate_input_sha256"]["flat"],
                  "flat_input_sha256": module.CONTRACT["candidate_input_sha256"]["flat"],
                  "nested_input_sha256": module.CONTRACT["candidate_input_sha256"]["nested"],
                  "simlox_exe_sha256": "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0",
                  "python_exe_sha256": "2204195cec25879507d958a8b6949add67091244b8b4da9cf3672f993548fa49",
                  "python_path": r"C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace\evidence\py312-venv\Scripts\python.exe",
                  "working_directory": r"C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace",
                  "session_id": 0, "session_name": None, "ssh_connection_present": True,
                  "ssh_ancestor_names": ["sshd.exe"], "created_utc": "2026-09-29T00:00:00Z",
                  "host_name": "4700-3", "queue_mutex": r"Global\SimloxIssue18NativeQueue",
                  "allow_existing_gui": False, "coexisting_gui": None,
                  "original_run_dir": str(original), "run_id": "probe-flat", "group_run_id": "probe"}
    files = {"contract_sha256": "contract.json", "static_validator_sha256": "validate.py",
             "native_validator_sha256": "validate_native_cli.py", "builder_sha256": "build.py",
             "runner_sha256": "run_native_ssh.ps1", "parameters_sha256": "parameters.json"}
    invocation.update({key: module.sha256(CASE / name) for key, name in files.items()})
    invocation["shared_parser_sha256"] = module.sha256(CASE.parent / "tools" / "validate_native.py")
    invocation["shared_binding_sha256"] = module.sha256(CASE.parent / "tools" / "native_binding.py")
    invocation["parent_input_sha256"] = module.CONTRACT["parent_input_sha256"]
    (run / "invocation.json").write_text(json.dumps(invocation), encoding="utf-8")
    steps = [{"name": name, "arguments": args, "exit_code": 0, "wall_seconds": .1,
              "started_utc": f"2026-09-29T00:0{i}:00Z", "completed_utc": f"2026-09-29T00:0{i}:01Z",
              "launch_error": None, "gui_state_check_passed": True,
              "gui_state_check_error": None, "coexisting_gui_present_after": False}
             for i, (name, args) in enumerate(module.expected_arguments(original).items(), 1)]
    closure = {"schema": "simlox-a09-closure/v1", "case_id": "A09", "variant": "flat", "run_id": "probe-flat",
               "input_sha256": invocation["input_sha256"],
               "invocation_sha256": module.sha256(run / "invocation.json"), "raw": raw}
    return run, invocation, closure, steps


def test_provenance_accepts_complete_serial_binding_and_rejects_tampering(tmp_path: Path) -> None:
    run, invocation, closure, steps = provenance(tmp_path)
    assert module.check_provenance(run, "flat", invocation, closure, steps) == []
    bad = copy.deepcopy(invocation)
    bad["native_validator_sha256"] = "0" * 64
    assert any("native_validator_sha256" in e for e in module.check_provenance(run, "flat", bad, closure, steps))
    bad_steps = copy.deepcopy(steps)
    bad_steps[2]["exit_code"] = 1
    assert any("calc arguments/exit/timing" in e for e in module.check_provenance(run, "flat", invocation, closure, bad_steps))
    bad_steps = copy.deepcopy(steps)
    bad_steps[2]["gui_state_check_passed"] = False
    bad_steps[2]["gui_state_check_error"] = "GUI process vanished"
    assert any("calc arguments/exit/timing" in e for e in module.check_provenance(run, "flat", invocation, closure, bad_steps))
    bad = copy.deepcopy(invocation)
    bad["host_name"] = 47003
    assert any("SSH session provenance differs" in e for e in module.check_provenance(run, "flat", bad, closure, steps))
    (run / "invocation.json").write_text(json.dumps({**invocation, "created_utc": "2026-09-29T00:00:01Z"}), encoding="utf-8")
    assert any("raw closure identity/file set differs" in e for e in module.check_provenance(run, "flat", invocation, closure, steps))
    (run / "invocation.json").write_text(json.dumps(invocation), encoding="utf-8")
    (run / "model.log").write_text("tampered", encoding="utf-8")
    assert any("raw closure mismatch: model.log" in e for e in module.check_provenance(run, "flat", invocation, closure, steps))


def test_provenance_rejects_gui_session_mismatch(tmp_path: Path) -> None:
    run, invocation, closure, steps = provenance(tmp_path)
    invocation["allow_existing_gui"] = True
    invocation["coexisting_gui"] = {"pid": 123, "session_id": 2, "session_query_line": "RDP-Tcp#4 user 2 Active",
                                    "process_start_utc": "2026-09-29T00:00:00Z"}
    assert any("did not preserve GUI" in e for e in module.check_provenance(run, "flat", invocation, closure, steps))
    invocation["coexisting_gui"]["session_query_line"] = "RDP-Tcp#4 user 3 Active"
    assert any("PID/session evidence" in e for e in module.check_provenance(run, "flat", invocation, closure, steps))


def test_provenance_accepts_preserved_single_gui(tmp_path: Path) -> None:
    run, invocation, closure, steps = provenance(tmp_path)
    invocation["allow_existing_gui"] = True
    invocation["coexisting_gui"] = {
        "pid": 13340,
        "session_id": 1,
        "session_query_line": "RDP-Tcp#37 user 1 Active",
        "process_start_utc": "2026-09-28T10:09:56.8261381Z",
    }
    (run / "invocation.json").write_text(json.dumps(invocation), encoding="utf-8")
    closure["invocation_sha256"] = module.sha256(run / "invocation.json")
    for step in steps:
        step["coexisting_gui_present_after"] = True
    assert module.check_provenance(run, "flat", invocation, closure, steps) == []


def test_read_only_full_validation_rejects_changed_native_wave_after_resealing(tmp_path: Path) -> None:
    run, invocation, closure, steps = provenance(tmp_path)
    (run / "input.json").write_bytes((CASE / "native-flat.json").read_bytes())
    (run / "roundtrip-raw.json").write_bytes((CASE / "native-flat.json").read_bytes())
    (run / "steps.json").write_text(json.dumps(steps), encoding="utf-8")
    (run / "run.log").write_text(
        "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0\n"
        "(warning #108) expected\n(warning #126) expected\n", encoding="utf-8")
    lines = [f"Time: {event['time_hours_printed']} {event['body']}"
             for event in make_events()]
    (run / "model.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
    report = make_report()
    source = json.loads((run / "input.json").read_text(encoding="utf-8"))
    report["report"]["tables"].append(
        next(table for table in source["model"]["tables"] if table["name"] == "ProblemDescription"))
    (run / "report-raw.json").write_text(json.dumps(report), encoding="utf-8")
    (run / "invocation.json").write_text(json.dumps(invocation), encoding="utf-8")

    def seal() -> None:
        closure["invocation_sha256"] = module.sha256(run / "invocation.json")
        closure["raw"] = {name: {"bytes": (run / name).stat().st_size,
                                 "sha256": module.sha256(run / name)} for name in module.RAW_NAMES}
        (run / "closure.json").write_text(json.dumps(closure), encoding="utf-8")

    seal()
    assert module.validate(run, "flat")["passed"]
    assert not (run / "validation.json").exists()  # validator is read-only
    (run / "model.log").write_text((run / "model.log").read_text().replace(
        "Time: 44 <BASIC-MISSION", "Time: 45 <BASIC-MISSION", 1), encoding="utf-8")
    seal()
    result = module.validate(run, "flat")
    assert not result["passed"]
    assert any("start wave times/count" in difference for difference in result["differences"])
