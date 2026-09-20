#!/usr/bin/env python3
"""Run the formal Stage C segmented Python/Rust benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable, TypeVar

import sim_engine_compiler
from sim_engine_compiler.ir.plan import ExecutionPlan
from sim_engine_compiler.reference import SimpyReferenceRuntime
from sim_engine_compiler.reference.conformance import first_divergence


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "rust" / "runtime" / "Cargo.toml"
DEFAULT_PLAN = (
    ROOT
    / "tests"
    / "fixtures"
    / "spare_mvp"
    / "f35-43day-5352a0d"
    / "execution-plan.json"
)
T = TypeVar("T")


def timed(call: Callable[[], T]) -> tuple[T, int]:
    started = time.perf_counter_ns()
    value = call()
    return value, time.perf_counter_ns() - started


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def peak_rss_bytes() -> int:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def median(values: list[int]) -> int:
    return int(statistics.median(values))


def benchmark_python(
    plan_path: Path, seeds: list[int], warmups: int, repeats: int
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    warm_plan = ExecutionPlan.from_dict(json.loads(plan_path.read_text()))
    for _ in range(warmups):
        SimpyReferenceRuntime(warm_plan, seed=seeds[0]).run()

    records: list[dict[str, Any]] = []
    last_results: list[dict[str, Any]] = []
    for repeat in range(repeats):
        plan_bytes, plan_read_ns = timed(plan_path.read_bytes)
        plan, plan_parse_validate_ns = timed(
            lambda: ExecutionPlan.from_dict(json.loads(plan_bytes))
        )
        samples: list[dict[str, Any]] = []
        results: list[dict[str, Any]] = []
        for sample_index, seed in enumerate(seeds):
            runtime, initialization_ns = timed(
                lambda seed=seed: SimpyReferenceRuntime(plan, seed=seed)
            )
            result, execution_ns = timed(runtime.run)
            encoded, serialization_ns = timed(
                lambda result=result: json.dumps(
                    result,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            )
            samples.append(
                {
                    "sample_index": sample_index,
                    "seed": seed,
                    "run_state_initialization_ns": initialization_ns,
                    "execution_ns": execution_ns,
                    "serialization_ns": serialization_ns,
                    "result_bytes": len(encoded),
                    "result_sha256": sha256_bytes(encoded),
                }
            )
            results.append(result)
        records.append(
            {
                "repeat": repeat,
                "plan_read_ns": plan_read_ns,
                "plan_parse_validate_ns": plan_parse_validate_ns,
                "samples": samples,
            }
        )
        last_results = results
    report = {
        "runtime": "python-reference",
        "python": sys.version,
        "simpy": __import__("simpy").__version__,
        "warmups": warmups,
        "repeats": repeats,
        "records": records,
        "process_peak_rss_bytes": peak_rss_bytes(),
    }
    return report, last_results


def parse_time_peak_rss(stderr: str) -> int | None:
    for line in stderr.splitlines():
        stripped = line.strip()
        if stripped.endswith("maximum resident set size"):
            try:
                return int(stripped.split(maxsplit=1)[0])
            except ValueError:
                return None
    return None


def run_native_report(
    binary: Path,
    plan: Path,
    seeds: list[int],
    threads: int,
    warmups: int,
    repeats: int,
    destination: Path,
) -> dict[str, Any]:
    command = [
        str(binary),
        str(plan),
        str(destination),
        "--seeds",
        ",".join(str(seed) for seed in seeds),
        "--worker-threads",
        str(threads),
        "--warmups",
        str(warmups),
        "--repeats",
        str(repeats),
    ]
    if sys.platform == "darwin" and Path("/usr/bin/time").exists():
        completed = subprocess.run(
            ["/usr/bin/time", "-l", *command],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        peak_rss = parse_time_peak_rss(completed.stderr)
    else:
        subprocess.run(command, cwd=ROOT, check=True)
        peak_rss = None
    report = json.loads(destination.read_text())
    report["process_peak_rss_bytes"] = peak_rss
    return report


def validate_binding(
    plan: Path,
    seeds: list[int],
    thread_counts: list[int],
    expected: list[dict[str, Any]],
    repeats: int,
) -> dict[str, Any]:
    calls: list[dict[str, Any]] = []
    baseline_samples: list[dict[str, Any]] | None = None
    all_conformant = True
    for threads in thread_counts:
        timings: list[int] = []
        latest: dict[str, Any] | None = None
        for _ in range(repeats):
            latest, elapsed_ns = timed(
                lambda threads=threads: sim_engine_compiler.run_batch(
                    plan, seeds, worker_threads=threads
                )
            )
            timings.append(elapsed_ns)
        assert latest is not None
        indexes = [sample["sample_index"] for sample in latest["samples"]]
        output_seeds = [sample["seed"] for sample in latest["samples"]]
        if indexes != list(range(len(seeds))) or output_seeds != seeds:
            raise AssertionError("native binding returned unstable sample order")
        if baseline_samples is None:
            baseline_samples = latest["samples"]
        elif latest["samples"] != baseline_samples:
            raise AssertionError("native sample results changed with worker thread count")
        divergences = [
            first_divergence(
                expected[index],
                sample["result"],
                float_rel_tol=2e-15,
                float_abs_tol=1e-12,
            )
            for index, sample in enumerate(latest["samples"])
        ]
        all_conformant = all_conformant and all(item is None for item in divergences)
        calls.append(
            {
                "worker_threads": latest["worker_threads"],
                "call_ns": timings,
                "median_call_ns": median(timings),
                "sample_indexes": indexes,
                "seeds": output_seeds,
                "python_reference_divergences": divergences,
            }
        )
    return {
        "native_available": sim_engine_compiler.native_available(),
        "calls": calls,
        "stable_input_order": True,
        "thread_invariant_samples": True,
        "python_reference_conformant": all_conformant,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seeds", default="0,1,7")
    parser.add_argument("--thread-counts", default="1,3")
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    args.plan = args.plan.resolve()
    args.output = args.output.resolve()
    seeds = [int(item) for item in args.seeds.split(",")]
    thread_counts = [int(item) for item in args.thread_counts.split(",")]
    if not seeds or not thread_counts or args.repeats < 1:
        raise SystemExit("seeds, thread-counts, and positive repeats are required")

    subprocess.run(
        [
            "cargo",
            "build",
            "--quiet",
            "--release",
            "--manifest-path",
            str(MANIFEST),
            "--bin",
            "stage-c-benchmark",
        ],
        cwd=ROOT,
        check=True,
    )
    binary = ROOT / "rust" / "runtime" / "target" / "release" / "stage-c-benchmark"
    python_report, python_results = benchmark_python(
        args.plan, seeds, args.warmups, args.repeats
    )
    with tempfile.TemporaryDirectory(prefix="stage-c-benchmark-") as tempdir:
        native_reports = [
            run_native_report(
                binary,
                args.plan,
                seeds,
                threads,
                args.warmups,
                args.repeats,
                Path(tempdir) / f"rust-{threads}.json",
            )
            for threads in thread_counts
        ]
    binding = validate_binding(
        args.plan, seeds, thread_counts, python_results, args.repeats
    )

    serial_hashes = {record["samples_sha256"] for record in native_reports[0]["records"]}
    all_hashes = {
        record["samples_sha256"]
        for report in native_reports
        for record in report["records"]
    }
    if len(serial_hashes) != 1 or len(all_hashes) != 1:
        raise AssertionError("native samples changed across repeats or thread counts")

    python_seed_zero = [
        record["samples"][0]["execution_ns"] for record in python_report["records"]
    ]
    rust_seed_zero = [
        record["phases"]["single_sample_execution_ns"]
        for record in native_reports[0]["records"]
    ]
    serial_batch = [
        record["phases"]["batch_execution_ns"]
        for record in native_reports[0]["records"]
    ]
    parallel_batch = [
        record["phases"]["batch_execution_ns"]
        for record in native_reports[-1]["records"]
    ]
    summary = {
        "python_single_execution_median_ns": median(python_seed_zero),
        "rust_single_execution_median_ns": median(rust_seed_zero),
        "rust_single_speedup_vs_python": median(python_seed_zero) / median(rust_seed_zero),
        "rust_serial_batch_median_ns": median(serial_batch),
        "rust_parallel_batch_median_ns": median(parallel_batch),
        "rust_parallel_speedup_vs_serial_batch": median(serial_batch)
        / median(parallel_batch),
    }

    source_paths = [
        ROOT / "rust" / "runtime" / "Cargo.lock",
        ROOT / "rust" / "runtime" / "src" / "batch.rs",
        ROOT / "rust" / "runtime" / "src" / "runtime.rs",
        ROOT / "src" / "sim_engine_compiler" / "native.py",
        Path(__file__),
    ]
    report = {
        "schema_version": "stage-c-formal-benchmark/v1",
        "generated_at_unix_seconds": int(time.time()),
        "environment": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "logical_cpus": os.cpu_count(),
            "python": sys.version,
            "git_revision": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
        },
        "plan": {
            "path": str(args.plan.relative_to(ROOT)),
            "bytes": args.plan.stat().st_size,
            "sha256": sha256_file(args.plan),
            "fingerprint": ExecutionPlan.from_dict(
                json.loads(args.plan.read_text())
            ).fingerprint,
        },
        "configuration": {
            "seeds": seeds,
            "thread_counts": thread_counts,
            "warmups": args.warmups,
            "repeats": args.repeats,
            "observation_level": "full result with sample_requests, trace, metrics, terminal_state",
        },
        "source_sha256": {
            str(path.relative_to(ROOT)): sha256_file(path) for path in source_paths
        },
        "python_reference": python_report,
        "rust_native": native_reports,
        "python_binding": binding,
        "validation": {
            "stable_across_repeats": len(serial_hashes) == 1,
            "stable_across_thread_counts": len(all_hashes) == 1,
            "python_reference_conformant": binding["python_reference_conformant"],
        },
        "summary": summary,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
