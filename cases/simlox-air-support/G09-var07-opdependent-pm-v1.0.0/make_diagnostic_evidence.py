"""Seal excluded G09.var07 v1.0.0 runs with inherited ENPM=N."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from check_roundtrip import native_json

HERE = Path(__file__).resolve().parent
ARMS = ("syshalf", "sysfull")
SOURCE = ("build.py", "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1",
          "contract.json", "exact-diff.json", "syshalf-input.json", "sysfull-input.json",
          "README.md", "make_diagnostic_evidence.py")


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def seal(path: Path) -> dict:
    return {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def rows(doc: dict, name: str) -> list[dict]:
    t = next(t for t in doc["report"]["tables"] if t["name"] == name)
    names = [c["name"] for c in t["columns"]]
    return [dict(zip(names, row, strict=True)) for inst in t["instances"] for row in inst["rows"]]


def main() -> None:
    contract = read(HERE / "contract.json")
    runs = {}
    for arm in ARMS:
        source = HERE / f"{arm}-input.json"
        doc = read(source)
        control = next(t for t in doc["model"]["tables"] if t["name"] == "Control")
        names = [c["name"] for c in control["columns"]]
        value = dict(zip(names, control["instances"][0]["rows"][0], strict=True))["ENPM"]
        if value != "N" or seal(source)["sha256"] != contract["input_sha256"][arm]:
            raise ValueError(f"diagnostic input changed: {arm}")
        run = HERE / "runs" / f"g09-var07-{arm}-v100-ssh-20261003-01"
        closure, rt = read(run / "closure.json"), read(run / "roundtrip-validation.json")
        if closure["native_outcome"] != "zero_error_reviewed_warnings" or \
           closure["conversion"]["errors"] != 0 or closure["conversion"]["warning_codes"] != ["108"] or \
           not rt["passed"] or len(rt["populated_tables"]) != 30 or len(closure["raw"]) != 13:
            raise ValueError(f"diagnostic native gate changed: {arm}")
        report = native_json(run / "report-raw.json")
        system = rows(report, "SystemResults")
        if len(system) != 72 or any((r["NPMS"] or 0) or (r["NPMT"] or 0) for r in system):
            raise ValueError(f"diagnostic PM absence changed: {arm}")
        raw = {n: seal(run / n) for n in sorted(closure["raw"])}
        if raw != {n: closure["raw"][n] for n in sorted(closure["raw"])}:
            raise ValueError(f"diagnostic raw changed: {arm}")
        runs[arm] = {"run_id": run.name, "local_directory": str(run),
                     "invocation": seal(run / "invocation.json"), "closure": seal(run / "closure.json"),
                     "raw": raw, "system_bins": len(system), "NPMS": 0, "NPMT": 0}
    result = {"schema": "simlox-g09-var07-disabled-pm-diagnostic/v1", "case_id": "G09",
              "variant_id": "G09.var07", "version": "1.0.0", "publication_state": "not_published",
              "reason": "Inherited Control.ENPM=N disabled PM in both arms, violating frozen first-PM timing gate.",
              "source": {n: seal(HERE / n) for n in SOURCE}, "runs": runs}
    (HERE / "diagnostic-evidence.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"diagnostic_raw": sum(len(x["raw"]) for x in runs.values())}))


if __name__ == "__main__":
    main()
