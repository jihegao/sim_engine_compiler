"""Prove accepted A02 parent fails proposed 66-bin System cutoff gate."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT_RUN = Path("C:/Users/user/Documents/Codex/2026-09-27/simlox-case-library-a01-a02-v1/repo/data/local/simlox-case-library/v1/A02/a02-bound-final-20260927-03")
PARENT_REPORT_SHA = "a7227687988841c074b28b524792af7d856cd674840169bf15c210f2d2cd4739"
PARENT_LOG_SHA = "5101ef9157f941627a2851774d884f9ec5abe92af894af0c177221749eca66ba"
OUTPUT = HERE / "review/negative-control-accepted-parent.json"
sys.path.insert(0, str(HERE.parent / "tools"))
from validate_native import remove_trailing_commas  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    report = PARENT_RUN / "report-raw.json"
    log = PARENT_RUN / "model.log"
    if sha(report) != PARENT_REPORT_SHA or sha(log) != PARENT_LOG_SHA:
        raise ValueError("accepted parent raw SHA differs")
    doc = json.loads(remove_trailing_commas(report.read_bytes()))
    found = [t for t in doc["report"]["tables"] if t["name"] == "SystemResults"]
    if len(found) != 1:
        raise ValueError("parent System table count differs")
    rows = [r for ins in found[0]["instances"] for r in ins["rows"]]
    columns = [c["name"] for c in found[0]["columns"]]
    if len(rows) != 72 or len(columns) != 40 or rows[-1][columns.index("ETINT")] != 36:
        raise ValueError("accepted parent System horizon differs")
    result = {"schema": "simlox-a02-var02-third-cutoff-v010-negative-control/v1",
              "parent_report_sha256": PARENT_REPORT_SHA, "parent_log_sha256": PARENT_LOG_SHA,
              "parent_system_rows": 72, "parent_system_end": 36,
              "predeclared_child_system_rows": 66, "predeclared_child_system_end": 33,
              "child_gate_passed": False, "native_process_started": False}
    data = (json.dumps(result, indent=2) + "\n").encode("utf-8")
    OUTPUT.parent.mkdir(exist_ok=True)
    if OUTPUT.exists() and OUTPUT.read_bytes() != data:
        raise ValueError("frozen negative control differs")
    OUTPUT.write_bytes(data)
    print(json.dumps({"passed": True, "sha256": hashlib.sha256(data).hexdigest()}))


if __name__ == "__main__":
    main()
