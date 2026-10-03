"""Seal G09.var01 authored, reviewed and local native evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs" / "g09-var01-mixed-v100-ssh-20261003-01"
SOURCE = (
    "build.py", "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1",
    "validate_native.py", "make_evidence_index.py", "contract.json", "exact-diff.json",
    "mixed-input.json", "author-validation.json", "review/independent_replay.py",
    "review/independent-validation-2026-10-03.json", "README.md", "cli-scope-signoff-2026-10-03.md",
)


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def seal(path: Path) -> dict:
    return {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main() -> None:
    contract = read(HERE / "contract.json")
    author = read(HERE / "author-validation.json")
    independent = read(HERE / "review/independent-validation-2026-10-03.json")
    closure = read(RUN / "closure.json")
    if not author["passed"] or not independent["passed"]:
        raise ValueError("acceptance replay not passed")
    if closure["native_outcome"] != "zero_error_reviewed_warnings" or len(closure["raw"]) != 13:
        raise ValueError("unaccepted native closure")
    raw = {name: seal(RUN / name) for name in sorted(closure["raw"])}
    for name, value in raw.items():
        if value != closure["raw"][name]:
            raise ValueError(f"raw seal changed: {name}")
    result = {"schema": "simlox-g09-var01-evidence-index/v1", "case_id": "G09", "variant_id": "G09.var01",
              "version": "1.0.0", "publication_state": "not_published",
              "source": {name: seal(HERE / name) for name in SOURCE},
              "accepted_parent": contract["accepted_parent"],
              "schema_and_control_donor": contract["schema_and_control_donor"],
              "manual_sha256": contract["source"]["manual_sha256"],
              "dictionary_sha256": contract["source"]["dictionary_sha256"],
              "run": {"run_id": RUN.name, "local_directory": str(RUN),
                      "invocation": seal(RUN / "invocation.json"), "closure": seal(RUN / "closure.json"),
                      "raw": raw},
              "author_validation": {"passed": True, "checks": author["passed_count"]},
              "independent_validation": {"passed": True, "checks": independent["checks_passed"]},
              "scope": "one aircraft, BASIC series versus PAR parallel across three seeded missions; remaining G09 boundaries open"}
    (HERE / "evidence-index.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"raw_files": len(raw), "author_checks": author["passed_count"],
                      "independent_checks": independent["checks_passed"]}))


if __name__ == "__main__":
    main()
