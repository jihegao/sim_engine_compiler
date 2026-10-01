"""Seal G05 source, guarded native runs and independent read-only review."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNS = {arm: HERE / "runs" / f"g05-passive-{arm}-v100-ssh-20261002-01" for arm in ("zero", "half")}
PARENT_RUN = ROOT / "G04-three-branch-threshold-v1.0.0/runs/g04-kn-one-v100-ssh-20261002-01"
REVIEW = HERE / "review/independent-readonly-2026-10-02.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run_index(arm: str, run: Path) -> dict:
    invocation, closure, steps = (load(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
    assert invocation["arm"] == arm and invocation["run_id"] == closure["run_id"] == run.name
    assert closure["invocation_sha256"] == sha(run / "invocation.json") and closure["error"] is None
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert len(closure["raw"]) == 12
    assert all((run / name).stat().st_size == seal["bytes"] and sha(run / name) == seal["sha256"]
               for name, seal in closure["raw"].items())
    assert [step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"]
    assert all(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] for step in steps)
    assert load(run / "roundtrip-validation.json")["passed"]
    assert closure["source_hashes_before"]["input"] == sha(HERE / f"{arm}-input.json")
    return {"run_id": run.name, "local_path": str(run.resolve()),
            "input_sha256": sha(run / "input.json"), "invocation_sha256": sha(run / "invocation.json"),
            "closure_sha256": sha(run / "closure.json"), "model_log_sha256": sha(run / "model.log"),
            "report_sha256": sha(run / "report-raw.json"), "raw": closure["raw"]}


def main() -> None:
    author, review = load(HERE / "author-validation.json"), load(REVIEW)
    assert author["passed"] and author["checks"] == 49 and not author["differences"]
    assert review["passed"] and review["verdict"] == "GO"
    assert not review.get("failures", [])
    files = sorted(path for path in HERE.rglob("*") if path.is_file() and
                   "runs" not in path.relative_to(HERE).parts and
                   "__pycache__" not in path.relative_to(HERE).parts and
                   path.name != "evidence-index.json")
    index = {"schema": "simlox-g05-passive-switchover-v100-evidence-index/v1",
             "case_id": "G05", "variant_ids": ["G05.var01", "G05.var03"], "version": "1.0.0",
             "scope": "one fixed-seed passive B-A-C priority sequence with zero versus half-hour switch",
             "source_files_sha256": {path.relative_to(HERE).as_posix(): sha(path) for path in files},
             "accepted_runs": {arm: run_index(arm, run) for arm, run in RUNS.items()},
             "accepted_direct_parent": {"run_id": PARENT_RUN.name,
                                        "closure_sha256": sha(PARENT_RUN / "closure.json"),
                                        "input_sha256": sha(PARENT_RUN / "input.json")},
             "author_validation_sha256": sha(HERE / "author-validation.json"),
             "independent_review_sha256": sha(REVIEW),
             "independent_reviewer_script_sha256": sha(HERE / "review/independent_readonly.py")}
    raw = (json.dumps(index, indent=2) + "\n").encode()
    output = HERE / "evidence-index.json"
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("frozen evidence index differs")
    if not output.exists():
        output.write_bytes(raw)
    print(json.dumps({"index_sha256": sha(output), "raw_seals": 24,
                      "independent_review_sha256": sha(REVIEW)}))


if __name__ == "__main__":
    main()
