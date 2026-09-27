"""Persisted, read-only CLI acceptance; no runtime in the query command."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from sim_engine_compiler.ir.plan import ExecutionPlan
from sim_engine_compiler.reference import SimpyReferenceRuntime
from sim_engine_compiler.trace_query import query_trace

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def inputs(tmp_path):
    fixture = ROOT / "tests/fixtures/identity_contract/b1"
    plan = json.loads((fixture / "plan.json").read_text())
    result = SimpyReferenceRuntime(ExecutionPlan.from_dict(plan), seed=7).run()
    request = {"run_id": "persisted", "sample_index": 0, "seed": 7,
               "backend": "python-reference"}
    bundle = {name: json.loads((fixture / f"{name}.json").read_text())
              for name in ("business", "core", "plan", "lineage")}
    objects = {"plan": plan, "result": result, "request": request, "bundle": bundle,
               "query": {"limit": 2}}
    paths = {}
    for name, value in objects.items():
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        paths[name] = path
    return paths, objects


def invoke(paths, *extra):
    return subprocess.run(
        [sys.executable, "-m", "sim_engine_compiler.trace_query", str(paths["result"]),
         "--request", str(paths["request"]), "--plan", str(paths["plan"]), *extra],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )


def hashes(paths):
    return {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()}


def test_cli_api_agree_and_leave_all_input_files_unchanged(inputs):
    paths, objects = inputs
    before = hashes(paths)
    run = invoke(paths, "--query", str(paths["query"]), "--bundle", str(paths["bundle"]))
    expected = query_trace(objects["result"], objects["request"], objects["plan"],
                           query=objects["query"], bundle=objects["bundle"])
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout) == expected
    assert hashes(paths) == before
    assert expected["coverage"]["selected_event_count"] == 2


@pytest.mark.parametrize("field", ["result", "request", "plan", "query", "bundle"])
def test_duplicate_json_keys_rejected_for_every_input(inputs, field):
    paths, _ = inputs
    paths[field].write_text('{"a":1,"a":2}', encoding="utf-8")
    before = hashes(paths)
    run = invoke(paths, "--query", str(paths["query"]), "--bundle", str(paths["bundle"]))
    report = json.loads(run.stdout)
    assert run.returncode == 2
    assert report["schema_version"] == "simulation-trace-query/v1"
    assert report["status"] == "invalid"
    assert "duplicate" in report["diagnostics"][0]["message"]
    assert hashes(paths) == before


def test_missing_file_produces_same_machine_envelope(inputs, tmp_path):
    paths, _ = inputs
    run = invoke(paths, "--bundle", str(tmp_path / "missing.json"))
    report = json.loads(run.stdout)
    assert run.returncode == 2
    assert report["status"] == "invalid"
    assert report["events"] == []
    assert report["diagnostics"][0]["code"] == "trace_query_input_read_error"


def test_unsupported_backend_fails_without_changing_inputs(inputs):
    paths, objects = inputs
    request = {**objects["request"], "backend": "rust"}
    paths["request"].write_text(json.dumps(request), encoding="utf-8")
    before = hashes(paths)
    run = invoke(paths)
    report = json.loads(run.stdout)
    assert run.returncode == 2
    assert report["status"] == "unsupported"
    assert report["events"] == []
    assert hashes(paths) == before


def test_empty_budget_emits_no_events_but_reports_omission(inputs):
    paths, _ = inputs
    paths["query"].write_text('{"max_event_bytes":2}', encoding="utf-8")
    run = invoke(paths, "--query", str(paths["query"]))
    report = json.loads(run.stdout)
    assert run.returncode == 0
    assert report["events"] == []
    assert report["coverage"]["budget_exhausted"] is True
    assert report["budget"]["used_event_bytes"] == 2
