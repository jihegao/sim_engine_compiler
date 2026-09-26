#!/usr/bin/env python3
"""Measure current three-layer/MLIR Plan compilation separately from runtime."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
FROZEN = ROOT / "benchmarks/dependency_dispatch/results/macos-arm64-20260925"
CASES = {
    "f35": (FROZEN / "f35/inputs.json", FROZEN / "f35/event-time-v2/indexed-plan.json"),
    "synthetic-capacity-16": (FROZEN / "synthetic-capacity-16/inputs.json",
                              FROZEN / "synthetic-capacity-16/event-time-v2/indexed-plan.json"),
    "synthetic-remote-16": (FROZEN / "synthetic-remote-16/inputs.json",
                            FROZEN / "synthetic-remote-16/event-time-v2/indexed-plan.json"),
    "shared-remote-pools": (ROOT / "benchmarks/batch_preparation/fixtures/shared-remote-pools/inputs.json",
                            ROOT / "benchmarks/batch_preparation/fixtures/shared-remote-pools/indexed-plan.json"),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--plugin-dir", type=Path, required=True)
    parser.add_argument("--mlir-opt", type=Path, required=True)
    parser.add_argument("--case-dir", type=Path,
                        help="frozen J35 inputs.json and indexed-plan.json")
    parser.add_argument("--cases", help="comma-separated cases; defaults to built-in cases")
    parser.add_argument("--repeats", type=int, default=6)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("repeats must be positive")
    cases = dict(CASES)
    if args.case_dir:
        case_dir = args.case_dir.resolve()
        cases["j35"] = (case_dir / "inputs.json", case_dir / "indexed-plan.json")
    selected = args.cases.split(",") if args.cases else list(CASES)
    if any(name not in cases for name in selected):
        parser.error("unknown case or J35 requires --case-dir")
    cases = {name: cases[name] for name in selected}
    plugin = args.plugin_dir.resolve() / "SimResourceDispatchPass.so"
    mlir_opt = args.mlir_opt.resolve()
    identity = {
        "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                        capture_output=True, text=True, check=True).stdout.strip(),
        "platform": platform.platform(), "python": sys.version,
        "cpu_count": os.cpu_count(),
        "plugin_sha256": digest(plugin), "mlir_opt_sha256": digest(mlir_opt),
        "warmups": 1, "repeats": args.repeats,
        "boundary": "compiler Python process wall includes canonical read, three-layer lowering, MLIR pass and Plan write; excludes plugin/binary build",
        "cases": {name: {"input_sha256": digest(source), "plan_sha256": digest(frozen)}
                  for name, (source, frozen) in cases.items()},
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "identity.json").write_text(json.dumps(identity, indent=2) + "\n")
    rows = []
    with tempfile.TemporaryDirectory(prefix="sim-batch-prep-compile-") as temporary:
        plan = Path(temporary) / "plan.json"
        for name, (source, frozen) in cases.items():
            for repeat in range(-1, args.repeats):
                command = [sys.executable, str(ROOT / "scripts/compile_mlir_execution_plan.py"),
                           str(source), str(plan), "--semantic-profile", "event-time-v2",
                           "--plugin-dir", str(args.plugin_dir.resolve()),
                           "--mlir-opt", str(mlir_opt)]
                started = time.perf_counter_ns()
                result = subprocess.run(command, cwd=ROOT, text=True,
                                        capture_output=True, check=True)
                wall_ns = time.perf_counter_ns() - started
                if plan.read_bytes() != frozen.read_bytes():
                    raise AssertionError(f"compiled Plan changed: {name}")
                if repeat >= 0:
                    row = {"case": name, "repeat": repeat, "process_wall_ns": wall_ns,
                           "compiler": json.loads(result.stdout)}
                    rows.append(row)
                    (args.output / "records.json").write_text(json.dumps(rows, indent=2) + "\n")
                    print(name, repeat, round(wall_ns / 1e6, 3), flush=True)


if __name__ == "__main__":
    main()
