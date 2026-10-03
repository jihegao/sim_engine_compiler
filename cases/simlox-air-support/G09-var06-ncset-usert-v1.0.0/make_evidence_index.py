"""Seal reviewed G09.var06 NC-set usage runs and accepted parent."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARMS = ("ncuse0", "ncuse1")
CONTROL = HERE.parent / "G09-var03-default-noncritical-v1.0.1"
SOURCE = ("build.py", "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1",
          "validate_native.py", "make_evidence_index.py", "contract.json", "exact-diff.json",
          "ncuse0-input.json", "ncuse1-input.json", "author-validation.json",
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
    if not author["passed"] or not independent["passed"]:
        raise ValueError("independent and author acceptance required")
    accepted = contract["accepted_parent"]
    parent_run = CONTROL / "runs" / "g09-var03-omitted-nc-b1-v101-ssh-20261003-01"
    parent_source = CONTROL / "omitted-nc-b1-input.json"
    if seal(parent_source)["sha256"] != accepted["input_sha256"] or \
       seal(parent_run / "closure.json")["sha256"] != accepted["native_closure_sha256"]:
        raise ValueError("accepted parent changed")
    controls = {"omitted_nc_b1": {"contract": accepted, "input": seal(parent_source),
                                  "closure": seal(parent_run / "closure.json")}}
    runs = {}
    for arm in ARMS:
        run = HERE / "runs" / f"g09-var06-{arm}-v100-ssh-20261003-01"
        closure, rt = read(run / "closure.json"), read(run / "roundtrip-validation.json")
        if closure["native_outcome"] != "zero_error_reviewed_warnings" or len(closure["raw"]) != 13:
            raise ValueError(f"native closure changed: {arm}")
        if not rt["passed"] or len(rt["populated_tables"]) != 27:
            raise ValueError(f"native roundtrip changed: {arm}")
        if seal(HERE / f"{arm}-input.json")["sha256"] != contract["input_sha256"][arm]:
            raise ValueError(f"input changed: {arm}")
        raw = {n: seal(run / n) for n in sorted(closure["raw"])}
        if raw != {n: closure["raw"][n] for n in sorted(closure["raw"])}:
            raise ValueError(f"raw seal changed: {arm}")
        runs[arm] = {"run_id": run.name, "local_directory": str(run),
                     "invocation": seal(run / "invocation.json"), "closure": seal(run / "closure.json"),
                     "raw": raw}
    result = {"schema": "simlox-g09-var06-ncset-usert-evidence-index/v1", "case_id": "G09",
              "variant_id": "G09.var06", "version": "1.0.0", "publication_state": "not_published",
              "source": {n: seal(HERE / n) for n in SOURCE}, "accepted_controls": controls,
              "manual_sha256": contract["source"]["manual_sha256"],
              "dictionary_sha256": contract["source"]["dictionary_sha256"],
              "runs": runs,
              "author_validation": {"passed": True, "checks": author["passed_count"]},
              "independent_validation": {"passed": True, "checks": independent["checks_passed"]},
              "scope": "two-arm BASIC NC-set POS-B USERT0 versus1, source-bound absence versus noncritical BASIC B faults in one seed"}
    (HERE / "evidence-index.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"accepted_raw": sum(len(r["raw"]) for r in runs.values()),
                      "author_checks": author["passed_count"],
                      "independent_checks": independent["checks_passed"]}))


if __name__ == "__main__":
    main()
