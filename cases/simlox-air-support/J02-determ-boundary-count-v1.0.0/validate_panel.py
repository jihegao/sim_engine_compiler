"""Recheck all five accepted J02 deterministic and boundary-count runs."""
from __future__ import annotations

import json
from pathlib import Path

import build
import validate

HERE = Path(__file__).resolve().parent
RUN_IDS = {
    "determ-2-seed-01": "j02-determ-2-seed01-accepted-20261001-01",
    "determ-2-seed-02": "j02-determ-2-seed02-accepted-20261001-01",
    "zero-six": "j02-zero-six-accepted-20261001-01",
    "four-eight": "j02-four-eight-accepted-20261001-01",
    "four-six": "j02-four-six-accepted-20261001-01",
}


def main() -> None:
    outputs, diff = build.build()
    if len(outputs) != 5 or (HERE / "exact-diff.json").read_bytes() != diff:
        raise ValueError("builder or exact diff differs")
    results = {arm: validate.validate(HERE / "runs" / run_id, arm)
               for arm, run_id in RUN_IDS.items()}
    errors = [f"{arm}: {result['differences']}" for arm, result in results.items()
              if not result["passed"]]
    if set(results) != set(build.ARMS):
        errors.append("run panel lacks an arm")
    if [results[arm]["starts"] for arm in RUN_IDS] != [2, 2, 0, 4, 3]:
        errors.append("cross-arm starts differ")
    if [results[arm]["flight_hours"] for arm in RUN_IDS] != [8, 8, 0, 16, 12]:
        errors.append("cross-arm flight hours differ")
    if results["four-six"]["cancellations"] != [(8.33333, 4)]:
        errors.append("six-aircraft capacity cancellation differs")
    if any(results[arm]["cancellations"] for arm in RUN_IDS if arm != "four-six"):
        errors.append("unexpected cancellation in other arm")
    output = {
        "schema": "simlox-j02-determ-boundary-author-panel/v1",
        "case_id": "J02", "variant_ids": ["J02.var01", "J02.var04"],
        "version": "1.0.0", "passed": not errors, "differences": errors,
        "accepted_run_ids": RUN_IDS,
        "excluded_probe_run_ids": sorted(path.name for path in (HERE / "runs").iterdir()
                                          if path.is_dir() and "-probe-" in path.name),
        "arms": results,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
