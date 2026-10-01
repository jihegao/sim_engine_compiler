"""Freeze reviewed G04 source and accepted/diagnostic raw identities."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNS = {arm: HERE / "runs" / f"g04-{arm}-v101-ssh-20261002-01" for arm in ("series", "parallel")}
OLD = ROOT / "G04-series-active-parallel-v1.0.0/runs/g04-series-v100-ssh-20261002-01"
PARENT = ROOT / "G02-var01-position-modes-v1.0.0/runs/g02-var01-two-position-accepted-20261001-01"


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
    assert [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"]
    assert all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps)
    assert load(run / "roundtrip-validation.json")["passed"]
    assert closure["source_hashes_before"]["input"] == sha(HERE / f"{arm}-input.json")
    return {"run_id": run.name, "local_path": str(run.resolve()),
            "input_sha256": sha(run / "input.json"), "invocation_sha256": sha(run / "invocation.json"),
            "closure_sha256": sha(run / "closure.json"), "model_log_sha256": sha(run / "model.log"),
            "report_sha256": sha(run / "report-raw.json"), "raw": closure["raw"]}


def main() -> None:
    author = load(HERE / "author-validation.json")
    assert author["passed"] and author["checks"] == 47 and not author["differences"]
    reviews = sorted((HERE / "review").glob("independent*.json"))
    assert len(reviews) == 1, "one separate read-only review required"
    review = load(reviews[0])
    verdict = str(review.get("verdict", review.get("decision", ""))).upper()
    assert verdict == "GO" and review["passed"] is True and review["check_count"] == 3248
    assert not review["failures"], "independent GO required"
    diagnostic = load(HERE / "diagnostic-predecessor.json")
    old_closure = load(OLD / "closure.json")
    assert diagnostic["publication_state"] == "excluded_diagnostic"
    assert sha(OLD / "input.json") == sha(HERE / "diagnostic-v100-series-input.json") == diagnostic["input_sha256"]
    assert sha(OLD / "closure.json") == diagnostic["closure_sha256"]
    assert len(old_closure["raw"]) == 8
    assert all((OLD / name).stat().st_size == seal["bytes"] and sha(OLD / name) == seal["sha256"]
               for name, seal in old_closure["raw"].items())
    files = sorted(path for path in HERE.rglob("*") if path.is_file() and
                   "runs" not in path.relative_to(HERE).parts and
                   "__pycache__" not in path.relative_to(HERE).parts and
                   path.name != "evidence-index.json")
    index = {"schema": "simlox-g04-series-active-parallel-v101-evidence-index/v1",
             "case_id": "G04", "variant_ids": ["G04.var01", "G04.var02"], "version": "1.0.1",
             "scope": "one fixed-seed two-position explicit series versus active one-of-two parallel RBD pair",
             "source_files_sha256": {p.relative_to(HERE).as_posix(): sha(p) for p in files},
             "accepted_runs": {arm: run_index(arm, run) for arm, run in RUNS.items()},
             "accepted_direct_parent": {"run_id": PARENT.name, "closure_sha256": sha(PARENT / "closure.json"),
                                        "model_log_sha256": sha(PARENT / "model.log"),
                                        "report_sha256": sha(PARENT / "report-raw.json")},
             "excluded_diagnostic": {"run_id": OLD.name, "local_path": str(OLD.resolve()),
                                     "input_sha256": sha(OLD / "input.json"),
                                     "closure_sha256": sha(OLD / "closure.json"),
                                     "raw": old_closure["raw"]},
             "author_validation_sha256": sha(HERE / "author-validation.json"),
             "independent_review_sha256": sha(reviews[0])}
    raw = (json.dumps(index, indent=2) + "\n").encode("utf-8")
    output = HERE / "evidence-index.json"
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("frozen evidence index differs")
    if not output.exists():
        output.write_bytes(raw)
    print(json.dumps({"index_sha256": sha(output), "accepted_raw_seals": 24,
                      "excluded_diagnostic_raw_seals": 8,
                      "independent_review_sha256": sha(reviews[0])}))


if __name__ == "__main__":
    main()
