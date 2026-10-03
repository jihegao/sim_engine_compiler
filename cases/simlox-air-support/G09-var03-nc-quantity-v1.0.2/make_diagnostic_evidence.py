"""Seal both excluded v1.0.2 native runs without publishing them."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARMS = ("qty1", "qty2")
SOURCE = ("build.py", "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1",
          "contract.json", "exact-diff.json", "qty1-input.json", "qty2-input.json",
          "README.md", "make_diagnostic_evidence.py")


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def seal(path: Path) -> dict:
    return {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main() -> None:
    contract = read(HERE / "contract.json")
    runs = {}
    for arm in ARMS:
        run = HERE / "runs" / f"g09-var03-{arm}-v102-ssh-20261003-01"
        closure, rt = read(run / "closure.json"), read(run / "roundtrip-validation.json")
        if closure["native_outcome"] != "zero_error_reviewed_warnings" or len(closure["raw"]) != 13:
            raise ValueError(f"native closure invalid: {arm}")
        if not rt["passed"] or len(rt["populated_tables"]) != 27:
            raise ValueError(f"roundtrip invalid: {arm}")
        if seal(HERE / f"{arm}-input.json")["sha256"] != contract["input_sha256"][arm]:
            raise ValueError(f"input changed: {arm}")
        log = (run / "model.log").read_text(encoding="utf-8-sig")
        if "Time: 21.742 <TEACH-AIR-01,0> critical CM failure mode added" not in log or \
           "Time: 21.742 <PAR-MISSION,TEACH-UNIT,0,0,1> mission aborted:" not in log:
            raise ValueError(f"excluded result changed: {arm}")
        raw = {n: seal(run / n) for n in sorted(closure["raw"])}
        if raw != {n: closure["raw"][n] for n in sorted(closure["raw"])}:
            raise ValueError(f"raw seal changed: {arm}")
        runs[arm] = {"run_id": run.name, "local_directory": str(run),
                     "invocation": seal(run / "invocation.json"), "closure": seal(run / "closure.json"), "raw": raw}
    result = {"schema": "simlox-g09-var03-excluded-quantity-diagnostic-evidence/v1",
              "case_id": "G09", "variant_id": "G09.var03", "version": "1.0.2",
              "publication_state": "excluded_diagnostic",
              "reason": "h20 PAR uses its parallel mode; matched QTYNC1/2 arms both log second B critical and PAR abort, so frozen distinction was unobserved",
              "source": {n: seal(HERE / n) for n in SOURCE}, "runs": runs,
              "roundtrip_populated_tables_per_arm": 27}
    (HERE / "diagnostic-evidence.json").write_bytes((json.dumps(result, indent=2) + "\n").encode())
    print(json.dumps({"excluded": True, "raw_files": sum(len(r["raw"]) for r in runs.values())}))


if __name__ == "__main__":
    main()
