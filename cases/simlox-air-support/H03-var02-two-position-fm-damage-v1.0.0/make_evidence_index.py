"""Bind accepted H03 two-position-FM sources, reviews and sealed evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "H03-var01-position-fm-damage-v1.0.0"
REVIEW = HERE / "review/independent-readonly-2026-10-02.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run_index(arm: str) -> dict:
    run = HERE / "runs" / f"h03-var02-{arm}-v100-ssh-20261002-01"
    invocation, closure, steps = (load(run / name) for name in
                                  ("invocation.json", "closure.json", "steps.json"))
    assert invocation["variant"] == arm and invocation["run_id"] == closure["run_id"] == run.name
    assert closure["error"] is None and closure["invocation_sha256"] == sha(run / "invocation.json")
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert closure["source_hashes_before"]["input"] == sha(HERE / f"{arm}-input.json")
    assert len(closure["raw"]) == 12 and all(
        (run / name).stat().st_size == seal["bytes"] and sha(run / name) == seal["sha256"]
        for name, seal in closure["raw"].items())
    assert load(run / "roundtrip-validation.json")["passed"]
    assert [step["name"] for step in steps] == [
        "import", "export", "calc", "jsonreport", "check_import_export"]
    assert all(step["status"] == ("calc_observed" if step["name"] == "calc" else "completed") and
               step["exit_code"] == 0 and step["gui_preserved"] for step in steps)
    return {"run_id": run.name, "local_path": str(run.resolve()),
            "input_sha256": sha(run / "input.json"),
            "invocation_sha256": sha(run / "invocation.json"),
            "closure_sha256": sha(run / "closure.json"),
            "model_log_sha256": sha(run / "model.log"),
            "report_sha256": sha(run / "report-raw.json"), "raw": closure["raw"]}


def main() -> None:
    author, review = load(HERE / "author-validation.json"), load(REVIEW)
    assert author["passed"] and author["checks"] == 28 and not author["differences"]
    assert review["passed"] and review["verdict"].startswith("GO:") and not review["failures"]
    assert review["checks_passed"] == review["checks_total"] and review["checks_total"] >= 500
    files = sorted(path for path in HERE.rglob("*") if path.is_file() and
                   "runs" not in path.relative_to(HERE).parts and
                   "__pycache__" not in path.relative_to(HERE).parts and
                   path.name != "evidence-index.json")
    index = {
        "schema": "simlox-h03-var02-two-position-fm-damage-v100-evidence-index/v1",
        "case_id": "H03", "variant_id": "H03.var02", "version": "1.0.0",
        "scope": "two BATTLE-HIT failure modes on one position with concurrent direct CM",
        "raw_publication": "local_sealed_not_committed",
        "source_files_sha256": {path.relative_to(HERE).as_posix(): sha(path) for path in files},
        "accepted_runs": {arm: run_index(arm) for arm in ("control", "two-mode")},
        "accepted_direct_parent": {"package": PARENT.name,
                                   "source_sha256": sha(PARENT / "mode-input.json"),
                                   "publication_signoff_sha256": sha(PARENT / "cli-scope-signoff-2026-10-02.md")},
        "author_validation_sha256": sha(HERE / "author-validation.json"),
        "independent_review_sha256": sha(REVIEW)}
    raw = (json.dumps(index, indent=2) + "\n").encode()
    output = HERE / "evidence-index.json"
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("frozen evidence index differs")
    if not output.exists():
        output.write_bytes(raw)
    print(json.dumps({"index_sha256": sha(output), "accepted_raw_seals": 24,
                      "independent_review_sha256": sha(REVIEW)}))


if __name__ == "__main__":
    main()
