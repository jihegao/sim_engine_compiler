"""Offline command boundary rejects malformed data without touching the runtime."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/identity_contract"


def invoke(*args):
    process = subprocess.run(
        [sys.executable, "-m", "sim_engine_compiler.identity", *map(str, args)],
        cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True, text=True, check=False,
    )
    return process.returncode, json.loads(process.stdout)


@pytest.mark.parametrize("case", ["b1", "f35"])
def test_bundle_cli_loads_persisted_layers(case):
    args = ["bundle"]
    for layer in ("business", "core", "plan", "lineage"):
        args.extend([f"--{layer}", FIXTURES / case / f"{layer}.json"])
    code, report = invoke(*args)
    assert code == 0
    assert report["status"] in ("valid", "partial")
    assert report["schema_version"] == "model-bundle-identity/v1"


@pytest.mark.parametrize("content", ['{"version":1,"version":2}', '{"x":NaN}', '[]'])
def test_invalid_json_or_artifact_is_structured(tmp_path, content):
    path = tmp_path / "invalid.json"
    path.write_text(content)
    code, report = invoke("artifact", path)
    assert code == 2
    assert report["status"] in ("invalid", "unsupported")
    assert report["diagnostics"]


def test_missing_input_is_structured(tmp_path):
    code, report = invoke("artifact", tmp_path / "absent.json")
    assert code == 2
    assert report["diagnostics"][0]["code"] == "input_read_error"
