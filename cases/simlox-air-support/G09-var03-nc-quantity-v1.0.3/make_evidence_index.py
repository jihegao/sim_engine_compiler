"""Seal the accepted two-copy QTYNC pair and excluded PAR diagnostic."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIAG = HERE.parent / "G09-var03-nc-quantity-v1.0.2"
ARMS = ("qty1", "qty2")
SOURCE = ("build.py", "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1",
          "validate_native.py", "make_evidence_index.py", "contract.json", "exact-diff.json",
          "qty1-input.json", "qty2-input.json", "author-validation.json",
          "review/independent_review.py", "review/verdict.json", "README.md",
          "cli-scope-signoff-2026-10-03.md")


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def seal(path: Path) -> dict:
    return {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main() -> None:
    contract = read(HERE / "contract.json")
    author = read(HERE / "author-validation.json")
    independent = read(HERE / "review/verdict.json")
    diagnostic = read(DIAG / "diagnostic-evidence.json")
    if not author["passed"] or not independent["passed"] or diagnostic["publication_state"] != "excluded_diagnostic":
        raise ValueError("acceptance or diagnostic state invalid")
    for arm in ARMS:
        if diagnostic["runs"][arm]["closure"]["sha256"] != contract["excluded_diagnostic"]["native_closure_sha256"][arm]:
            raise ValueError(f"diagnostic provenance changed: {arm}")
    runs = {}
    for arm in ARMS:
        run = HERE / "runs" / f"g09-var03-{arm}-v103-ssh-20261003-01"
        closure = read(run / "closure.json")
        if closure["native_outcome"] != "zero_error_reviewed_warnings" or len(closure["raw"]) != 13:
            raise ValueError(f"native closure invalid: {arm}")
        raw = {name: seal(run / name) for name in sorted(closure["raw"])}
        if raw != {name: closure["raw"][name] for name in sorted(closure["raw"])}:
            raise ValueError(f"raw seals changed: {arm}")
        runs[arm] = {"run_id": run.name, "local_directory": str(run),
                     "invocation": seal(run / "invocation.json"), "closure": seal(run / "closure.json"), "raw": raw}
    result = {"schema": "simlox-g09-var03-quantity-evidence-index/v1", "case_id": "G09",
              "variant_id": "G09.var03", "version": "1.0.3", "publication_state": "not_published",
              "source": {name: seal(HERE / name) for name in SOURCE},
              "accepted_parent": contract["accepted_parent"], "accepted_control": contract["accepted_control"],
              "excluded_diagnostic": {"contract": contract["excluded_diagnostic"],
                 "evidence": seal(DIAG / "diagnostic-evidence.json")},
              "manual_sha256": contract["source"]["manual_sha256"],
              "dictionary_sha256": contract["source"]["dictionary_sha256"],
              "runs": runs,
              "author_validation": {"passed": True, "checks": author["passed_count"]},
              "independent_validation": {"passed": True, "checks": independent["checks_passed"]},
              "scope": "two installed POS-B copies, selected BASIC NCID QTYNC1 versus2; second h20 B critical/abort versus noncritical/success; excluded PAR diagnostic"}
    (HERE / "evidence-index.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"accepted_raw": sum(len(r["raw"]) for r in runs.values()),
                      "excluded_raw": sum(len(r["raw"]) for r in diagnostic["runs"].values()),
                      "author_checks": author["passed_count"], "independent_checks": independent["checks_passed"]}))


if __name__ == "__main__":
    main()
