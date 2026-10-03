"""Record sealed native outcomes for the two frozen paired candidates."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
CASES = [
    ("E13-var01-two-item-robbing-probe-v0.1.2", "e13-var01-two-item-probe-v012-ssh-20261004-01", "0.1.2", "GO enabled candidate: explicit donor B2 rob at h8.47992, recipient ready h8.97992; paired control required"),
    ("E13-var01-two-item-no-robbing-control-v0.1.3", "e13-var01-no-robbing-control-v013-ssh-20261004-01", "0.1.3", "GO matched control candidate: no rob, recipient ready h12.8133; paired independent replay required"),
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    for package, run_id, version, decision in CASES:
        base = HERE / package
        run = base / "runs" / run_id
        contract = json.loads((base / "contract.json").read_text(encoding="utf-8"))
        closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
        assert closure["error"] is None and closure["run_id"] == run_id
        assert closure["source_hashes_before"] == closure["source_hashes_after"]
        assert len(closure["raw"]) == 12
        assert sha(base / "native-input.json") == contract["native_input_sha256"]
        for name, meta in closure["raw"].items():
            path = run / name
            assert path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"]
        result = {
            "schema": "simlox-e13-robbing-geometry-diagnostic/v1", "version": version,
            "run_id": run_id, "publication_state": "not_published", "decision": decision,
            "native_steps_completed": True, "roundtrip_passed": True, "conversion_errors": 0,
            "conversion_warning_ids": [108], "input_sha256": sha(base / "native-input.json"),
            "contract_sha256": sha(base / "contract.json"), "diff_sha256": sha(base / "exact-diff.json"),
            "closure_sha256": sha(run / "closure.json"), "event_log_sha256": sha(run / "model.log"),
            "report_sha256": sha(run / "report-raw.json"), "raw_files_sealed": len(closure["raw"]),
            "next_action": "Use only the bounded E13.var01 paired signoff after separate author and independent replay."
        }
        path = base / "diagnostic-2026-10-04.json"
        if path.exists():
            assert json.loads(path.read_text(encoding="utf-8")) == result
        else:
            path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(package, result["closure_sha256"])


if __name__ == "__main__":
    main()
