#!/usr/bin/env python3
"""Validate and summarize the captured F35 43-day benchmark result."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path


SERIAL_ENGINES = {
    "AircraftSupportV1Model",
    "TriggeredModel",
    "CompiledModel",
    "SimpyProcessModel",
}
DAG_ENGINES = {"ParallelDAGModel", "SimpyDAGModel"}


def load_and_validate(path: Path) -> dict:
    report = json.loads(path.read_text())
    if report.get("status") != "passed":
        raise ValueError(f"benchmark status is {report.get('status')!r}")

    rows = report.get("rows") or []
    engines = {row["engine"] for row in rows}
    expected = SERIAL_ENGINES | DAG_ENGINES
    if engines != expected:
        raise ValueError(f"unexpected engines: {sorted(engines ^ expected)}")

    counts = Counter((row["engine"], row["seed"]) for row in rows)
    seeds = {row["seed"] for row in rows}
    if seeds != {0, 1, 7} or any(counts[(engine, seed)] != 2 for engine in expected for seed in seeds):
        raise ValueError(f"expected two repetitions for engines × seeds 0,1,7; got {counts}")

    differences = [
        item
        for item in report.get("comparisons") or []
        if item.get("core_difference") or item.get("terminal_state_difference")
    ]
    if differences:
        raise ValueError(f"semantic differences found: {differences[0]}")

    measured = {
        engine: statistics.median(row["total_seconds"] for row in rows if row["engine"] == engine)
        for engine in expected
    }
    recorded = report.get("median_total_seconds") or {}
    for engine, value in measured.items():
        if value != recorded.get(engine):
            raise ValueError(f"median mismatch for {engine}: {value} != {recorded.get(engine)}")
    return report


def markdown(report: dict) -> str:
    medians = report["median_total_seconds"]
    speedups = report["speedup_vs_tick"]
    baseline = medians["AircraftSupportV1Model"]
    rows = [
        ("分钟基线", "AircraftSupportV1Model", "串行兼容"),
        ("状态触发", "TriggeredModel", "串行兼容"),
        ("编译结构", "CompiledModel", "串行兼容"),
        ("独立 SimPy 调度", "SimpyProcessModel", "串行兼容"),
        ("并行 DAG 直接调度", "ParallelDAGModel", "行为实验"),
        ("并行 DAG + SimPy", "SimpyDAGModel", "行为实验"),
    ]
    output = [
        f"- upstream commit: `{report['commit']}`",
        f"- canonical inputs SHA-256: `{report['inputs_sha256']}`",
        f"- platform: `{report['platform']}`",
        f"- Python / SimPy: `{report['python'].split()[0]}` / `{report['simpy']}`",
        f"- Adapter / shared IR compile: {report['adapter_seconds']:.4f}s / {report['ir_compile_seconds']:.4f}s",
        f"- formal rows / semantic comparisons / warm-up invariant checks: "
        f"{len(report['rows'])} / {len(report['comparisons'])} / "
        f"{sum(item['checks'] for item in report['invariants']):,}",
        "",
        "| 路线 | 中位总耗时 | 相对分钟基线 | 语义范围 |",
        "|---|---:|---:|---|",
    ]
    output.extend(
        f"| {label} | {medians[key]:.3f}s | {speedups[key]:.2f}× | {scope} |"
        for label, key, scope in rows
    )
    simpy_delta = (medians["SimpyProcessModel"] / medians["CompiledModel"] - 1.0) * 100.0
    output.extend(
        [
            "",
            f"串行 SimPy 相对编译结构耗时差：{simpy_delta:+.2f}%（正值表示更慢）。",
            f"分钟基线中位耗时：{baseline:.6f}s。",
        ]
    )
    return "\n".join(output) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "result",
        nargs="?",
        type=Path,
        default=Path(__file__).parent / "results" / "results-43day-20260920.json",
    )
    args = parser.parse_args()
    print(markdown(load_and_validate(args.result)), end="")


if __name__ == "__main__":
    main()
