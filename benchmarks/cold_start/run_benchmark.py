#!/usr/bin/env python3
"""Benchmark Python lowering against Rust AOT lowering and binary Plan cache."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import tempfile
import time

from sim_engine_compiler.compiler import compile_aircraft_support


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = (
    ROOT
    / "tests"
    / "fixtures"
    / "spare_mvp"
    / "f35-43day-5352a0d"
    / "simulation-inputs.json"
)
DEFAULT_PLAN = DEFAULT_INPUT.with_name("execution-plan.json")
DEFAULT_BINARY = ROOT / "rust" / "compiler" / "target" / "release" / "sim-engine-compiler-aot"


def median(values: list[float | int]) -> float:
    return float(statistics.median(values))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--expected-plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--compiler", type=Path, default=DEFAULT_BINARY)
    parser.add_argument("--project-json", type=Path)
    parser.add_argument(
        "--adapter-contract-version",
        default="spare-mvp-5352a0d/aircraft-support-v1-project+input",
    )
    parser.add_argument("--warmups", type=int, default=3)
    parser.add_argument("--repeats", type=int, default=30)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.warmups < 0 or args.repeats < 1:
        parser.error("warmups must be non-negative and repeats must be positive")

    build_command = [
        "cargo",
        "build",
        "--release",
        "--manifest-path",
        "rust/compiler/Cargo.toml",
    ]
    if vendor_dir := os.environ.get("CARGO_VENDOR_DIR"):
        build_command.extend(
            [
                "--offline",
                "--config",
                'source.crates-io.replace-with="vendored-sources"',
                "--config",
                f'source.vendored-sources.directory="{vendor_dir}"',
            ]
        )
    subprocess.run(
        build_command,
        cwd=ROOT,
        check=True,
    )
    inputs = json.loads(args.input.read_text())
    expected_plan = json.loads(args.expected_plan.read_text())
    expected_plan["semantic_profile"] = "event-time-v2"
    expected_fingerprint = hashlib.sha256(
        json.dumps(
            expected_plan, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()

    for _ in range(args.warmups):
        plan = compile_aircraft_support(inputs, semantic_profile="event-time-v2")
        if plan.fingerprint != expected_fingerprint:
            raise AssertionError("Python warmup plan fingerprint drifted")

    python_compile_ns: list[int] = []
    for _ in range(args.repeats):
        started = time.perf_counter_ns()
        plan = compile_aircraft_support(inputs, semantic_profile="event-time-v2")
        python_compile_ns.append(time.perf_counter_ns() - started)
        if json.loads(json.dumps(plan.to_dict())) != expected_plan:
            raise AssertionError("Python plan differs from checked-in fixture")

    rust_miss: list[dict] = []
    rust_miss_with_run: list[dict] = []
    rust_hit: list[dict] = []
    rust_hit_with_run: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="sim-engine-cold-start-") as temporary:
        temporary = Path(temporary)

        def invoke(cache_dir: Path, index: int, *, run: bool = False) -> dict:
            command = [
                str(args.compiler),
                str(args.input),
                str(temporary / f"plan-{index}.seplan"),
                "--cache-dir",
                str(cache_dir),
            ]
            if args.project_json:
                command.extend(
                    [
                        "--project-json",
                        str(args.project_json),
                        "--adapter-contract-version",
                        args.adapter_contract_version,
                    ]
                )
            if run:
                command.extend(
                    [
                        "--run-output",
                        str(temporary / f"result-{index}.json"),
                        "--observation-level",
                        "summary",
                    ]
                )
            started = time.perf_counter_ns()
            completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=True)
            process_wall_ns = time.perf_counter_ns() - started
            row = json.loads(completed.stdout)
            row["process_wall_ns"] = process_wall_ns
            if row["plan_fingerprint"] != expected_fingerprint:
                raise AssertionError("Rust plan fingerprint differs from checked-in fixture")
            return row

        for index in range(args.warmups):
            invoke(temporary / f"warmup-miss-{index}", -100 - index)

        for index in range(args.repeats):
            row = invoke(temporary / f"miss-{index}", index)
            if row["cache_hit"]:
                raise AssertionError("cold compile unexpectedly hit cache")
            rust_miss.append(row)

        for index in range(args.warmups):
            invoke(temporary / f"warmup-miss-run-{index}", 500 + index, run=True)
        for index in range(args.repeats):
            row = invoke(temporary / f"miss-run-{index}", 600 + index, run=True)
            if row["cache_hit"]:
                raise AssertionError("cold execution unexpectedly hit cache")
            rust_miss_with_run.append(row)

        shared_cache = temporary / "shared-cache"
        invoke(shared_cache, -1)
        for index in range(args.repeats):
            row = invoke(shared_cache, 1000 + index)
            if not row["cache_hit"]:
                raise AssertionError("warm compile unexpectedly missed cache")
            rust_hit.append(row)

        for index in range(args.warmups):
            invoke(shared_cache, 2000 + index, run=True)
        for index in range(args.repeats):
            row = invoke(shared_cache, 3000 + index, run=True)
            if not row["cache_hit"]:
                raise AssertionError("cached execution unexpectedly missed cache")
            rust_hit_with_run.append(row)

    def stage_medians(rows: list[dict]) -> dict[str, float]:
        keys = rows[0]["timing_ns"]
        return {
            **{key: median([row["timing_ns"][key] for row in rows]) for key in keys},
            "process_wall": median([row["process_wall_ns"] for row in rows]),
        }

    report = {
        "status": "passed",
        "scope": (
            "fixed Project fingerprint cache lookup before Adapter; Rust build, Adapter and Project export excluded"
            if args.project_json
            else "fixed canonical inputs; Rust build excluded; adapter and Project export excluded"
        ),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "logical_cpus": os.cpu_count(),
        "python": platform.python_version(),
        "rustc": subprocess.check_output(["rustc", "--version"], text=True).strip(),
        "cargo": subprocess.check_output(["cargo", "--version"], text=True).strip(),
        "git_commit": os.environ.get("SIM_ENGINE_SOURCE_COMMIT")
        or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "input": str(args.input),
        "input_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
        "project_json": str(args.project_json) if args.project_json else None,
        "project_json_sha256": (
            hashlib.sha256(args.project_json.read_bytes()).hexdigest()
            if args.project_json
            else None
        ),
        "adapter_contract_version": args.adapter_contract_version if args.project_json else None,
        "expected_plan_fingerprint": expected_fingerprint,
        "compiler_sha256": hashlib.sha256(args.compiler.read_bytes()).hexdigest(),
        "warmups": args.warmups,
        "repeats": args.repeats,
        "median_ns": {
            "python_compile": median(python_compile_ns),
            "rust_cache_miss": stage_medians(rust_miss),
            "rust_cache_miss_with_summary_run": stage_medians(rust_miss_with_run),
            "rust_cache_hit": stage_medians(rust_hit),
            "rust_cache_hit_with_summary_run": stage_medians(rust_hit_with_run),
        },
        "raw": {
            "python_compile_ns": python_compile_ns,
            "rust_cache_miss": rust_miss,
            "rust_cache_miss_with_summary_run": rust_miss_with_run,
            "rust_cache_hit": rust_hit,
            "rust_cache_hit_with_summary_run": rust_hit_with_run,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report["median_ns"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
