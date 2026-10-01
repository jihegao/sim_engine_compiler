"""Replay all twelve J01.var02 runs and record bounded sample statistics."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import statistics

import build
import validate

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "review/author-panel-validation-2026-10-01.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    details = []
    errors = []
    for seed in build.SEEDS:
        run = HERE / "runs" / f"j01-var02-seed{seed:02d}-v101-20261001-01"
        result = validate.validate(run, seed)
        if not result["passed"]:
            errors.extend(f"seed {seed}: {message}" for message in result["differences"])
        details.append({
            "seed": seed, "run_id": run.name, "input_sha256": sha(run / "input.json"),
            "invocation_sha256": sha(run / "invocation.json"),
            "closure_sha256": sha(run / "closure.json"),
            "validation_sha256": sha(run / "validation.json"),
            "sample_preparation_hours": result["sample_preparation_hours"],
            "report_preparation_hours": result["report_preparation_hours"],
            "raw_file_count": len(json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))["raw"]),
        })
    values = [row["sample_preparation_hours"] for row in details]
    if len(values) != 12 or any(value is None for value in values):
        errors.append("panel does not have twelve measured durations")
    if values and (min(values) < 0.25 - 1e-6 or max(values) > 0.75 + 1e-6):
        errors.append("panel sample outside RECT support")
    if len({round(value, 8) for value in values}) < 2:
        errors.append("RECT panel does not vary")
    if [row["seed"] for row in details] != list(range(1, 13)):
        errors.append("seed panel identity differs")
    result = {
        "schema": "simlox-j01-var02-author-panel/v1", "case_id": "J01",
        "variant_id": "J01.var02", "version": "1.0.1", "passed": not errors,
        "differences": errors, "runs": details,
        "sample_statistics": {
            "count": len(values), "minimum": min(values), "maximum": max(values),
            "mean": statistics.mean(values), "sample_stdev": statistics.stdev(values),
            "distinct_count": len({round(value, 8) for value in values}),
        },
        "raw_seal_count": sum(row["raw_file_count"] for row in details),
        "scope": "twelve fixed seeds; descriptive observations only, no population-law inference",
    }
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    OUTPUT.parent.mkdir(exist_ok=True)
    if OUTPUT.exists() and OUTPUT.read_bytes() != raw:
        raise ValueError("frozen author panel result differs")
    if not OUTPUT.exists():
        OUTPUT.write_bytes(raw)
    print(json.dumps({"passed": result["passed"], "differences": errors,
                      "statistics": result["sample_statistics"], "raw_seals": result["raw_seal_count"]}))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
