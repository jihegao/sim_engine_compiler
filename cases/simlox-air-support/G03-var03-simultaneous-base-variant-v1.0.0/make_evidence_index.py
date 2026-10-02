"""Seal G03.var03 source, guarded native run and independent review."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN_ID = "g03-var03-simultaneous-v100-ssh-20261003-01"


def seal(path: Path) -> dict:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def main() -> None:
    names = ("build.py", "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1",
             "validate_native.py", "contract.json", "exact-diff.json", "native-input.json",
             "author-validation.json", "review/independent_replay.py",
             "review/independent-validation-2026-10-03.json")
    source = {name: seal(HERE / name) for name in names}
    run = HERE / "runs" / RUN_ID
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    author = json.loads((HERE / "author-validation.json").read_text(encoding="utf-8"))
    review = json.loads((HERE / "review/independent-validation-2026-10-03.json").read_text(encoding="utf-8"))
    if not author["passed"] or not review["passed"]:
        raise ValueError("validation failed")
    review_count = review.get("checks_passed", review.get("passed_count"))
    index = {"schema": "simlox-g03-var03-simultaneous-base-variant-evidence-index/v1",
             "case_id": "G03", "variant_id": "G03.var03", "version": "1.0.0",
             "publication_state": "not_published", "source": source,
             "accepted_parent": {"package": "G03-effective-item-contrast-v1.0.0",
                                 "arm": "add-extra",
                                 "input_sha256": closure["source_hashes_before"]["parent"],
                                 "native_closure_sha256": closure["source_hashes_before"]["parent_closure"]},
             "manual_sha256": closure["source_hashes_before"]["manual"],
             "dictionary_sha256": closure["source_hashes_before"]["dictionary"],
             "run": {"run_id": RUN_ID, "local_directory": str(run),
                     "invocation": seal(run / "invocation.json"),
                     "closure": seal(run / "closure.json"), "raw": closure["raw"]},
             "raw_file_count": len(closure["raw"]),
             "author_validation": {"passed": True, "passed_count": author["passed_count"]},
             "independent_validation": {"passed": True, "passed_count": review_count}}
    (HERE / "evidence-index.json").write_bytes((json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"source_files": len(source), "raw_files": index["raw_file_count"],
                      "author_checks": author["passed_count"], "independent_checks": review_count}))


if __name__ == "__main__":
    main()
