"""Freeze local raw evidence paths and hashes without committing raw artifacts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = {"qty-zero": "c07-shift-qty-zero-20260930-02", "row-absent": "c07-shift-row-absent-20260930-02"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    entries = []
    for variant, run_id in RUNS.items():
        run = HERE / "runs" / run_id
        closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
        assert closure["error"] is None
        entries.append({
            "variant": variant,
            "run_id": run_id,
            "original_run_dir": str(run.resolve()),
            "input_sha256": sha(run / "input.json"),
            "closure_sha256": sha(run / "closure.json"),
            "model_log_sha256": sha(run / "model.log"),
            "report_raw_sha256": sha(run / "report-raw.json"),
            "raw": closure["raw"],
        })
    result = {
        "schema": "simlox-c07-missing-shift-resource-evidence-index/v1",
        "host": "4700-3",
        "relative_raw_root": "runs/",
        "raw_publication": "local_sealed_not_committed",
        "source_manual_sha256": "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3",
        "source_dictionary_sha256": "11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0",
        "simlox_exe_sha256": "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0",
        "runs": entries,
        "excluded_diagnostic_runs": ["c07-shift-qty-zero-20260930-01: completed under prior checker, superseded by paired -02", "c07-shift-row-absent-20260930-01: old checker rejected native all-null placeholder in empty ShiftResource table"],
    }
    path = HERE / "evidence-index.json"
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    if path.exists():
        assert path.read_bytes() == raw
    else:
        path.write_bytes(raw)
    print(sha(path))


if __name__ == "__main__":
    main()



