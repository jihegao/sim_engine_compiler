#!/usr/bin/env python3
"""Paired PyO3 Plan-batch calls; report this boundary separately from Rust CLI."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from run_benchmark import plan_path, seeds, write_json


def worker(args: argparse.Namespace) -> None:
    import sim_engine_compiler

    if not sim_engine_compiler.native_available():
        raise RuntimeError("native binding unavailable in this checkout")
    plan = args.plan.read_bytes()
    sample_seeds = seeds(args.samples)
    sim_engine_compiler.run_batch(plan, sample_seeds, worker_threads=args.threads,
                                  observation_level=args.level)
    started = time.perf_counter_ns()
    result = sim_engine_compiler.run_batch(plan, sample_seeds,
                                            worker_threads=args.threads,
                                            observation_level=args.level)
    call_ns = time.perf_counter_ns() - started
    if [row["sample_index"] for row in result["samples"]] != list(range(args.samples)):
        raise AssertionError("binding sample order changed")
    if [row["seed"] for row in result["samples"]] != sample_seeds:
        raise AssertionError("binding seed order changed")
    encoded = json.dumps(result["samples"], ensure_ascii=False,
                         sort_keys=True, separators=(",", ":")).encode()
    write_json(args.report, {"call_ns": call_ns,
                             "samples_sha256": hashlib.sha256(encoded).hexdigest(),
                             "result_bytes": len(encoded)})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-root", type=Path)
    parser.add_argument("--candidate-root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--samples", type=int, default=32)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--level", choices=("summary", "full"), default="summary")
    parser.add_argument("--arm", choices=("scan", "cache"), default="cache")
    parser.add_argument("--repeats", type=int, default=6)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.samples < 1 or args.threads < 1 or args.repeats < 1:
        parser.error("samples, threads and repeats must be positive")
    if args.worker:
        if not args.plan or not args.report:
            parser.error("worker needs --plan and --report")
        worker(args)
        return
    if not args.baseline_root or not args.candidate_root or not args.output:
        parser.error("paired run needs --baseline-root, --candidate-root and --output")
    roots = {"baseline": args.baseline_root.resolve(), "candidate": args.candidate_root.resolve()}
    args.output.mkdir(parents=True, exist_ok=True)
    artifacts = {}
    for name, root in roots.items():
        extension = root / "src/sim_engine_compiler/_runtime.abi3.so"
        plan = plan_path(root, "f35", args.arm, None)
        artifacts[name] = {
            "commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                                      text=True, capture_output=True, check=True).stdout.strip(),
            "extension_sha256": hashlib.sha256(extension.read_bytes()).hexdigest(),
            "plan_sha256": hashlib.sha256(plan.read_bytes()).hexdigest(),
        }
    if artifacts["baseline"]["plan_sha256"] != artifacts["candidate"]["plan_sha256"]:
        raise AssertionError("binding A/B Plans differ")
    identity = {"roots": {name: str(root) for name, root in roots.items()},
                "artifacts": artifacts,
                "boundary": "Python run_batch(bytes) call: native Plan parse/validation, runtime, JSON transfer and decode; Plan file read and process startup excluded",
                "samples": args.samples, "threads": args.threads, "level": args.level,
                "arm": args.arm, "repeats": args.repeats,
                "run_order": "paired baseline/candidate, reversed on odd repeats"}
    write_json(args.output / "identity.json", identity)
    expected = None
    with (args.output / "records.jsonl").open("w") as records:
        for repeat in range(args.repeats):
            order = list(roots)
            if repeat % 2:
                order.reverse()
            for variant in order:
                root = roots[variant]
                report = args.output / f"{variant}-{repeat}.json"
                command = [str(root / ".venv/bin/python"), str(Path(__file__).resolve()),
                           "--worker", "--plan", str(plan_path(root, "f35", args.arm, None)),
                           "--report", str(report), "--samples", str(args.samples),
                           "--threads", str(args.threads), "--level", args.level]
                environment = dict(os.environ, PYTHONPATH=str(root / "src"))
                process = subprocess.run(command, cwd=root, env=environment,
                                         text=True, capture_output=True)
                if process.returncode:
                    raise RuntimeError(f"{command}: {process.stderr}")
                row = {"variant": variant, "repeat": repeat, **json.loads(report.read_text())}
                expected = expected or row["samples_sha256"]
                if row["samples_sha256"] != expected:
                    raise AssertionError(f"binding result changed: {row}")
                records.write(json.dumps(row) + "\n")
                records.flush()
                print(variant, repeat, round(row["call_ns"] / 1e6, 3), flush=True)


if __name__ == "__main__":
    main()
