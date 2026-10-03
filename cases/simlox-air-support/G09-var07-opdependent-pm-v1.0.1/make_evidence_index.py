"""Seal reviewed G09.var07 PM runs and excluded disabled-PM controls."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ARMS = ("syshalf", "sysfull")
SOURCE = ("build.py", "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1",
          "validate_native.py", "make_evidence_index.py", "contract.json", "exact-diff.json",
          "syshalf-input.json", "sysfull-input.json", "author-validation.json",
          "review/independent_replay.py", "review/independent-validation-2026-10-03.json",
          "README.md", "contract-erratum.md", "cli-scope-signoff-2026-10-03.md")


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def seal(path: Path) -> dict:
    return {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main() -> None:
    contract, author, independent = (read(p) for p in
        (HERE / "contract.json", HERE / "author-validation.json",
         HERE / "review/independent-validation-2026-10-03.json"))
    if not author["passed"] or not independent["passed"]:
        raise ValueError("author and independent acceptance required")
    controls = {}
    for key, package, source, run, pin in (
        ("G09_parent", "G09-var04-usert-boundary-v1.0.1", "use1-input.json",
         "g09-var04-use1-v101-ssh-20261003-01", contract["accepted_parent"]),
        ("D10_PM_pattern", "D10-var02-multi-counter-v1.0.0", "native-input.json",
         "d10-multicounter-v100-ssh-20261001-01", contract["accepted_pm_pattern"])):
        pkg = ROOT / package
        input_path, closure_path = pkg / source, pkg / "runs" / run / "closure.json"
        if seal(input_path)["sha256"] != pin["input_sha256"] or \
           seal(closure_path)["sha256"] != pin["native_closure_sha256"]:
            raise ValueError(f"accepted control changed: {key}")
        controls[key] = {"contract": pin, "input": seal(input_path), "closure": seal(closure_path)}
    diagnostic = ROOT / "G09-var07-opdependent-pm-v1.0.0"
    diag_index = diagnostic / "diagnostic-evidence.json"
    diag = read(diag_index)
    if diag["publication_state"] != "not_published" or len(diag["runs"]) != 2:
        raise ValueError("diagnostic index changed")
    for arm in ARMS:
        path = diagnostic / f"{arm}-input.json"
        run = diagnostic / "runs" / f"g09-var07-{arm}-v100-ssh-20261003-01"
        if seal(path)["sha256"] != contract["excluded_diagnostic"]["input_sha256"][arm] or \
           seal(run / "closure.json")["sha256"] != contract["excluded_diagnostic"]["native_closure_sha256"][arm]:
            raise ValueError(f"diagnostic source changed: {arm}")
    runs = {}
    for arm in ARMS:
        run = HERE / "runs" / f"g09-var07-{arm}-v101-ssh-20261003-01"
        closure, rt = read(run / "closure.json"), read(run / "roundtrip-validation.json")
        if closure["native_outcome"] != "zero_error_reviewed_warnings" or len(closure["raw"]) != 13:
            raise ValueError(f"native closure changed: {arm}")
        if not rt["passed"] or len(rt["populated_tables"]) != 30:
            raise ValueError(f"native roundtrip changed: {arm}")
        if seal(HERE / f"{arm}-input.json")["sha256"] != contract["input_sha256"][arm]:
            raise ValueError(f"input changed: {arm}")
        raw = {n: seal(run / n) for n in sorted(closure["raw"])}
        if raw != {n: closure["raw"][n] for n in sorted(closure["raw"])}:
            raise ValueError(f"raw seal changed: {arm}")
        runs[arm] = {"run_id": run.name, "local_directory": str(run),
                     "invocation": seal(run / "invocation.json"), "closure": seal(run / "closure.json"),
                     "raw": raw}
    result = {"schema": "simlox-g09-var07-opdependent-pm-evidence-index/v1", "case_id": "G09",
              "variant_id": "G09.var07", "version": "1.0.1", "publication_state": "not_published",
              "source": {n: seal(HERE / n) for n in SOURCE}, "accepted_controls": controls,
              "excluded_diagnostic_index": seal(diag_index),
              "manual_sha256": contract["source"]["manual_sha256"],
              "dictionary_sha256": contract["source"]["dictionary_sha256"],
              "runs": runs,
              "author_validation": {"passed": True, "checks": author["passed_count"]},
              "independent_validation": {"passed": True, "checks": independent["checks_passed"]},
              "scope": "two-arm BASIC system USERT0.5/1 shifts first system OPHOURS1.5 PM h22/h10, one versus three tasks, one seed"}
    (HERE / "evidence-index.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"accepted_raw": sum(len(x["raw"]) for x in runs.values()),
                      "diagnostic_raw": sum(len(x["raw"]) for x in diag["runs"].values()),
                      "author_checks": author["passed_count"],
                      "independent_checks": independent["checks_passed"]}))


if __name__ == "__main__":
    main()
