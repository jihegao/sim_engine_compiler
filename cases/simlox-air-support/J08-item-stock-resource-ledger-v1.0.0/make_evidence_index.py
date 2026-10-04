"""Index local sealed native artifacts without publishing proprietary raw bytes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = ["j08-ledger-v100-ssh-20261004-01", "j08-item-report-v100-ssh-20261004-01",
        "j08-item-full-v100-ssh-20261004-01"]
FILES = ["native-input.json", "exact-diff.json", "contract.json", "report-contract-amendment.json",
         "build.py", "describe_diff.py", "check_roundtrip.py", "run_native_ssh.ps1",
         "make_report_settings.py", "run_item_report_ssh.ps1", "make_full_report_settings.py",
         "run_item_report_full_ssh.ps1", "validate_native.py", "author-validation-2026-10-04.json",
         "review/static-review-2026-10-04.md", "review/independent_replay.py",
         "review/independent-verdict.json"]


def seal(path: Path) -> dict:
    raw = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def main() -> None:
    result = {"schema": "simlox-j08-evidence-index/v1", "case_id": "J08",
              "publication_state": "candidate", "files": {}, "native_runs": {}, "local_report_settings": {}}
    for name in FILES:
        path = HERE / name
        assert path.is_file(), name
        result["files"][name] = seal(path)
    for run_id in RUNS:
        directory = HERE / "runs" / run_id
        closure = json.loads((directory / "closure.json").read_text(encoding="utf-8-sig"))
        assert closure["run_id"] == run_id and closure["error"] is None
        assert closure["invocation_sha256"] == seal(directory / "invocation.json")["sha256"]
        raw = {}
        for name, expected in closure["raw"].items():
            raw[name] = seal(directory / name)
            assert raw[name]["sha256"] == expected["sha256"] and raw[name]["bytes"] == expected["bytes"]
        result["native_runs"][run_id] = {"closure": seal(directory / "closure.json"),
                                           "invocation": seal(directory / "invocation.json"), "raw": raw}
    for name in ("item-position-selected.sxs", "item-position-results.sxs"):
        result["local_report_settings"][name] = seal(HERE / "runs" / "report-settings" / name)
    (HERE / "evidence-index.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"indexed {len(result['native_runs'])} sealed native runs")


if __name__ == "__main__":
    main()
