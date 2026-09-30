"""Index sealed local raw evidence without committing proprietary native files."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN_ID = "c08-exact-limit-20260930-02"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    run = HERE / "runs" / RUN_ID
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    assert closure["error"] is None and closure["run_id"] == RUN_ID
    result = {
        "schema": "simlox-c08-exact-limit-evidence-index/v1",
        "host": "4700-3",
        "relative_raw_root": "runs/",
        "raw_publication": "local_sealed_not_committed",
        "source_manual_sha256": "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3",
        "source_dictionary_sha256": "11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0",
        "simlox_exe_sha256": "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0",
        "runs": [{
            "variant": "exact-limit",
            "run_id": RUN_ID,
            "original_run_dir": str(run.resolve()),
            "input_sha256": sha(run / "input.json"),
            "closure_sha256": sha(run / "closure.json"),
            "run_log_sha256": sha(run / "run.log"),
            "model_log_sha256": sha(run / "model.log"),
            "report_raw_sha256": sha(run / "report-raw.json"),
            "raw": closure["raw"],
        }],
        "excluded_diagnostic_run": "c08-exact-limit-20260930-01: contract parent publication ID was corrected after execution; raw retained locally, not used for acceptance",
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
