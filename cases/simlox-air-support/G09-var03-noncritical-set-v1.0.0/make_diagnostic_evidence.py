"""Seal the excluded G09.var03 v1.0.0 native diagnostic without accepting it."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs" / "g09-var03-nc-b1-v100-ssh-20261003-01"
SOURCE = ("build.py", "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1",
          "contract.json", "exact-diff.json", "nc-b1-input.json", "README.md",
          "make_diagnostic_evidence.py")


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def seal(path: Path) -> dict:
    return {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main() -> None:
    closure, rt = read(RUN / "closure.json"), read(RUN / "roundtrip-validation.json")
    if closure["native_outcome"] != "zero_error_reviewed_warnings" or len(closure["raw"]) != 13:
        raise ValueError("native run not intact")
    if not rt["passed"] or len(rt["populated_tables"]) != 27:
        raise ValueError("roundtrip not intact")
    log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    if "Time: 8.62763 <TEACH-AIR-01,0> critical CM failure mode added" not in log or \
       "Time: 8.62763 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission aborted:" not in log:
        raise ValueError("frozen hypothesis did not fail as observed")
    raw = {n: seal(RUN / n) for n in sorted(closure["raw"])}
    if raw != {n: closure["raw"][n] for n in sorted(closure["raw"])}:
        raise ValueError("raw seal changed")
    result = {"schema": "simlox-g09-var03-excluded-diagnostic-evidence/v1", "case_id": "G09",
              "variant_id": "G09.var03", "version": "1.0.0", "publication_state": "excluded_diagnostic",
              "reason": "POS-B still critical in selected RBDSeries despite NCID; frozen positive hypothesis failed",
              "source": {n: seal(HERE / n) for n in SOURCE},
              "run": {"run_id": RUN.name, "local_directory": str(RUN),
                      "invocation": seal(RUN / "invocation.json"),
                      "closure": seal(RUN / "closure.json"), "raw": raw},
              "roundtrip_populated_tables": 27}
    (HERE / "diagnostic-evidence.json").write_bytes((json.dumps(result, indent=2) + "\n").encode())
    print(json.dumps({"excluded": True, "raw_files": len(raw)}))


if __name__ == "__main__":
    main()
