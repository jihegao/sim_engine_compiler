#!/usr/bin/env python3
"""Compare the J35 upstream model with the accepted Python Plan reference."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from sim_engine_compiler.reference.conformance import first_divergence
from tests.conformance.test_f35_reference import (
    CORE_METRICS,
    _business_timeline,
    _sample_projection,
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare(expected: object, actual: object, label: str) -> None:
    difference = first_divergence(expected, actual, float_rel_tol=2e-15,
                                  float_abs_tol=1e-12)
    if difference:
        raise AssertionError(
            f"{label}: {difference.path}: {difference.expected!r} != {difference.actual!r}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--spare-mvp-root", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--reference-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    runtime_root = args.runtime_root.resolve()
    spare_root = args.spare_mvp_root.resolve()
    inputs = args.inputs.resolve()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for seed in (0, 1, 7):
        oracle_path = output / f"oracle-{seed}.json"
        command = [str(spare_root / ".abm-mesa-test-env/bin/python"),
                   str(runtime_root / "scripts/run_spare_mvp_oracle.py"),
                   "--spare-mvp-root", str(spare_root), "--input", str(inputs),
                   "--seed", str(seed), "--output", str(oracle_path), "--compact"]
        process = subprocess.run(command, cwd=runtime_root, text=True,
                                 capture_output=True)
        if process.returncode:
            raise RuntimeError(f"{command}: {process.stderr}")
        oracle = json.loads(oracle_path.read_text())
        reference_path = args.reference_dir.resolve() / f"reference-{seed}.json"
        reference = json.loads(reference_path.read_text())
        # The upstream reporter uses null for an undefined 0/0 fill rate;
        # the Plan reporter uses the vacuous rate 1.0. Preserve and report
        # both raw values while comparing all defined metrics exactly.
        metric_keys = [key for key in CORE_METRICS if not (
            key == "spare_fill_rate" and oracle["metrics"]["spare_demand_total"] == 0
            and reference["metrics"]["spare_demand_total"] == 0)]
        compare({key: oracle["metrics"][key] for key in metric_keys},
                {key: reference["metrics"][key] for key in metric_keys},
                f"metrics seed={seed}")
        compare(oracle["terminal_state"], reference["terminal_state"],
                f"terminal/resource ledger seed={seed}")
        compare(_sample_projection(oracle["sample_requests"]),
                _sample_projection(reference["sample_requests"]),
                f"random requests seed={seed}")
        compare(_business_timeline(oracle["trace"]),
                _business_timeline(reference["trace"]),
                f"business trace seed={seed}")
        rows.append({"seed": seed, "oracle_sha256": sha256(oracle_path),
                     "reference_sha256": sha256(reference_path),
                     "spare_demand_total": oracle["metrics"]["spare_demand_total"],
                     "spare_fill_rate": {"upstream": oracle["metrics"]["spare_fill_rate"],
                                         "plan": reference["metrics"]["spare_fill_rate"]},
                     "oracle_events": len(oracle["trace"]),
                     "business_events": len(_business_timeline(oracle["trace"])),
                     "random_requests": len(oracle["sample_requests"])})
        print(f"J35 seed {seed}: upstream oracle and Plan reference match", flush=True)
    report = {
        "spare_mvp_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=spare_root,
                                           text=True, capture_output=True,
                                           check=True).stdout.strip(),
        "input_sha256": sha256(inputs),
        "comparison": "established business trace and random projections, defined core metrics, exact terminal/resource ledger; zero-demand spare_fill_rate is retained raw but excluded because upstream reports null and Plan reports 1.0; float rel=2e-15 abs=1e-12",
        "rows": rows,
    }
    (output / "oracle-validation.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
