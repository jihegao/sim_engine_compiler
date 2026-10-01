"""Seal the accepted overlap pair and the excluded four-hour diagnostic."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DIAGNOSTIC = ROOT / "G05-overlapping-switches-v1.0.0"
PARENT = ROOT / "G05-passive-threshold-v1.0.0"
REVIEW = HERE / "review/independent-readonly-2026-10-02.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run_index(package: Path, arm: str, version: str) -> dict:
    run = package / "runs" / f"g05-overlap-{arm}-{version}-ssh-20261002-01"
    invocation, closure, steps = (load(run / name) for name in
                                  ("invocation.json", "closure.json", "steps.json"))
    assert invocation["arm"] == arm
    assert invocation["run_id"] == closure["run_id"] == run.name
    assert closure["invocation_sha256"] == sha(run / "invocation.json")
    assert closure["error"] is None
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert closure["source_hashes_before"]["input"] == sha(package / f"{arm}-input.json")
    assert closure["source_hashes_before"]["parent"] == sha(PARENT / "two-input.json")
    assert len(closure["raw"]) == 12
    assert all((run / name).stat().st_size == seal["bytes"] and
               sha(run / name) == seal["sha256"]
               for name, seal in closure["raw"].items())
    assert [step["name"] for step in steps] == [
        "import", "export", "calc", "jsonreport", "check_import_export"]
    assert all(step["status"] == "completed" and step["exit_code"] == 0 and
               step["gui_preserved"] for step in steps)
    assert load(run / "roundtrip-validation.json")["passed"]
    return {"run_id": run.name, "local_path": str(run.resolve()),
            "input_sha256": sha(run / "input.json"),
            "invocation_sha256": sha(run / "invocation.json"),
            "closure_sha256": sha(run / "closure.json"),
            "model_log_sha256": sha(run / "model.log"),
            "report_sha256": sha(run / "report-raw.json"),
            "raw": closure["raw"]}


def source_files(package: Path) -> dict:
    files = sorted(path for path in package.rglob("*") if path.is_file() and
                   "runs" not in path.relative_to(package).parts and
                   "__pycache__" not in path.relative_to(package).parts and
                   path.name != "evidence-index.json")
    return {path.relative_to(package).as_posix(): sha(path) for path in files}


def main() -> None:
    author, review, diagnostic = (load(path) for path in (
        HERE / "author-validation.json", REVIEW,
        DIAGNOSTIC / "diagnostic-result.json"))
    assert author["passed"] and author["checks"] == 51 and not author["differences"]
    assert review["passed"] and review["verdict"] == "GO"
    assert review["checks_passed"] == review["checks_total"] == 3453
    assert not review["failures"]
    assert diagnostic["publication_state"] == "not_published"
    assert diagnostic["reason"] == "No overlapping native switch intervals in either arm"
    accepted = {arm: run_index(HERE, arm, "v101") for arm in ("short", "long")}
    excluded = {arm: run_index(DIAGNOSTIC, arm, "v100") for arm in ("short", "long")}
    for arm in ("short", "long"):
        for key in ("input_sha256", "closure_sha256", "model_log_sha256", "report_sha256"):
            assert excluded[arm][key] == diagnostic["arms"][arm][key]
    parent_run = PARENT / "runs/g05-nbreq-two-v100-ssh-20261002-01"
    index = {
        "schema": "simlox-g05-overlapping-switches-v101-evidence-index/v1",
        "case_id": "G05", "variant_ids": ["G05.var05"], "version": "1.0.1",
        "scope": "one fixed-seed four-branch passive short/long pair with two overlapping nine-hour activation intervals",
        "source_files_sha256": {HERE.name: source_files(HERE),
                                DIAGNOSTIC.name: source_files(DIAGNOSTIC)},
        "accepted_runs": accepted,
        "excluded_diagnostic_runs": excluded,
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
    print(json.dumps({"index_sha256": sha(output), "accepted_raw_seals": 24,
                      "excluded_diagnostic_raw_seals": 24,
                      "independent_review_sha256": sha(REVIEW)}))


if __name__ == "__main__":
    main()
