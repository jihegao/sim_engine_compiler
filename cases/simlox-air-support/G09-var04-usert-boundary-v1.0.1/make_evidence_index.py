"""Seal accepted G09.var04 four-arm panel and unpublished preliminary evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRELIM = HERE.parent / "G09-var04-usert-boundary-v1.0.0"
ARMS = ("use0", "use05", "use1", "use2")
SOURCE = ("build.py", "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1",
          "validate_native.py", "make_evidence_index.py", "contract.json", "exact-diff.json",
          "use0-input.json", "use05-input.json", "use1-input.json", "use2-input.json",
          "author-validation.json", "review/independent_replay.py", "review/independent-validation-2026-10-03.json",
          "README.md", "cli-scope-signoff-2026-10-03.md")


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def seal(path: Path) -> dict:
    return {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main() -> None:
    contract, author, independent = (read(p) for p in
        (HERE / "contract.json", HERE / "author-validation.json", HERE / "review/independent-validation-2026-10-03.json"))
    preliminary = read(PRELIM / "preliminary-evidence.json")
    if not author["passed"] or not independent["passed"] or preliminary["publication_state"] != "preliminary_unpublished":
        raise ValueError("acceptance or preliminary status changed")
    for arm in ARMS:
        if preliminary["runs"][arm]["closure"]["sha256"] != contract["preliminary_panel"]["native_closure_sha256"][arm]:
            raise ValueError(f"preliminary closure changed: {arm}")
    runs = {}
    for arm in ARMS:
        run = HERE / "runs" / f"g09-var04-{arm}-v101-ssh-20261003-01"
        closure, rt = read(run / "closure.json"), read(run / "roundtrip-validation.json")
        if closure["native_outcome"] != "zero_error_reviewed_warnings" or len(closure["raw"]) != 13:
            raise ValueError(f"native closure changed: {arm}")
        if not rt["passed"] or len(rt["populated_tables"]) != 25:
            raise ValueError(f"roundtrip changed: {arm}")
        raw = {name: seal(run / name) for name in sorted(closure["raw"])}
        if raw != {name: closure["raw"][name] for name in sorted(closure["raw"])}:
            raise ValueError(f"raw seal changed: {arm}")
        runs[arm] = {"run_id": run.name, "local_directory": str(run),
                     "invocation": seal(run / "invocation.json"), "closure": seal(run / "closure.json"), "raw": raw}
    result = {"schema": "simlox-g09-var04-usert-evidence-index/v1", "case_id": "G09",
              "variant_id": "G09.var04", "version": "1.0.1", "publication_state": "not_published",
              "source": {name: seal(HERE / name) for name in SOURCE},
              "accepted_parent": contract["accepted_parent"],
              "preliminary_panel": {"contract": contract["preliminary_panel"],
                                    "evidence": seal(PRELIM / "preliminary-evidence.json")},
              "manual_sha256": contract["source"]["manual_sha256"],
              "dictionary_sha256": contract["source"]["dictionary_sha256"],
              "runs": runs,
              "author_validation": {"passed": True, "checks": author["passed_count"]},
              "independent_validation": {"passed": True, "checks": independent["checks_passed"]},
              "scope": "BASIC POS-B USERT0/0.5/1/2 with common positive A FRQ1e-9; direct first-BASIC fault contrast at half/full/double versus zero; one seed"}
    (HERE / "evidence-index.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"accepted_raw": sum(len(r["raw"]) for r in runs.values()),
                      "preliminary_raw": sum(len(r["raw"]) for r in preliminary["runs"].values()),
                      "author_checks": author["passed_count"], "independent_checks": independent["checks_passed"]}))


if __name__ == "__main__":
    main()
