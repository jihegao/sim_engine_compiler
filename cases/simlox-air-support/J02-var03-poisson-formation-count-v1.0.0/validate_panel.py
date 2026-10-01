"""Replay all 32 accepted J02.var03 runs and freeze bounded count statistics."""
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
        run = HERE / "runs" / f"j02-var03-seed{seed:02d}-accepted-20261001-01"
        result = validate.validate(run, seed)
        if not result["passed"]:
            errors.extend(f"seed {seed}: {message}" for message in result["differences"])
        details.append({
            "seed": seed, "run_id": run.name,
            "input_sha256": sha(run / "input.json"),
            "invocation_sha256": sha(run / "invocation.json"),
            "closure_sha256": sha(run / "closure.json"),
            "validation_sha256": sha(run / "validation.json"),
            "realized_count": result["realized_count"],
            "mission_start_hours": [item[0] for item in result["mission_starts"]],
            "flight_hours": result["flight_hours"],
            "raw_file_count": len(json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))["raw"]),
        })
    counts = [item["realized_count"] for item in details]
    expected = contract["expected_observation"]
    frequencies = dict(sorted(Counter(counts).items()))
    if counts != expected["frozen_counts_by_seed"]:
        errors.append("accepted counts differ from frozen 32-seed diagnostic panel")
    if {str(k): v for k, v in frequencies.items()} != expected["frozen_frequencies"]:
        errors.append("count frequencies differ from frozen panel")
    if len(counts) != 32 or not set(counts) == {0, 1, 2, 3, 4, 5}:
        errors.append("panel lacks the six observed count outcomes")
    if statistics.mean(counts) != expected["frozen_sample_mean"]:
        errors.append("panel sample mean differs")
    if abs(statistics.variance(counts) - expected["frozen_sample_variance"]) > 1e-12:
        errors.append("panel sample variance differs")
    result = {
        "schema": "simlox-j02-var03-poisson-count-author-panel/v1",
        "case_id": "J02", "variant_id": "J02.var03", "version": "1.0.0",
        "passed": not errors, "differences": errors, "runs": details,
        "sample_statistics": {
            "count": len(counts), "minimum": min(counts), "maximum": max(counts),
            "frequencies": {str(k): v for k, v in frequencies.items()},
            "mean": statistics.mean(counts),
            "sample_variance": statistics.variance(counts),
            "zero_count_seeds": [item["seed"] for item in details if item["realized_count"] == 0],
            "five_count_seeds": [item["seed"] for item in details if item["realized_count"] == 5],
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
