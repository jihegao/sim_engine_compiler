"""A03 description revision and frozen native-evidence boundaries."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path, PureWindowsPath


ROOT = Path(__file__).resolve().parents[2] / "cases/simlox-air-support"
PREVIOUS = ROOT / "A03-two-aircraft-formation"
CANDIDATE = ROOT / "A03-two-aircraft-formation-v1.0.1"
OLD_HASHES = {
    "native-input.json": "51e3f99ecf86e05e35dce2b2c9e062b483a2c0f3dd64625761bc64c45900cce6",
    "contract.json": "d68caffff890fd9956e7c1a6eb317f8ee74612512730074381e3a58c39a81cf8",
    "validate.py": "3ea24b22d7e76f621648f2de1e968dae1beee257be739f8b8de7191494704759",
    "validate_strict.py": "146e048235476044d557f5f6e11d16ab7f0e7d36ac90cdc0eb97ccea1eaacd65",
    "run_native_ssh.ps1": "f949098e38cdb833974d40e71d16e241988b074a3200bcf5cd513c8df09c6090",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name: str):
    spec = importlib.util.spec_from_file_location(f"simlox_a03_v101_{name}", CANDIDATE / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_revision_changes_only_description_and_keeps_frozen_sources() -> None:
    builder = load("build")
    assert {name: sha256(PREVIOUS / name) for name in OLD_HASHES} == OLD_HASHES
    old_raw = (PREVIOUS / "native-input.json").read_bytes()
    new_raw = (CANDIDATE / "native-input.json").read_bytes()
    assert builder.build() == new_raw
    assert new_raw == old_raw.replace(
        builder.OLD_DESCRIPTION.encode(), builder.NEW_DESCRIPTION.encode(), 1
    )
    assert sha256(CANDIDATE / "native-input.json") == "d7aa35c11a1426de1e74167cc6a3277879f4a2a5814792274490a43dcfe986a4"

    a02 = json.loads(builder.A02.read_bytes())
    previous = json.loads(old_raw)
    candidate = json.loads(new_raw)
    parent_diff = json.loads((CANDIDATE / "parent-diff.json").read_text())
    revision_diff = json.loads((CANDIDATE / "revision-diff.json").read_text())
    assert sorted(builder.changed_tables(previous, candidate)) == ["ProblemDescription"]
    assert sorted(builder.changed_tables(a02, candidate)) == [
        "MissionType", "OperationProfile", "ProblemDescription", "SystemDeployment"
    ]
    assert sorted(parent_diff["changed_tables"]) == sorted(builder.changed_tables(a02, candidate))
    assert sorted(revision_diff["changed_tables"]) == ["ProblemDescription"]
    assert parent_diff["parent_input_sha256"] == builder.A02_SHA256
    assert revision_diff["previous_input_sha256"] == builder.PREVIOUS_SHA256


def test_versioned_contract_and_description_check_reject_each_wrong_artifact() -> None:
    validator = load("validate")
    contract = validator.CONTRACT
    assert contract["version"] == "1.0.1-candidate"
    assert contract["parent_case"] == "A02@1.0.0"
    assert contract["supersedes"]["input_sha256"] == OLD_HASHES["native-input.json"]
    assert contract["input_sha256"] == sha256(CANDIDATE / "native-input.json")
    assert contract["expected_native"]["problem_description"] == load("build").NEW_DESCRIPTION
    source = json.loads((CANDIDATE / "native-input.json").read_text())
    report = {"report": {"tables": [table for table in source["model"]["tables"]
                                     if table["name"] == "ProblemDescription"]}}
    assert validator.check_description(source, source, report) == []
    for label, changed in (
        ("source", {"model": {"tables": json.loads((PREVIOUS / "native-input.json").read_text())["model"]["tables"]}}),
        ("roundtrip", {"model": {"tables": json.loads((PREVIOUS / "native-input.json").read_text())["model"]["tables"]}}),
        ("report", {"report": {"tables": [{**report["report"]["tables"][0],
                                            "instances": [{"instance_name": "", "rows": [["wrong description"]]}]}]}}),
    ):
        docs = {"source": source, "roundtrip": source, "report": report}
        docs[label] = changed
        assert any(error.startswith(f"{label} ProblemDescription.PDESC:")
                   for error in validator.check_description(**docs))


def test_strict_validator_binds_version_local_runner_and_case_version() -> None:
    strict = load("validate_strict")
    assert strict.original.HERE == CANDIDATE
    assert strict.original.EXPECTED_INPUT_SHA256 == sha256(CANDIDATE / "native-input.json")
    invocation = {
        "schema": "simlox-a03-invocation/ssh-cli-v1",
        "execution_mode": "ssh_cli_v1",
        "case_version": "1.0.1-candidate",
        "runner_sha256": strict.sha256(CANDIDATE / "run_native_ssh.ps1"),
        "run_id": "a03-v101-test",
        "original_run_dir": r"C:\native\a03-v101\a03-v101-test",
        "host_name": "4700-3",
        "created_utc": "2026-09-29T00:00:00Z",
        "session_name": None,
        "session_id": 0,
        "ssh_connection_present": True,
        "ssh_client_present": True,
        "ssh_ancestor_names": ["sshd.exe"],
        "allow_existing_gui": False,
        "coexisting_gui": None,
        "queue_mutex": r"Global\SimloxIssue18NativeQueue",
    }
    run_dir = Path("/copy/a03-v101-test")
    steps = [
        {"name": name, "arguments": arguments, "exit_code": 0, "wall_seconds": 0.1,
         "started_utc": f"2026-09-29T00:0{index}:00Z",
         "completed_utc": f"2026-09-29T00:0{index}:01Z"}
        for index, (name, arguments) in enumerate(
            strict.expected_arguments(PureWindowsPath(invocation["original_run_dir"])).items(), 1
        )
    ]
    assert strict.check_invocation(invocation, steps, run_dir) == []
    assert strict.check_invocation({**invocation, "case_version": "1.0.0-candidate"}, steps, run_dir)
    assert strict.check_invocation({**invocation, "execution_mode": "interactive_v1"}, steps, run_dir) == [
        "unsupported A03 execution mode: 'interactive_v1'"
    ]
