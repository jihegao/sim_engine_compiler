"""Seal F04.var01 accepted and excluded local native artifacts by path and SHA-256."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUNS = ["f04-var01-repeat-a-v101-ssh-20261004-01",
        "f04-var01-repeat-b-v101-ssh-20261004-01"]
EXCLUDED = [ROOT / "F04-var01-deterministic-43day-v1.0.0" / "runs" /
            f"f04-var01-repeat-{arm}-v100-ssh-20261004-01" for arm in ("a", "b")]
FILES = ["native-input.json", "contract.json", "exact-diff.json", "build.py",
         "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1",
         "validate_native.py", "author-validation-2026-10-04.json",
         "review/static-review-2026-10-04.md",
         "review/independent_replay.py", "review/independent-verdict.json"]


def seal(path: Path) -> dict:
    raw = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def sealed_run(run: Path) -> dict:
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    assert closure["run_id"] == run.name and closure["error"] is None
    assert closure["invocation_sha256"] == seal(run / "invocation.json")["sha256"]
    raw = {}
    for name, expected in closure["raw"].items():
        raw[name] = seal(run / name)
        assert raw[name]["bytes"] == expected["bytes"]
        assert raw[name]["sha256"] == expected["sha256"]
    return {"closure": seal(run / "closure.json"),
            "invocation": seal(run / "invocation.json"), "raw": raw}


def main() -> None:
    result = {"schema": "simlox-f04-deterministic-43day-evidence-index/v1",
              "case_id": "F04", "variant_id": "F04.var01", "version": "1.0.1",
              "publication_state": "candidate", "files": {}, "native_runs": {},
              "excluded_diagnostics": {}}
    for name in FILES:
        path = HERE / name
        assert path.is_file(), name
        result["files"][name] = seal(path)
    for name in RUNS:
        result["native_runs"][name] = sealed_run(HERE / "runs" / name)
    for run in EXCLUDED:
        result["excluded_diagnostics"][run.name] = {
            "reason": "IQTY21/IPER48 compressed mission requests to 2.2857-hour spacing",
            **sealed_run(run)}
    (HERE / "evidence-index.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"indexed {len(RUNS)} accepted and {len(EXCLUDED)} excluded runs")


if __name__ == "__main__":
    main()
