"""Seal the four reviewed preliminary runs without publishing them."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARMS = ("use0", "use05", "use1", "use2")
SOURCE = ("build.py", "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1",
          "validate_native.py", "make_preliminary_evidence.py", "contract.json", "exact-diff.json",
          "use0-input.json", "use05-input.json", "use1-input.json", "use2-input.json",
          "author-validation.json", "review/independent_replay.py",
          "review/independent-validation-2026-10-03.json", "README.md")


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def seal(path: Path) -> dict:
    return {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main() -> None:
    contract = read(HERE / "contract.json")
    author = read(HERE / "author-validation.json")
    independent = read(HERE / "review/independent-validation-2026-10-03.json")
    if not author["passed"] or not independent["passed"] or independent["checks_passed"] != 11754:
        raise ValueError("reviewed preliminary status changed")
    runs = {}
    for arm in ARMS:
        run = HERE / "runs" / f"g09-var04-{arm}-v100-ssh-20261003-01"
        closure, rt = read(run / "closure.json"), read(run / "roundtrip-validation.json")
        if closure["native_outcome"] != "zero_error_reviewed_warnings" or len(closure["raw"]) != 13:
            raise ValueError(f"native result changed: {arm}")
        if not rt["passed"] or len(rt["populated_tables"]) != 25:
            raise ValueError(f"roundtrip changed: {arm}")
        if seal(HERE / f"{arm}-input.json")["sha256"] != contract["input_sha256"][arm]:
            raise ValueError(f"input changed: {arm}")
        raw = {n: seal(run / n) for n in sorted(closure["raw"])}
        if raw != {n: closure["raw"][n] for n in sorted(closure["raw"])}:
            raise ValueError(f"raw changed: {arm}")
        runs[arm] = {"run_id": run.name, "local_directory": str(run),
                     "invocation": seal(run / "invocation.json"), "closure": seal(run / "closure.json"), "raw": raw}
    result = {"schema": "simlox-g09-var04-preliminary-evidence/v1", "case_id": "G09",
              "variant_id": "G09.var04", "version": "1.0.0",
              "publication_state": "preliminary_unpublished",
              "reason": "USERT0.5 BASIC missions were preempted by POS-A before a POS-B fault; positive fractional B exposure unobserved",
              "source": {n: seal(HERE / n) for n in SOURCE}, "runs": runs,
              "author_validation": {"passed": True, "checks": author["passed_count"]},
              "independent_validation": {"passed": True, "checks": independent["checks_passed"]}}
    (HERE / "preliminary-evidence.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"preliminary": True, "raw_files": sum(len(r["raw"]) for r in runs.values())}))


if __name__ == "__main__":
    main()
