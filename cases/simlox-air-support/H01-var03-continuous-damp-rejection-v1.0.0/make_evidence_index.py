"""Seal the H01.var03 source, control, rejection and independent verdict."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A05-continuous-baseline-v1.0.1"
RUNS = {
    "control": HERE / "runs/h01-var03-control-v100-ssh-20261002-01",
    "damp": HERE / "runs/h01-var03-damp-v100-ssh-20261002-01",
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
    if len(raw) != (12 if arm == "control" else 9):
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
        "classification": "valid_continuous_control" if arm == "control" else "DAMP_converter_rejection_252",
        "input_sha256": sha(run / "input.json"),
        "invocation_sha256": sha(run / "invocation.json"),
        "closure_sha256": sha(run / "closure.json"),
        "model_sxo_bytes": (run / "model.sxo").stat().st_size,
        "raw": raw,
    }


def main() -> None:
    author, review = load(HERE / "author-validation.json"), load(REVIEW)
    if not author["passed"] or author["checks_passed"] != author["checks_total"] or author["checks_total"] != 68:
        raise ValueError("author validation failed")
    if not review["passed"] or review["verdict"] != "GO" or review["checks_passed"] != review["checks_total"] or review["checks_total"] != 1815:
        raise ValueError("independent review failed")
    files = sorted(path for path in HERE.rglob("*") if path.is_file() and
                   "runs" not in path.relative_to(HERE).parts and
                   "__pycache__" not in path.relative_to(HERE).parts and
                   path.name != "evidence-index.json")
    result = {
        "schema": "simlox-h01-var03-continuous-damp-rejection-evidence-index/v1",
        "case_id": "H01", "variant_ids": ["H01.var03"], "version": "1.0.0",
        "scope": "one valid continuous control and one exact-source DAMP=1 converter rejection #252",
        "source_files_sha256": {path.relative_to(HERE).as_posix(): sha(path) for path in files},
        "observed_runs": {arm: run_index(arm, run) for arm, run in RUNS.items()},
        "accepted_direct_parent": {
            "package": PARENT.name,
            "source_sha256": sha(PARENT / "native-continuous.json"),
            "publication_signoff_sha256": sha(PARENT / "cli-scope-signoff-2026-09-30.md"),
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
    print(json.dumps({"index_sha256": sha(path), "raw_seals": 21,
                      "author_checks": 68, "independent_checks": 1815}))


if __name__ == "__main__":
    main()
