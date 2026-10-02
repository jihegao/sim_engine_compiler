"""Seal the four-path bridge panel sources, guarded runs and independent review."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARMS = ("ulur", "lllr", "ulbrlr", "allbroken")
IDS = {arm: f"g07-panel-{arm}-v100-ssh-20261003-01" for arm in ARMS}


def seal(path: Path) -> dict:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    names = ("build.py", "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1", "validate_native.py",
             "contract.json", "exact-diff.json", *(f"{arm}-input.json" for arm in ARMS), "author-validation.json",
             "review/independent_replay.py", "review/independent-validation-2026-10-03.json")
    source = {name: seal(HERE / name) for name in names}
    author, reviewer = read(HERE / "author-validation.json"), read(HERE / "review/independent-validation-2026-10-03.json")
    if not author["passed"] or not reviewer["passed"]:
        raise ValueError("validation failed")
    contract = read(HERE / "contract.json")
    runs = {}
    for arm, run_id in IDS.items():
        run = HERE / "runs" / run_id
        closure = read(run / "closure.json")
        runs[arm] = {"run_id": run_id, "local_directory": str(run), "invocation": seal(run / "invocation.json"),
                     "closure": seal(run / "closure.json"), "raw": closure["raw"],
                     "raw_file_count": len(closure["raw"]), "native_outcome": closure["native_outcome"]}
    result = {"schema": "simlox-g07-four-path-panel-evidence-index/v1", "case_id": "G07",
              "variant_ids": ["G07.var01", "G07.var02"], "version": "1.0.0", "publication_state": "not_published",
              "source": source, "accepted_parent": contract["accepted_parent"],
              "manual_sha256": contract["source"]["manual_sha256"],
              "dictionary_sha256": contract["source"]["dictionary_sha256"], "runs": runs,
              "author_validation": {"passed": True, "passed_count": author["passed_count"]},
              "independent_validation": {"passed": True, "passed_count": reviewer.get("passed_count", reviewer.get("checks_passed"))}}
    (HERE / "evidence-index.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"source_files": len(source), "raw_files": {arm: runs[arm]["raw_file_count"] for arm in ARMS},
                      "author_checks": author["passed_count"], "independent_checks": result["independent_validation"]["passed_count"]}))


if __name__ == "__main__":
    main()
