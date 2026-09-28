"""Source-bound A03 v2 checks layered over the preserved probe validator.

``validate.py`` is retained byte-for-byte because the three historical probe
archives bind its SHA-256. New runs also bind and execute this stricter check.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import validate as original  # noqa: E402

EXPECTED_SUMMARY = {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MSTF": 1, "MSUF": 1}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_summary(report: dict) -> list[str]:
    try:
        rows = original.native.table_rows(report, "ResultSummary")
    except (KeyError, ValueError) as error:
        return [str(error)]
    if len(rows) != 1:
        return [f"ResultSummary must have one row, got {len(rows)}"]
    errors = []
    for field, expected in EXPECTED_SUMMARY.items():
        actual = rows[0].get(field)
        if type(actual) not in (int, float) or not math.isfinite(actual) or actual != expected:
            errors.append(f"ResultSummary.{field}: expected {expected}, got {actual!r}")
    return errors


def validate(run_dir: Path) -> dict:
    invocation = json.loads((run_dir / "invocation.json").read_text(encoding="utf-8-sig"))
    if invocation.get("strict_validator_sha256") != sha256(Path(__file__)):
        raise ValueError("invocation strict validator hash differs from acceptance source")
    base = original.validate(run_dir)
    report = json.loads(original.native.remove_trailing_commas(
        (run_dir / "report-raw.json").read_bytes()))
    differences = [*base["differences"], *check_summary(report)]
    return {**base, "schema": "simlox-a03-strict-validation/v2",
            "passed": not differences, "differences": differences,
            "strict_validator_sha256": sha256(Path(__file__))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    result = validate(args.run_dir)
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
