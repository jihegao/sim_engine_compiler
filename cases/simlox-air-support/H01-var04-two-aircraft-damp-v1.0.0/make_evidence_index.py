"""Seal the H01.var04 sources, two native runs and independent verdict."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A03-two-aircraft-formation-v1.0.1"
RUNS = {
    "control": HERE / "runs/h01-var04-control-v100-ssh-20261002-01",
    "damp": HERE / "runs/h01-var04-damp-v100-ssh-20261002-01",
}
REVIEW = HERE / "review/independent-readonly-2026-10-02.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run_index(arm: str, run: Path) -> dict:
    invocation, closure = load(run / "invocation.json"), load(run / "closure.json")
    if invocation["run_id"] != closure["run_id"] or closure["run_id"] != run.name:
        raise ValueError(f"{arm} run identity differs")
    if closure["invocation_sha256"] != sha(run / "invocation.json"):
        raise ValueError(f"{arm} invocation seal differs")
    if closure["error"] is not None or closure["source_hashes_before"] != closure["source_hashes_after"]:
        raise ValueError(f"{arm} closure/source differs")
    raw = closure["raw"]
    if len(raw) != 12:
        raise ValueError(f"{arm} raw count differs")
    for name, seal in raw.items():
        path = run / name
        if path.stat().st_size != seal["bytes"] or sha(path) != seal["sha256"]:
            raise ValueError(f"{arm} raw seal differs: {name}")
    if not load(run / "roundtrip-validation.json")["passed"]:
        raise ValueError(f"{arm} roundtrip failed")
    return {
        "run_id": run.name,
        "local_path": str(run.resolve()),
        "classification": "valid_A03_control" if arm == "control" else "one_visible_damp_occurrence_per_aircraft",
        "input_sha256": sha(run / "input.json"),
        "invocation_sha256": sha(run / "invocation.json"),
        "closure_sha256": sha(run / "closure.json"),
        "model_log_sha256": sha(run / "model.log"),
        "report_sha256": sha(run / "report-raw.json"),
        "raw": raw,
    }


def main() -> None:
    author, review = load(HERE / "author-validation.json"), load(REVIEW)
    if not author["passed"] or author["checks_passed"] != author["checks_total"] or author["checks_total"] != 89:
        raise ValueError("author validation failed")
    if not review["passed"] or review["verdict"] != "GO" or review["checks_passed"] != review["checks_total"] or review["checks_total"] != 7729:
        raise ValueError("independent review failed")
    files = sorted(path for path in HERE.rglob("*") if path.is_file() and
                   "runs" not in path.relative_to(HERE).parts and
                   "__pycache__" not in path.relative_to(HERE).parts and
                   path.name != "evidence-index.json")
    result = {
        "schema": "simlox-h01-var04-two-aircraft-damp-evidence-index/v1",
        "case_id": "H01", "variant_ids": ["H01.var04"], "version": "1.0.0",
        "scope": "one fixed-seed two-aircraft fixed-mission DAMP=1 no-consequence pair with one visible occurrence per aircraft",
        "source_files_sha256": {path.relative_to(HERE).as_posix(): sha(path) for path in files},
        "accepted_runs": {arm: run_index(arm, run) for arm, run in RUNS.items()},
        "accepted_direct_parent": {
            "package": PARENT.name,
            "source_sha256": sha(PARENT / "native-input.json"),
            "publication_signoff_sha256": sha(PARENT / "cli-scope-signoff-2026-09-29.md"),
        },
        "author_validation_sha256": sha(HERE / "author-validation.json"),
        "independent_review_sha256": sha(REVIEW),
        "independent_reviewer_script_sha256": sha(HERE / "review/independent_readonly.py"),
    }
    raw = (json.dumps(result, indent=2) + "\n").encode()
    path = HERE / "evidence-index.json"
    if path.exists() and path.read_bytes() != raw:
        raise ValueError("frozen evidence index differs")
    if not path.exists():
        path.write_bytes(raw)
    print(json.dumps({"index_sha256": sha(path), "raw_seals": 24,
                      "author_checks": 89, "independent_checks": 7729}))


if __name__ == "__main__":
    main()
