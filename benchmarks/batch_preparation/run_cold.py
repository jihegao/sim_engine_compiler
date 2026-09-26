#!/usr/bin/env python3
"""Measure new-process Plan-file batch latency and peak RSS on Linux.

Each invocation starts a new runtime process without an in-process warmup.
The OS page cache is not flushed. Compilation is a separate boundary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

from run_benchmark import ARMS, CASES, LEVELS, input_path, plan_path, seeds, write_json


def file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def samples_sha256(path: Path) -> str:
    """Hash serde's final `samples` field without loading multi-GB Full JSON."""
    marker = b'\n  "samples": '
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        prefix = stream.read(512)
        if prefix.count(marker) != 1:
            raise ValueError(f"unexpected batch JSON header: {path}")
        start = prefix.index(marker) + len(marker)
        stream.seek(0, os.SEEK_END)
        size = stream.tell()
        stream.seek(-3, os.SEEK_END)
        if stream.read(3) != b"]\n}":
            raise ValueError(f"unexpected batch JSON footer: {path}")
        remaining = size - 2 - start
        stream.seek(start)
        while remaining:
            chunk = stream.read(min(1024 * 1024, remaining))
            if not chunk:
                raise ValueError(f"truncated batch JSON: {path}")
            hasher.update(chunk)
            remaining -= len(chunk)
    return hasher.hexdigest()


def run_one(root: Path, plan: Path, output: Path, case: str, arm: str,
            level: str, count: int, threads: int, repeat: int, variant: str) -> dict:
    payload = output / "scratch" / f"{case}-{arm}-{level}-{count}-{threads}-{repeat}-{variant}.json"
    binary = root / "rust/runtime/target/release/sim-engine-runtime"
    command = ["/usr/bin/time", "-v", str(binary), str(plan), str(payload),
               "--seeds", ",".join(map(str, seeds(count))),
               "--worker-threads", str(threads), "--observation-level", level]
    if arm == "candidates":
        command.append("--dependency-dispatch")
    started = time.perf_counter_ns()
    process = subprocess.run(command, cwd=root, text=True, capture_output=True)
    wall_ns = time.perf_counter_ns() - started
    if process.returncode:
        raise RuntimeError(f"{command}: {process.stderr}")
    summary = json.loads(process.stdout)
    if summary["sample_indexes"] != list(range(count)) or summary["seeds"] != seeds(count):
        raise AssertionError("sample identity/order changed")
    rss = next((int(line.rsplit(":", 1)[1].strip()) * 1024
                for line in process.stderr.splitlines()
                if "Maximum resident set size (kbytes):" in line), None)
    sample_digest = samples_sha256(payload)
    row = {"variant": variant, "case": case, "arm": arm, "level": level,
           "samples": count, "threads": threads, "repeat": repeat,
           "process_wall_ns": wall_ns, "peak_rss_bytes": rss,
           "result_sha256": file_sha256(payload),
           "samples_sha256": sample_digest, "result_bytes": payload.stat().st_size}
    payload.unlink()
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--shared-plan-dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", default=",".join(CASES))
    parser.add_argument("--arms", default="scan,cache,candidates")
    parser.add_argument("--levels", default="summary,full")
    parser.add_argument("--counts", default="1,32,256")
    parser.add_argument("--threads", default="1,2,4,8")
    parser.add_argument("--repeats", type=int, default=6)
    args = parser.parse_args()
    cases = args.cases.split(",")
    arms = args.arms.split(",")
    levels = args.levels.split(",")
    counts = [int(value) for value in args.counts.split(",")]
    threads = [int(value) for value in args.threads.split(",")]
    if any(value not in CASES for value in cases) or any(value not in ARMS for value in arms) or any(value not in LEVELS for value in levels):
        parser.error("unknown case, arm or level")
    if args.repeats < 1 or any(value < 1 for value in counts + threads):
        parser.error("repeats, sample counts and threads must be positive")
    roots = {"baseline": args.baseline_root.resolve(), "candidate": args.candidate_root.resolve()}
    shared_plan_dir = args.shared_plan_dir.resolve() if args.shared_plan_dir else None
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "scratch").mkdir(exist_ok=True)
    identity = {"roots": {label: str(root) for label, root in roots.items()},
                "plan_scope": "new process, Plan-file load; one per-configuration warmup; OS page cache not flushed; no canonical compile",
                "cases": cases, "arms": arms, "levels": levels, "counts": counts,
                "threads": threads, "repeats": args.repeats,
                "run_order": "paired baseline/candidate, reversed on odd repeats"}
    identity["platform"] = platform.platform()
    identity["python"] = sys.version
    identity["cpu_topology"] = subprocess.run(["lscpu"], text=True,
                                               capture_output=True, check=True).stdout.strip()
    identity["rustc"] = subprocess.run([str(Path.home() / ".cargo/bin/rustc"), "--version"],
                                       text=True, capture_output=True, check=True).stdout.strip()
    identity["artifacts"] = {}
    for variant, root in roots.items():
        if subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                          cwd=root, text=True, capture_output=True, check=True).stdout:
            raise RuntimeError(f"tracked source changes in {root}")
        binary = root / "rust/runtime/target/release/sim-engine-runtime"
        identity["artifacts"][variant] = {
            "commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                                     text=True, capture_output=True, check=True).stdout.strip(),
            "binary_sha256": file_sha256(binary),
            "plans": {f"{case}/{arm}": file_sha256(plan_path(root, case, arm, shared_plan_dir))
                      for case in cases for arm in ("scan", "cache")},
            "inputs": {case: file_sha256(input_path(root, case, shared_plan_dir))
                       for case in cases},
        }
    if (identity["artifacts"]["baseline"]["plans"] != identity["artifacts"]["candidate"]["plans"]
        or identity["artifacts"]["baseline"]["inputs"] != identity["artifacts"]["candidate"]["inputs"]):
        raise AssertionError("cold A/B inputs or Plans differ")
    identity["load_before"] = list(os.getloadavg())
    write_json(args.output / "identity.json", identity)
    expected_samples: dict[tuple[str, str, int], str] = {}
    expected_result: dict[tuple[str, str, int, int], str] = {}
    with (args.output / "records.jsonl").open("w") as records:
        for count in counts:
            for case in cases:
                for level in levels:
                    for arm in arms:
                        for workers in ([1] if count == 1 else threads):
                            if workers > count:
                                continue
                            for variant, root in roots.items():
                                run_one(root, plan_path(root, case, arm, shared_plan_dir),
                                        args.output, case, arm, level, count, workers,
                                        -1, variant)
                            for repeat in range(args.repeats):
                                order = list(roots)
                                if repeat % 2:
                                    order.reverse()
                                for variant in order:
                                    root = roots[variant]
                                    plan = plan_path(root, case, arm, shared_plan_dir)
                                    row = run_one(root, plan, args.output, case, arm, level,
                                                  count, workers, repeat, variant)
                                    key = (case, level, count)
                                    reference = expected_samples.setdefault(key, row["samples_sha256"])
                                    result_key = (case, level, count, workers)
                                    result_reference = expected_result.setdefault(
                                        result_key, row["result_sha256"])
                                    if (row["samples_sha256"] != reference
                                            or row["result_sha256"] != result_reference):
                                        raise AssertionError(f"result changed: {row}")
                                    records.write(json.dumps(row) + "\n")
                                    records.flush()
                                    print(case, arm, level, count, workers, repeat, variant,
                                          round(row["process_wall_ns"] / 1e6, 3), flush=True)
    identity["load_after"] = list(os.getloadavg())
    write_json(args.output / "identity.json", identity)


if __name__ == "__main__":
    main()
