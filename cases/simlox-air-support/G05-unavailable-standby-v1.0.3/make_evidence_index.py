"""Seal the accepted G05 unavailable-standby trace and excluded #335 diagnostic."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EXCLUDED = ROOT / "G05-unavailable-standby-v1.0.2"
PARENT = ROOT / "G05-passive-switchover-v1.0.0"
RUN = HERE / "runs/g05-unavailable-v103-ssh-20261002-01"
EXCLUDED_RUN = EXCLUDED / "runs/g05-unavailable-v102-ssh-20261002-01"
REVIEW = HERE / "review/independent-readonly-2026-10-02.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run_index(run: Path, package: Path, accepted: bool) -> dict:
    invocation, closure, steps = (load(run / name) for name in
                                  ("invocation.json", "closure.json", "steps.json"))
    assert invocation["run_id"] == closure["run_id"] == run.name
    assert invocation["arm"] == "unavailable"
    assert closure["invocation_sha256"] == sha(run / "invocation.json")
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert closure["source_hashes_before"]["input"] == sha(package / "unavailable-input.json")
    assert closure["source_hashes_before"]["parent"] == sha(PARENT / "half-input.json")
    assert all((run / name).stat().st_size == seal["bytes"] and
               sha(run / name) == seal["sha256"]
               for name, seal in closure["raw"].items())
    expected_steps = ["import", "export", "calc", "jsonreport", "check_import_export"]
    if accepted:
        assert closure["error"] is None and len(closure["raw"]) == 12
        assert [step["name"] for step in steps] == expected_steps
        assert all(step["status"] == "completed" and step["exit_code"] == 0 and
                   step["gui_preserved"] for step in steps)
        assert load(run / "roundtrip-validation.json")["passed"]
    else:
        assert closure["error"] == "calc output model.sxo absent/empty"
        assert len(closure["raw"]) == 8
        assert [step["name"] for step in steps] == expected_steps[:3]
        assert all(step["gui_preserved"] for step in steps)
        assert steps[-1]["status"] == "failed"
        assert "(error #335) Out and return time fractions" in (
            run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    result = {"run_id": run.name, "local_path": str(run.resolve()),
              "input_sha256": sha(run / "input.json"),
              "invocation_sha256": sha(run / "invocation.json"),
              "closure_sha256": sha(run / "closure.json"), "raw": closure["raw"]}
    if accepted:
        result.update(model_log_sha256=sha(run / "model.log"),
                      report_sha256=sha(run / "report-raw.json"))
    else:
        result.update(converter_log_sha256=sha(run / "run.log"),
                      model_stub_sha256=sha(run / "model.sxo"))
    return result


def source_files(package: Path) -> dict:
    files = sorted(path for path in package.rglob("*") if path.is_file() and
                   "runs" not in path.relative_to(package).parts and
                   "__pycache__" not in path.relative_to(package).parts and
                   path.name != "evidence-index.json")
    return {path.relative_to(package).as_posix(): sha(path) for path in files}


def main() -> None:
    author, review = load(HERE / "author-validation.json"), load(REVIEW)
    assert author["passed"] and author["checks"] == 23 and not author["differences"]
    assert review["passed"] and review["verdict"] == "GO"
    assert review["checks_passed"] == review["checks_total"] == 1584
    assert not review["failures"]
    parent_run = PARENT / "runs/g05-passive-half-v100-ssh-20261002-01"
    index = {
        "schema": "simlox-g05-unavailable-standby-v103-evidence-index/v1",
        "case_id": "G05", "variant_ids": ["G05.var04"], "version": "1.0.3",
        "scope": "one continuous mission where B long online CM remains open at A failure and passive C is selected",
        "source_files_sha256": {HERE.name: source_files(HERE),
                                EXCLUDED.name: source_files(EXCLUDED)},
        "accepted_run": run_index(RUN, HERE, True),
        "excluded_335_diagnostic_run": run_index(EXCLUDED_RUN, EXCLUDED, False),
        "accepted_direct_parent": {
            "run_id": parent_run.name,
            "closure_sha256": sha(parent_run / "closure.json"),
            "input_sha256": sha(parent_run / "input.json")},
        "author_validation_sha256": sha(HERE / "author-validation.json"),
        "independent_review_sha256": sha(REVIEW),
        "independent_reviewer_script_sha256": sha(HERE / "review/independent_readonly.py")}
    raw = (json.dumps(index, indent=2) + "\n").encode()
    output = HERE / "evidence-index.json"
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("frozen evidence index differs")
    if not output.exists():
        output.write_bytes(raw)
    print(json.dumps({"index_sha256": sha(output), "accepted_raw_seals": 12,
                      "excluded_diagnostic_raw_seals": 8,
                      "independent_review_sha256": sha(REVIEW)}))


if __name__ == "__main__":
    main()
