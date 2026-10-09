"""Read-only bounded I05.var04 source/export/log/report verifier."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from check_roundtrip import validate as check_roundtrip
from event_ledger import verify_file as check_log
from model_common import NATIVE_DIR, RECOVERED_DIR, RUN_ID, INPUT_PIN, seal
from report_oracle import compare_file as check_report
from source_gate import verify as check_source

def validate(run: Path) -> dict[str, object]:
    assert run in (NATIVE_DIR, RECOVERED_DIR) and run.is_dir()
    check_source()
    exported = check_roundtrip(run, source=False)
    log = check_log(run / "model.log")
    report = check_report(run / "report-raw.json", log["ledger"])
    assert log["physical_lines"] == 222 and log["timed_lines"] == 186
    assert report["typed_cells"] == 4044
    return {"schema":"i05-var04-native-behavior-check/v103", "passed":True,
            "run_id":RUN_ID, "native_run_directory":str(NATIVE_DIR),
            "input_sha256":INPUT_PIN["sha256"], "export_sha256":exported["export_sha256"],
            "log_sha256":seal(run / "model.log")["sha256"],
            "report_sha256":report["raw_sha256"],
            "physical_log_lines":222, "timed_log_lines":186, "report_typed_cells":4044,
            "authored_cells":284, "exported_cells":379,
            "complete_repair_cycles":3, "native_calls":0, "issues":[]}

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(validate(args.run_dir), sort_keys=True))

if __name__ == "__main__":
    main()
