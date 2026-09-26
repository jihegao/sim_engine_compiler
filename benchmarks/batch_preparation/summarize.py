#!/usr/bin/env python3
"""Summarize paired batch-preparation records without hiding noisy cells."""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import statistics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("records", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.records.read_text().splitlines() if line]
    grouped: dict[tuple, dict[int, dict[str, dict]]] = defaultdict(lambda: defaultdict(dict))
    for row in rows:
        key = (row["case"], row["arm"], row["level"], row["samples"], row["threads"])
        grouped[key][row["repeat"]][row["variant"]] = row
    summary = []
    for key, repeats in sorted(grouped.items()):
        pairs = [repeats[index] for index in sorted(repeats)]
        if any(set(pair) != {"baseline", "candidate"} for pair in pairs):
            raise ValueError(f"incomplete pair: {key}")
        phase_report = "phases" in pairs[0]["baseline"]
        metric_name = "end_to_end_batch_ns" if phase_report else "process_wall_ns"
        def metric(row: dict) -> int:
            return row["phases"][metric_name] if phase_report else row[metric_name]
        before = [metric(pair["baseline"]) for pair in pairs]
        after = [metric(pair["candidate"]) for pair in pairs]
        gains = [1 - candidate / baseline for baseline, candidate in zip(before, after)]
        memory_before = [pair["baseline"]["peak_rss_bytes"] for pair in pairs]
        memory_after = [pair["candidate"]["peak_rss_bytes"] for pair in pairs]
        memory_ratio = [candidate / baseline for baseline, candidate in zip(memory_before, memory_after)]
        phases = {}
        if phase_report:
            phases = {
                name: {
                    "baseline_median_ns": statistics.median(pair["baseline"]["phases"][name] for pair in pairs),
                    "candidate_median_ns": statistics.median(pair["candidate"]["phases"][name] for pair in pairs),
                }
                for name in pairs[0]["baseline"]["phases"]
            }
        summary.append({
            "case": key[0], "arm": key[1], "level": key[2],
            "samples": key[3], "threads": key[4], "pairs": len(pairs),
            "metric_name": metric_name,
            "baseline_median_end_to_end_ns": statistics.median(before),
            "candidate_median_end_to_end_ns": statistics.median(after),
            "paired_gain_percent": [100 * gain for gain in gains],
            "median_paired_gain_percent": 100 * statistics.median(gains),
            "positive_pairs": sum(gain > 0 for gain in gains),
            "baseline_median_peak_rss_bytes": statistics.median(memory_before),
            "candidate_median_peak_rss_bytes": statistics.median(memory_after),
            "median_paired_memory_ratio": statistics.median(memory_ratio),
            "memory_regression_pairs": sum(ratio > 1.05 for ratio in memory_ratio),
            "adoption_gate": len(pairs) >= 6 and all(gain > 0 for gain in gains)
                             and statistics.median(gains) >= 0.05
                             and not (statistics.median(memory_ratio) > 1.05
                                      and sum(ratio > 1.05 for ratio in memory_ratio) >= 5),
            "phases": phases,
        })
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    for row in summary:
        if row["case"] == "f35" and row["level"] == "summary":
            print(row["case"], row["arm"], row["samples"], row["threads"],
                  f"{row['median_paired_gain_percent']:.2f}%",
                  f"{row['positive_pairs']}/{row['pairs']}",
                  f"RSS x{row['median_paired_memory_ratio']:.3f}",
                  "gate" if row["adoption_gate"] else "no gate")


if __name__ == "__main__":
    main()
