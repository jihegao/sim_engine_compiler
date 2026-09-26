#!/usr/bin/env python3
"""Paired, uninstrumented Stage C measurements for batch Plan preparation.

Both checkouts must contain the same frozen Plan files. This runner never
compiles or modifies source; it records each completed invocation immediately.
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

CASES = ("f35", "synthetic-capacity-16", "synthetic-remote-16", "shared-remote-pools")
ARMS = ("scan", "cache", "candidates")
LEVELS = ("summary", "full")
SEED_CYCLE = (0, 1, 7, 7)


def checked(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, check=True, text=True, capture_output=True)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(root: Path, *arguments: str) -> str:
    return checked(["git", *arguments], root).stdout.strip()


def plan_path(root: Path, case: str, arm: str, shared_plan_dir: Path | None) -> Path:
    if case == "shared-remote-pools":
        directory = shared_plan_dir or root / "benchmarks/batch_preparation/fixtures/shared-remote-pools"
        return directory / ("scan-plan.json" if arm == "scan" else "indexed-plan.json")
    return root / "benchmarks/dependency_dispatch/results/macos-arm64-20260925" / case / "event-time-v2" / ("scan-plan.json" if arm == "scan" else "indexed-plan.json")


def identity(root: Path, cases: list[str], shared_plan_dir: Path | None) -> dict:
    binary = root / "rust/runtime/target/release/stage-c-benchmark"
    if git(root, "status", "--porcelain", "--untracked-files=no"):
        raise RuntimeError(f"tracked changes in {root}")
    result = {
        "root": str(root), "commit": git(root, "rev-parse", "HEAD"),
        "tree": git(root, "rev-parse", "HEAD^{tree}"),
        "binary_sha256": sha256(binary),
        "plans": {f"{case}/{arm}": sha256(plan_path(root, case, arm, shared_plan_dir))
                  for case in cases for arm in ("scan", "cache")},
        "inputs": {
            case: sha256(shared_plan_dir / "inputs.json" if case == "shared-remote-pools" and shared_plan_dir
                         else root / "benchmarks/batch_preparation/fixtures/shared-remote-pools/inputs.json"
                         if case == "shared-remote-pools"
                         else root / "benchmarks/dependency_dispatch/results/macos-arm64-20260925" / case / "inputs.json")
            for case in cases
        },
    }
    return result


def seeds(count: int) -> list[int]:
    return [SEED_CYCLE[index % len(SEED_CYCLE)] for index in range(count)]


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def run_one(root: Path, output: Path, case: str, arm: str, level: str,
            count: int, threads: int, repeat: int, variant: str,
            shared_plan_dir: Path | None) -> dict:
    binary = root / "rust/runtime/target/release/stage-c-benchmark"
    report = output / "runs" / f"{case}-{arm}-{level}-{count}-{threads}-{repeat}-{variant}.json"
    arguments = [str(binary), str(plan_path(root, case, arm, shared_plan_dir)), str(report),
                 "--seeds", ",".join(map(str, seeds(count))),
                 "--worker-threads", str(threads), "--warmups", "1",
                 "--repeats", "1", "--observation-level", level]
    if arm == "candidates":
        arguments.append("--dependency-dispatch")
    process = checked(["/usr/bin/time", "-v", *arguments], root)
    data = json.loads(report.read_text())
    row = data["records"][0]
    if row["sample_indexes"] != list(range(count)) or row["seeds"] != seeds(count):
        raise AssertionError(f"sample identity/order changed: {report}")
    rss = None
    for line in process.stderr.splitlines():
        if "Maximum resident set size (kbytes):" in line:
            rss = int(line.rsplit(":", 1)[1].strip()) * 1024
    return {"variant": variant, "case": case, "arm": arm, "level": level,
            "samples": count, "threads": threads, "repeat": repeat,
            "report": str(report), "phases": row["phases"],
            "samples_sha256": row["samples_sha256"],
            "peak_rss_bytes": rss}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=6)
    parser.add_argument("--cases", default=",".join(CASES))
    parser.add_argument("--levels", default=",".join(LEVELS))
    parser.add_argument("--arms", default=",".join(ARMS))
    parser.add_argument("--counts", default="1,32,256")
    parser.add_argument("--threads", default="1,2,4,8")
    parser.add_argument("--shared-plan-dir", type=Path,
                        help="frozen shared-remote-pools Plans, also used by the baseline checkout")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("repeats must be positive")
    cases = args.cases.split(",")
    levels = args.levels.split(",")
    arms = args.arms.split(",")
    counts = [int(value) for value in args.counts.split(",")]
    threads = [int(value) for value in args.threads.split(",")]
    if any(value not in CASES for value in cases) or any(value not in LEVELS for value in levels) or any(value not in ARMS for value in arms):
        parser.error("unknown case, level or arm")
    if any(value < 1 for value in counts + threads):
        parser.error("counts and threads must be positive")
    variants = {"baseline": args.baseline_root.resolve()}
    if args.candidate_root:
        variants["candidate"] = args.candidate_root.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "runs").mkdir(exist_ok=True)
    shared_plan_dir = args.shared_plan_dir.resolve() if args.shared_plan_dir else None
    if "shared-remote-pools" in cases and len(variants) == 2 and shared_plan_dir is None:
        parser.error("--shared-plan-dir is required for paired shared-remote-pools runs")
    metadata = {"variants": {name: identity(root, cases, shared_plan_dir) for name, root in variants.items()},
                "platform": platform.platform(), "python": sys.version,
                "logical_cpus": os.cpu_count(), "repeats": args.repeats,
                "warmups_per_invocation": 1,
                "memory_scope": "whole stage-c-benchmark process, including warmup and isolated single-sample measurements",
                "timing_scope": "stage-c-benchmark internal uninstrumented phases; process startup excluded",
                "cases": cases, "levels": levels, "arms": arms,
                "counts": counts, "threads": threads,
                "run_order": "paired baseline/candidate, reversed on odd repeats"}
    metadata["rustc"] = checked([str(Path.home() / ".cargo/bin/rustc"), "--version"],
                                  variants["baseline"]).stdout.strip()
    metadata["cpu_topology"] = checked(["lscpu"], variants["baseline"]).stdout.strip()
    metadata["load_before"] = os.getloadavg()
    if len(variants) == 2:
        baseline = metadata["variants"]["baseline"]
        candidate = metadata["variants"]["candidate"]
        if baseline["plans"] != candidate["plans"] or baseline["inputs"] != candidate["inputs"]:
            raise AssertionError("baseline and candidate must use identical inputs and Plans")
    write_json(args.output / "identity.json", metadata)
    records_file = args.output / "records.jsonl"
    hashes: dict[tuple[str, str, int], str] = {}
    with records_file.open("w") as records:
        for count in counts:
            for case in cases:
                for level in levels:
                    for arm in arms:
                        for workers in ([1] if count == 1 else threads):
                            if workers > count:
                                continue
                            for repeat in range(args.repeats):
                                order = list(variants)
                                if repeat % 2:
                                    order.reverse()
                                pair = []
                                for variant in order:
                                    row = run_one(variants[variant], args.output, case, arm,
                                                  level, count, workers, repeat, variant,
                                                  shared_plan_dir)
                                    key = (case, level, count)
                                    expected = hashes.setdefault(key, row["samples_sha256"])
                                    if row["samples_sha256"] != expected:
                                        raise AssertionError(f"result changed across arms/threads/repeats: {row}")
                                    records.write(json.dumps(row) + "\n")
                                    records.flush()
                                    pair.append(row)
                                    print(case, arm, level, count, workers, repeat, variant,
                                          round(row["phases"]["end_to_end_batch_ns"] / 1e6, 3),
                                          flush=True)
                                if len(pair) == 2 and pair[0]["samples_sha256"] != pair[1]["samples_sha256"]:
                                    raise AssertionError(f"A/B result mismatch: {pair}")
    metadata["load_after"] = os.getloadavg()
    write_json(args.output / "identity.json", metadata)


if __name__ == "__main__":
    main()
