#!/usr/bin/env python3
"""Reproducible exploratory benchmarks; semantic equality precedes every timing.

The independent reference intentionally scans. It is a correctness oracle and
an algorithmic baseline, not an optimized commercial simulator comparison.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path

import generic
import reference

HERE = Path(__file__).resolve().parent


def semantic(result):
    return {k: v for k, v in result.items() if k != "diagnostics"}


def measured(call):
    before = time.perf_counter_ns()
    answer = call()
    return answer, time.perf_counter_ns() - before


def describe(ns):
    ordered = sorted(ns)
    return {"raw_ns": ns, "median_ms": statistics.median(ns) / 1e6,
            "min_ms": min(ns) / 1e6, "max_ms": max(ns) / 1e6,
            "q1_ms": ordered[len(ordered) // 4] / 1e6,
            "q3_ms": ordered[3 * len(ordered) // 4] / 1e6}


def workload(pools=16, per_pool=8, assets=0, horizon=1000, sparse=False):
    return {
        "schema": "business/v1", "profile": "ir-native-event-v1",
        "domain": "production", "model_id": "benchmark", "revision": "1",
        "time_unit": "tick", "horizon": horizon,
        "machines": [{"id": f"unused-{i}"} for i in range(assets)],
        "resources": [{"id": f"pool-{i}", "kind": "capacity", "initial": 1}
                      for i in range(pools)],
        "jobs": [{"id": f"job-{pool}-{j}", "release": (j * 10 if sparse else 0),
                  "duration": [1, 3], "needs": {f"pool-{pool}": 1}}
                 for pool in range(pools) for j in range(per_pool)],
    }


def rust_call(binary, plan, seeds, trace=False, threads=1):
    request = {"plan": plan.to_dict(), "seeds": seeds, "trace": trace,
               "threads": threads}
    encoded = json.dumps(request, separators=(",", ":"))
    output, elapsed = measured(lambda: subprocess.run(
        [str(binary)], input=encoded, text=True, capture_output=True, check=True))
    return json.loads(output.stdout), elapsed


def run_benchmark(binary, repeats=7):
    specs = [
        ("sparse_horizon_1000", dict(pools=1, per_pool=32, sparse=True, horizon=1000)),
        ("sparse_horizon_1b", dict(pools=1, per_pool=32, sparse=True, horizon=10**9)),
        ("unused_assets_16", dict(pools=4, per_pool=8, assets=16)),
        ("unused_assets_10000", dict(pools=4, per_pool=8, assets=10000)),
        ("local_pools_16x8", dict(pools=16, per_pool=8)),
        ("local_pools_64x16", dict(pools=64, per_pool=16)),
        ("global_pool_1x256", dict(pools=1, per_pool=256, horizon=2000)),
    ]
    records = []
    for name, kwargs in specs:
        raw = workload(**kwargs)
        build_times = {key: [] for key in ("business_validate", "core_lower", "plan_compile")}
        for _ in range(repeats):
            business, dt = measured(lambda: generic.compile_business(raw))
            build_times["business_validate"].append(dt)
            core, dt = measured(lambda: generic.lower_core(business))
            build_times["core_lower"].append(dt)
            plan, dt = measured(lambda: generic.compile_plan(core))
            build_times["plan_compile"].append(dt)
        expected = reference.run_plan(plan, seed=7, trace=False)
        actual = generic.run_plan(plan, seed=7, trace=False)
        assert semantic(actual) == semantic(expected), name
        rs, _ = rust_call(binary, plan, [7])
        assert semantic(rs["results"][0]) == semantic(expected), name + " Rust"
        py_ns, py_init, py_exec, ref_ns, rs_ns, rs_init, rs_parse, rs_e2e, cold_ns = [], [], [], [], [], [], [], [], []
        # Warm each engine once, then alternate Python order. Rust timings are
        # in-process execution durations; separate CLI end-to-end includes IPC.
        generic.run_plan(plan, seed=7, trace=False)
        reference.run_plan(plan, seed=7, trace=False)
        for repeat in range(repeats):
            actions = [(generic.run_plan, py_ns), (reference.run_plan, ref_ns)]
            if repeat % 2:
                actions.reverse()
            for function, samples in actions:
                if function is generic.run_plan:
                    runtime, init_dt = measured(lambda: generic.Runtime(plan, seed=7, trace=False))
                    result, exec_dt = measured(runtime.run)
                    py_init.append(init_dt)
                    py_exec.append(exec_dt)
                    dt = init_dt + exec_dt
                else:
                    result, dt = measured(lambda: function(plan, seed=7, trace=False))
                assert semantic(result) == semantic(expected)
                samples.append(dt)
            result, elapsed = rust_call(binary, plan, [7])
            assert semantic(result["results"][0]) == semantic(expected)
            rs_e2e.append(elapsed)
            # Adapted to the kernel's documented per-sample measurement shape.
            timing = result["timings"][0]
            rs_ns.append(timing["execution_ns"])
            rs_init.append(timing["initialization_ns"])
            rs_parse.append(result["parse_validate_ns"])
            cold, cold_dt = measured(lambda: rust_call(binary, generic.build_plan(raw), [7]))
            assert semantic(cold[0]["results"][0]) == semantic(expected)
            cold_ns.append(cold_dt)
        records.append({
            "name": name, "parameters": kwargs, "fingerprint": plan.to_dict()["fingerprint"],
            "counts": {"assets": len(raw["machines"]), "resources": len(raw["resources"]),
                       "processes": len(raw["jobs"]), "horizon": raw["horizon"]},
            "semantic_equal_three_engines": True,
            "compile": {k: describe(v) for k, v in build_times.items()},
            "python_indexed_init_and_execution": describe(py_ns),
            "python_indexed_initialization": describe(py_init),
            "python_indexed_execution": describe(py_exec),
            "python_reference_init_and_execution": describe(ref_ns),
            "rust_execution": describe(rs_ns), "rust_initialization": describe(rs_init),
            "rust_parse_validate": describe(rs_parse), "rust_cli_end_to_end": describe(rs_e2e),
            "cold_business_to_rust_result": describe(cold_ns),
            "python_indexed_counters": actual["diagnostics"],
            "reference_counters": expected["diagnostics"],
            "reference_to_indexed_ratio": statistics.median(ref_ns) / statistics.median(py_ns),
            "indexed_to_rust_init_exec_ratio": statistics.median(py_ns) /
                statistics.median([a + b for a, b in zip(rs_init, rs_ns)]),
        })
        print(name, "passed", flush=True)
    plan = generic.build_plan(workload(pools=16, per_pool=16))
    seeds = [0, 1, 7, 7] * 8
    batch = {"samples": len(seeds), "threads": {}}
    serial = None
    for threads in [1, 3]:
        wall, end_to_end = [], []
        for _ in range(repeats):
            answer, dt = rust_call(binary, plan, seeds, threads=threads)
            states = [semantic(x) for x in answer["results"]]
            if serial is None:
                serial = states
            assert states == serial
            wall.append(answer["batch_wall_ns"])
            end_to_end.append(dt)
        batch["threads"][str(threads)] = {"batch_wall": describe(wall), "cli_e2e": describe(end_to_end)}
    batch["stable_results_with_duplicate_seeds"] = True
    trace_tests = {}
    full = generic.run_plan(plan, seed=7, trace=True)
    summary = generic.run_plan(plan, seed=7, trace=False)
    assert {k: v for k, v in semantic(full).items() if k != "trace"} == {
        k: v for k, v in semantic(summary).items() if k != "trace"}
    observation_samples = {False: [], True: []}
    for repeat in range(repeats):
        for observation in ([False, True] if repeat % 2 == 0 else [True, False]):
            observation_samples[observation].append(measured(lambda: generic.run_plan(plan, seed=7, trace=observation))[1])
    for observation, ns in observation_samples.items():
        trace_tests[str(observation)] = describe(ns)
    return {
        "schema": "ir-validation-benchmark/v1", "recorded_unix": time.time(),
        "environment": {"python": sys.version, "platform": platform.platform(),
                        "cpu_count": os.cpu_count(), "cpu_model": next((line.split(':', 1)[1].strip()
                            for line in Path('/proc/cpuinfo').read_text().splitlines()
                            if line.startswith('model name')), 'unknown'),
                        "rust_binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest()},
        "method": {"repeats": repeats, "warmups": 1, "observation": "trace off unless specified",
                   "notes": ["Exploratory shared-host timings; not production or vendor comparisons.",
                             "Python wall times include initialization and result construction.",
                             "Rust execution includes result construction; CLI e2e includes process/JSON/IPC.",
                             "CLI timing excludes caller-side JSON encoding/decoding and compilation; cold_business_to_rust_result includes them.",
                             "core_lower defensively revalidates Business IR; compiler phase costs are inclusive, not disjoint passes.",
                             "Reference is deliberately scanning and used as algorithmic ablation."]},
        "workloads": records, "batch": batch, "trace": trace_tests,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=7)
    parser.add_argument("--binary", type=Path, default=HERE / "rust_kernel/target/release/ir-validation-kernel")
    parser.add_argument("--output", type=Path, default=HERE / "results/benchmark_results.json")
    args = parser.parse_args()
    output = run_benchmark(args.binary, args.repeats)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    print(args.output)
