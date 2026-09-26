#!/usr/bin/env python3
"""Accept the frozen J35 Plan before collecting runtime timing evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from sim_engine_compiler.reference.conformance import first_divergence


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str], root: Path) -> None:
    process = subprocess.run(command, cwd=root, text=True, capture_output=True)
    if process.returncode:
        raise RuntimeError(f"{command}: {process.stderr}")


def same(left: dict, right: dict, label: str, *, ignore_fingerprint: bool = False) -> None:
    left = left.copy()
    right = right.copy()
    if ignore_fingerprint:
        left.pop("plan_fingerprint")
        right.pop("plan_fingerprint")
    difference = first_divergence(left, right, float_rel_tol=2e-15, float_abs_tol=1e-12)
    if difference:
        raise AssertionError(
            f"{label}: {difference.path}: {difference.expected!r} != {difference.actual!r}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--legacy-plan", type=Path, required=True)
    parser.add_argument("--scan-plan", type=Path, required=True)
    parser.add_argument("--indexed-plan", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.runtime_root.resolve()
    plans = {
        "legacy": args.legacy_plan.resolve(),
        "scan": args.scan_plan.resolve(),
        "cache": args.indexed_plan.resolve(),
        "candidates": args.indexed_plan.resolve(),
    }
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    binary = root / "rust/runtime/target/release/sim-engine-runtime"
    python = root / ".venv/bin/python"
    rows = []
    for seed in (0, 1, 7):
        reference_path = output / f"reference-{seed}.json"
        run([str(python), str(root / "scripts/run_reference_plan.py"),
             str(plans["legacy"]), str(reference_path), "--seed", str(seed)], root)
        reference = json.loads(reference_path.read_text())
        full_results = {}
        for arm, plan in plans.items():
            path = output / f"{arm}-full-{seed}.json"
            command = [str(binary), str(plan), str(path), "--seed", str(seed),
                       "--observation-level", "full"]
            if arm == "candidates":
                command.append("--dependency-dispatch")
            run(command, root)
            full_results[arm] = json.loads(path.read_text())
            rows.append({"seed": seed, "arm": arm, "level": "full",
                         "sha256": sha256(path), "bytes": path.stat().st_size,
                         "events": len(full_results[arm]["trace"])})
        same(reference, full_results["legacy"], f"reference/legacy seed={seed}")
        for arm in ("scan", "cache", "candidates"):
            same(full_results["legacy"], full_results[arm],
                 f"legacy/{arm} seed={seed}", ignore_fingerprint=True)
        for arm in ("scan", "cache", "candidates"):
            path = output / f"{arm}-summary-{seed}.json"
            command = [str(binary), str(plans[arm]), str(path), "--seed", str(seed),
                       "--observation-level", "summary"]
            if arm == "candidates":
                command.append("--dependency-dispatch")
            run(command, root)
            summary = json.loads(path.read_text())
            if summary["trace"] != []:
                raise AssertionError(f"Summary trace is not empty: {arm} seed={seed}")
            full = full_results[arm].copy()
            full["trace"] = []
            same(full, summary, f"Full/Summary {arm} seed={seed}")
            rows.append({"seed": seed, "arm": arm, "level": "summary",
                         "sha256": sha256(path), "bytes": path.stat().st_size})
        print(f"J35 seed {seed}: reference/legacy/O5/three arms/Full/Summary match", flush=True)
    report = {
        "runtime_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                                         text=True, capture_output=True, check=True).stdout.strip(),
        "binary_sha256": sha256(binary),
        "plans": {name: sha256(path) for name, path in plans.items()},
        "seeds": [0, 1, 7],
        "acceptance": "complete RunResult first-divergence comparison, float rel=2e-15 abs=1e-12; Summary excludes trace only",
        "rows": rows,
    }
    (output / "validation.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
