"""Seal G07.var04 v1.0.1 sources, guarded run and independent review."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN_ID = "g07-var04-br75-v101-ssh-20261003-01"


def seal(path: Path) -> dict:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    names = ("build.py", "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1", "validate_native.py",
             "contract.json", "exact-diff.json", "br75-input.json", "author-validation.json",
             "review/independent_replay.py", "review/independent-validation-2026-10-03.json")
    source = {name: seal(HERE / name) for name in names}
    author, reviewer = read(HERE / "author-validation.json"), read(HERE / "review/independent-validation-2026-10-03.json")
    if not author["passed"] or not reviewer["passed"]:
        raise ValueError("validation failed")
    contract = read(HERE / "contract.json")
    run = HERE / "runs" / RUN_ID
    closure = read(run / "closure.json")
    if closure["error"] or len(closure["raw"]) != 13:
        raise ValueError("native closure failed")
    result = {"schema": "simlox-g07-var04-bridge-operational-mode-evidence-index/v1", "case_id": "G07",
              "variant_id": "G07.var04", "version": "1.0.1", "publication_state": "not_published",
              "source": source, "accepted_parent": contract["accepted_parent"],
              "diagnostic_predecessor": contract["diagnostic_predecessor"],
              "manual_sha256": contract["source"]["manual_sha256"],
              "dictionary_sha256": contract["source"]["dictionary_sha256"],
              "run": {"run_id": RUN_ID, "local_directory": str(run), "invocation": seal(run / "invocation.json"),
                      "closure": seal(run / "closure.json"), "raw": closure["raw"],
                      "raw_file_count": len(closure["raw"]), "native_outcome": closure["native_outcome"]},
              "author_validation": {"passed": True, "passed_count": author["passed_count"]},
              "independent_validation": {"passed": True, "passed_count": reviewer.get("passed_count", reviewer.get("checks_passed"))}}
    (HERE / "evidence-index.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"source_files": len(source), "raw_files": len(closure["raw"]),
                      "author_checks": author["passed_count"],
                      "independent_checks": result["independent_validation"]["passed_count"]}))


if __name__ == "__main__":
    main()
