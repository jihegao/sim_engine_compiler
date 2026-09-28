"""A03 parent boundary and two-aircraft event acceptance."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path, PureWindowsPath

BASE = Path(__file__).resolve().parents[2] / "cases/simlox-air-support/A03-two-aircraft-formation"


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, BASE / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a03_is_exactly_one_wave_two_aircraft_delta() -> None:
    builder = load("build")
    parent = json.loads(builder.PARENT.read_text(encoding="utf-8"))
    child = builder.build()
    assert builder.sha256(builder.PARENT) == builder.PARENT_SHA256
    assert sorted(builder.changed_tables(parent, child)) == ["MissionType", "OperationProfile", "SystemDeployment"]
    assert [row["STIM"] for row in builder.rows(child, "OperationProfile")] == [8.0]
    assert [(row["NOS"], row["MNOS"]) for row in builder.rows(child, "MissionType")] == [(2, 2)]
    assert [row["QTYPS"] for row in builder.rows(child, "SystemDeployment")] == [2]
    assert (BASE / "native-input.json").read_bytes() == (json.dumps(child, ensure_ascii=False, indent=2) + "\n").encode()


def test_a03_rejects_single_aircraft_and_split_mission() -> None:
    validator = load("validate")
    tag = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    lines = [
        "Time: 7 <TEACH-UNIT> mission ordered: BASIC-MISSION",
        f"Time: 7 {tag} mission created: ",
        f"Time: 7 {tag} mission activated, systems requested: 2",
        f"Time: 7 {tag} mission allocates system: <TEACH-AIR-01,0>",
        f"Time: 7 {tag} mission allocates system: <TEACH-AIR-01,1>",
        f"Time: 8 {tag} mission starting, duration: 2 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>",
        f"Time: 10 {tag} mission success: ",
        f"Time: 10 {tag} mission completed: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>",
    ]
    assert validator.check_events("\n".join(lines)) == []
    assert validator.check_events("\n".join(lines).replace(",<TEACH-AIR-01,1>", ""))
    assert validator.check_events("\n".join(lines).replace(tag, "<BASIC-MISSION,TEACH-UNIT,0,0,1>", 1))


def test_a03_strict_summary_rejects_false_wave_and_result_window() -> None:
    strict = load("validate_strict")
    fields = ("NREP", "RTILW", "RTIUP", "MSTF", "MSUF")

    def report(values: tuple[int, ...]) -> dict:
        return {"report": {"tables": [{
            "name": "ResultSummary",
            "columns": [{"name": field} for field in fields],
            "instances": [{"rows": [list(values)]}],
        }]}}

    good = (1, 0, 36, 1, 1)
    assert strict.check_summary(report(good)) == []
    for field, index, wrong in (("RTILW", 1, 1), ("RTIUP", 2, 999),
                                ("MSTF", 3, 99), ("MSUF", 4, 0)):
        bad = list(good)
        bad[index] = wrong
        assert any(field in error for error in strict.check_summary(report(tuple(bad))))


def test_a03_strict_invocation_requires_active_session_and_complete_native_steps() -> None:
    strict = load("validate_strict")
    invocation = {
        "runner_sha256": strict.sha256(BASE / "run_native.ps1"),
        "run_id": "run-001",
        "original_run_dir": r"C:\native\a03\run-001",
        "session_name": "rdp-tcp#35",
        "session_id": 1,
        "session_user": "user",
        "session_query_line": ">rdp-tcp#35 user 1 Active",
    }
    run_dir = Path("/review/copy/run-001")
    steps = [{"name": name, "arguments": arguments, "exit_code": 0, "wall_seconds": 0.1}
             for name, arguments in strict.expected_arguments(PureWindowsPath(invocation["original_run_dir"])).items()]
    assert strict.check_invocation(invocation, steps, run_dir) == []
    assert strict.check_invocation(invocation, steps, Path("/another/replay/run-001")) == []
    assert strict.check_invocation({**invocation, "original_run_dir": r"C:\native\a03\other"}, steps, run_dir)
    assert strict.check_invocation({**invocation, "session_id": 0}, steps, run_dir)
    assert strict.check_invocation({**invocation, "session_query_line": ">rdp-tcp#35 user 1 Disc"}, steps, run_dir)
    assert strict.check_invocation({**invocation, "runner_sha256": "0" * 64}, steps, run_dir)
    assert strict.check_invocation(invocation, steps[:-1], run_dir)
    assert strict.check_invocation(invocation, [{**steps[0], "exit_code": 1}, *steps[1:]], run_dir)
    assert strict.check_invocation(invocation, [{**steps[0], "arguments": "-calc other.sxi"}, *steps[1:]], run_dir)
    assert strict.check_invocation(invocation, [{**steps[0], "wall_seconds": -1}, *steps[1:]], run_dir)


def test_a03_ssh_invocation_has_separate_provenance_and_ordered_steps() -> None:
    strict = load("validate_strict")
    invocation = {
        "schema": "simlox-a03-invocation/ssh-cli-v1",
        "execution_mode": "ssh_cli_v1",
        "runner_sha256": strict.sha256(BASE / "run_native_ssh.ps1"),
        "run_id": "ssh-run-001",
        "original_run_dir": r"C:\native\a03\ssh-run-001",
        "host_name": "4700-3",
        "created_utc": "2026-09-28T12:00:00Z",
        "session_name": None,
        "session_id": 0,
        "ssh_connection_present": True,
        "ssh_client_present": True,
        "ssh_ancestor_names": ["cmd.exe", "sshd.exe"],
    }
    run_dir = Path("/review/copy/ssh-run-001")
    steps = [
        {"name": name, "arguments": arguments, "exit_code": 0, "wall_seconds": 0.1,
         "started_utc": f"2026-09-28T12:0{index}:00Z",
         "completed_utc": f"2026-09-28T12:0{index}:01Z"}
        for index, (name, arguments) in enumerate(
            strict.expected_arguments(PureWindowsPath(invocation["original_run_dir"])).items(), 1
        )
    ]
    assert strict.check_invocation(invocation, steps, run_dir) == []
    assert strict.check_invocation(invocation, steps, Path("/independent/replay/ssh-run-001")) == []
    for changed in (
        {"execution_mode": "unknown"},
        {"runner_sha256": strict.sha256(BASE / "run_native.ps1")},
        {"ssh_connection_present": False},
        {"ssh_ancestor_names": ["cmd.exe"]},
        {"session_id": 1},
        {"session_name": "rdp-tcp#35"},
        {"host_name": ""},
        {"created_utc": "yesterday"},
    ):
        assert strict.check_invocation({**invocation, **changed}, steps, run_dir)
    assert strict.check_invocation(invocation, [{**steps[0], "completed_utc": "2026-09-28T11:59:00Z"}, *steps[1:]], run_dir)
    assert strict.check_invocation(invocation, [{**steps[0], "arguments": "-calc other.sxi"}, *steps[1:]], run_dir)
