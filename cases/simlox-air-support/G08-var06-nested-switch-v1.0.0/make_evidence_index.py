"""Seal authored source, independent replay, closures, and local native raw evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARMS = ("instant", "delay05")
SOURCE = (
    "build.py", "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1",
    "validate_native.py", "make_evidence_index.py", "contract.json", "exact-diff.json",
    "instant-input.json", "delay05-input.json", "author-validation.json",
    "review/independent_replay.py", "review/independent-validation-2026-10-03.json",
    "README.md", "cli-scope-signoff-2026-10-03.md",
)


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def seal(path: Path) -> dict:
    return {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main() -> None:
    contract = read(HERE / "contract.json")
    author = read(HERE / "author-validation.json")
    independent = read(HERE / "review/independent-validation-2026-10-03.json")
    if not author["passed"] or not independent["passed"]:
        raise ValueError("acceptance replay not passed")
    runs = []
    for arm in ARMS:
        run = HERE / "runs" / f"g08-var06-{arm}-v100-ssh-20261003-01"
        closure = read(run / "closure.json")
        if closure["native_outcome"] != "zero_error_reviewed_warnings" or len(closure["raw"]) != 13:
            raise ValueError(f"unaccepted native closure: {arm}")
        runs.append({"arm": arm, "run_id": run.name, "local_directory": str(run),
                     "invocation": seal(run / "invocation.json"), "closure": seal(run / "closure.json"),
                     "raw": {name: seal(run / name) for name in sorted(closure["raw"])}})
        for name, value in runs[-1]["raw"].items():
            if value != closure["raw"][name]:
                raise ValueError(f"raw seal changed: {arm}/{name}")
    result = {"schema": "simlox-g08-var06-evidence-index/v1", "case_id": "G08", "variant_id": "G08.var06",
              "version": "1.0.0", "publication_state": "not_published",
              "source": {name: seal(HERE / name) for name in SOURCE},
              "accepted_parent": contract["accepted_parent"], "schema_donor": contract["schema_donor"],
              "manual_sha256": contract["source"]["manual_sha256"],
              "dictionary_sha256": contract["source"]["dictionary_sha256"],
              "runs": runs,
              "author_validation": {"passed": True, "checks": author["passed_count"]},
              "independent_validation": {"passed": True, "checks": independent["checks_passed"]},
              "scope": "one B/E passive parallel tree leaf, zero versus 0.5-hour switch, seed1/rep1; other nested paths open"}
    (HERE / "evidence-index.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"runs": len(runs), "raw_files": sum(len(r["raw"]) for r in runs),
                      "author_checks": author["passed_count"], "independent_checks": independent["checks_passed"]}))


if __name__ == "__main__":
    main()
