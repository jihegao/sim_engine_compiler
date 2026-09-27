from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from sim_engine_compiler.review import export_review
from sim_engine_compiler.review.__main__ import main

FIXTURES = Path(__file__).parents[1] / "fixtures/identity_contract/b1"


def test_offline_cli_complete_bundle_returns_verified_partial_json(capsys):
    arguments = ["export", str(FIXTURES / "core.json")]
    for layer in ("business", "core", "plan", "lineage"):
        arguments += [f"--{layer}", str(FIXTURES / f"{layer}.json")]
    assert main(arguments) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["association_status"] == "verified"
    assert report["status"] == "partial"
    assert report["mappings"]["core_to_plan"]


def test_module_cli_runs_offline_without_modifying_persisted_input():
    path = FIXTURES / "business.json"
    before = path.read_bytes()
    completed = subprocess.run([sys.executable, "-m", "sim_engine_compiler.review", "export", str(path),
                                "--view", "resources"], capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert set(report["views"]) == {"resources"}
    assert report["association_status"] == "unverified"
    assert path.read_bytes() == before


@pytest.mark.parametrize("text", ['{"version":0,"version":1}', '{', '[]', '{"x":NaN}', '[' * 2000])
def test_cli_malformed_or_unsupported_input_returns_json_error(tmp_path, capsys, text):
    path = tmp_path / "input.json"
    path.write_text(text)
    assert main(["export", str(path)]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["status"] in {"invalid", "unsupported"}
    assert report["views"] == {}
    assert report["diagnostics"]


def test_cli_missing_file_does_not_crash(tmp_path, capsys):
    assert main(["export", str(tmp_path / "absent")]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["diagnostics"][0]["stage"] == "load"
    assert set(report) == set(export_review({}))
    assert len(report["export_fingerprint"]) == 64
