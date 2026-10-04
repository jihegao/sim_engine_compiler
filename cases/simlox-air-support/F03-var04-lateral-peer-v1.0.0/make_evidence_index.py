"""Seal F03.var04 source, review, and ignored native raw bytes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = ["f03-lateral-on-v100-ssh-20261004-01",
        "f03-lateral-off-v100-ssh-20261004-01"]
FILES = ["lateral_on-input.json", "lateral_off-input.json", "contract.json",
         "exact-diff.json", "build.py", "describe_diff.py", "check_roundtrip.py",
         "run_native_ssh.ps1", "validate_native.py",
         "author-validation-2026-10-04.json",
         "review/static-review-2026-10-04.md",
         "review/independent_replay.py", "review/independent-verdict.json"]


def seal(path: Path) -> dict:
    raw = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def main() -> None:
    result = {"schema": "simlox-f03-lateral-peer-evidence-index/v1",
              "case_id": "F03", "variant_id": "F03.var04",
              "publication_state": "candidate", "files": {}, "native_runs": {}}
    for name in FILES:
        path = HERE / name
        assert path.is_file(), name
        result["files"][name] = seal(path)
    for run_id in RUNS:
        run = HERE / "runs" / run_id
        closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
        assert closure["run_id"] == run_id and closure["error"] is None
        assert closure["invocation_sha256"] == seal(run / "invocation.json")["sha256"]
        raw = {}
        for name, expected in closure["raw"].items():
            raw[name] = seal(run / name)
            assert raw[name]["bytes"] == expected["bytes"]
            assert raw[name]["sha256"] == expected["sha256"]
        result["native_runs"][run_id] = {
            "closure": seal(run / "closure.json"),
            "invocation": seal(run / "invocation.json"), "raw": raw}
    (HERE / "evidence-index.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"indexed {len(RUNS)} sealed runs")


if __name__ == "__main__":
    main()
