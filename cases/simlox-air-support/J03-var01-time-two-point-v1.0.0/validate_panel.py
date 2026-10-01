"""Replay all 32 accepted J03.var01 runs and freeze bounded count statistics."""
from __future__ import annotations

from collections import Counter
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
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    details: list[dict] = []
    errors: list[str] = []
    for seed in build.SEEDS:
        run = HERE / "runs" / f"j03-var01-seed{seed:02d}-accepted-20261001-01"
        result = validate.validate(run, seed)
        if not result["passed"]:
            errors.extend(f"seed {seed}: {message}" for message in result["differences"])
        details.append({
            "seed": seed, "run_id": run.name,
            "input_sha256": sha(run / "input.json"),
            "invocation_sha256": sha(run / "invocation.json"),
            "closure_sha256": sha(run / "closure.json"),
            "validation_sha256": sha(run / "validation.json"),
            "sample_preparation_hours": result["sample_preparation_hours"],
            "report_preparation_hours": result["report_preparation_hours"],
            "flight_hours": result["flight_hours"],
            "raw_file_count": len(json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))["raw"]),
        })
    samples = [item["sample_preparation_hours"] for item in details]
    expected = contract["expected_observation"]
    frequencies = dict(sorted(Counter(samples).items()))
    if samples != expected["frozen_preparation_hours_by_seed"]:
        errors.append("accepted preparation durations differ from frozen 32-seed diagnostic panel")
    if {str(k): v for k, v in frequencies.items()} != expected["frozen_frequencies"]:
        errors.append("preparation-duration frequencies differ from frozen panel")
    if len(samples) != 32 or not set(samples) == {0.25, 0.75}:
        errors.append("panel lacks the two observed preparation durations")
    if statistics.mean(samples) != expected["frozen_sample_mean"]:
        errors.append("panel sample mean differs")
    if abs(statistics.variance(samples) - expected["frozen_sample_variance"]) > 1e-12:
        errors.append("panel sample variance differs")
    result = {
        "schema": "simlox-j03-var01-time-two-point-author-panel/v1",
        "case_id": "J03", "variant_id": "J03.var01", "version": "1.0.0",
        "passed": not errors, "differences": errors, "runs": details,
        "sample_statistics": {
            "count": len(samples), "minimum": min(samples), "maximum": max(samples),
            "frequencies": {str(k): v for k, v in frequencies.items()},
            "mean": statistics.mean(samples),
            "sample_variance": statistics.variance(samples),
            "quarter_hour_seeds": [item["seed"] for item in details if item["sample_preparation_hours"] == 0.25],
            "three_quarter_hour_seeds": [item["seed"] for item in details if item["sample_preparation_hours"] == 0.75],
        },
        "raw_seal_count": sum(item["raw_file_count"] for item in details),
        "scope": "32 fixed seeds; descriptive observations only, no population-law inference",
    }
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    OUTPUT.parent.mkdir(exist_ok=True)
    if OUTPUT.exists() and OUTPUT.read_bytes() != raw:
        raise ValueError("frozen author panel result differs")
    if not OUTPUT.exists():
        OUTPUT.write_bytes(raw)
    print(json.dumps({"passed": result["passed"], "differences": errors,
                      "statistics": result["sample_statistics"],
                      "raw_seals": result["raw_seal_count"]}))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
