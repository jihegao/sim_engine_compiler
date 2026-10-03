"""Seal accepted G09.var03 pair and its excluded overlap diagnostic."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DIAGNOSTIC = HERE.parent / "G09-var03-noncritical-set-v1.0.0"
ARMS = ("omitted-control", "omitted-nc-b1")
SOURCE = ("build.py", "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1",
          "validate_native.py", "make_evidence_index.py", "contract.json", "exact-diff.json",
          "omitted-control-input.json", "omitted-nc-b1-input.json", "author-validation.json",
          "review/independent_replay.py", "review/independent-validation-2026-10-03.json",
          "README.md", "cli-scope-signoff-2026-10-03.md")


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def seal(path: Path) -> dict:
    return {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main() -> None:
    contract, author, independent = (read(p) for p in
        (HERE / "contract.json", HERE / "author-validation.json",
         HERE / "review/independent-validation-2026-10-03.json"))
    diagnostic = read(DIAGNOSTIC / "diagnostic-evidence.json")
    if not author["passed"] or not independent["passed"] or diagnostic["publication_state"] != "excluded_diagnostic":
        raise ValueError("acceptance and diagnostic states not verified")
    if diagnostic["run"]["closure"]["sha256"] != contract["excluded_diagnostic"]["native_closure_sha256"]:
        raise ValueError("excluded diagnostic provenance changed")
    runs = {}
    for arm in ARMS:
        run = HERE / "runs" / f"g09-var03-{arm}-v101-ssh-20261003-01"
        closure = read(run / "closure.json")
        if closure["native_outcome"] != "zero_error_reviewed_warnings" or len(closure["raw"]) != 13:
            raise ValueError(f"unaccepted native closure: {arm}")
        raw = {name: seal(run / name) for name in sorted(closure["raw"])}
        if raw != {name: closure["raw"][name] for name in sorted(closure["raw"])}:
            raise ValueError(f"raw seal changed: {arm}")
        runs[arm] = {"run_id": run.name, "local_directory": str(run),
                     "invocation": seal(run / "invocation.json"),
                     "closure": seal(run / "closure.json"), "raw": raw}
    result = {"schema": "simlox-g09-var03-evidence-index/v1", "case_id": "G09",
              "variant_id": "G09.var03", "version": "1.0.1", "publication_state": "not_published",
              "source": {name: seal(HERE / name) for name in SOURCE},
              "accepted_parent": contract["accepted_parent"], "series_control": contract["series_control"],
              "excluded_diagnostic": {"contract": contract["excluded_diagnostic"],
                                      "evidence": seal(DIAGNOSTIC / "diagnostic-evidence.json")},
              "manual_sha256": contract["source"]["manual_sha256"],
              "dictionary_sha256": contract["source"]["dictionary_sha256"],
              "runs": runs,
              "author_validation": {"passed": True, "checks": author["passed_count"]},
              "independent_validation": {"passed": True, "checks": independent["checks_passed"]},
              "scope": "omitted physical POS-B control versus NCID/QTYNC1 in BASIC series; QTYNC>1 remains open"}
    (HERE / "evidence-index.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"accepted_raw": sum(len(r["raw"]) for r in runs.values()),
                      "excluded_raw": len(diagnostic["run"]["raw"]),
                      "author_checks": author["passed_count"],
                      "independent_checks": independent["checks_passed"]}))


if __name__ == "__main__":
    main()
