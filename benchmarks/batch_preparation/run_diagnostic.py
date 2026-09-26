#!/usr/bin/env python3
"""Collect phase counters from separate instrumented runtime checkouts."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

from run_benchmark import KNOWN_CASES, plan_path, seeds, write_json
from run_cold import file_sha256


def tagged_json(stderr: str, prefix: str) -> dict:
    matches = [line.removeprefix(prefix) for line in stderr.splitlines()
               if line.startswith(prefix)]
    if len(matches) != 1:
        raise ValueError(f"expected one {prefix!r} record, got {len(matches)}")
    return json.loads(matches[0])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", choices=KNOWN_CASES, default="f35")
    parser.add_argument("--case-dir", type=Path)
    parser.add_argument("--counts", default="32,256")
    parser.add_argument("--arms", default="scan,cache")
    args = parser.parse_args()
    counts = [int(value) for value in args.counts.split(",")]
    arms = args.arms.split(",")
    if any(count < 1 for count in counts) or any(arm not in ("scan", "cache") for arm in arms):
        parser.error("counts must be positive and arms must be scan or cache")
    if args.case == "j35" and args.case_dir is None:
        parser.error("J35 requires --case-dir")
    roots = {"baseline": args.baseline_root.resolve(),
             "candidate": args.candidate_root.resolve()}
    args.output.mkdir(parents=True, exist_ok=True)
    identity = {"boundary": "instrumented JSON Plan CLI; phase counters only, excluded from formal timing",
                "case": args.case, "case_dir": str(args.case_dir) if args.case_dir else None,
                "counts": counts, "arms": arms, "worker_threads": 1,
                "roots": {variant: str(root) for variant, root in roots.items()},
                "artifacts": {}}
    for variant, root in roots.items():
        binary = root / "rust/runtime/target/release/sim-engine-runtime"
        identity["artifacts"][variant] = {
            "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                                            text=True, capture_output=True, check=True).stdout.strip(),
            "patch_sha256": hashlib.sha256(subprocess.run(
                ["git", "diff", "--binary"], cwd=root, capture_output=True,
                check=True).stdout).hexdigest(),
            "binary_sha256": file_sha256(binary),
            "plans": {arm: file_sha256(plan_path(root, args.case, arm, args.case_dir))
                      for arm in arms},
        }
    write_json(args.output / "identity.json", identity)
    expected: dict[int, str] = {}
    rows = []
    for count in counts:
        for arm in arms:
            for variant, root in roots.items():
                output = args.output / f"scratch-{variant}-{arm}-{count}.json"
                command = [str(root / "rust/runtime/target/release/sim-engine-runtime"),
                           str(plan_path(root, args.case, arm, args.case_dir)), str(output),
                           "--seeds", ",".join(map(str, seeds(count))),
                           "--worker-threads", "1", "--observation-level", "summary"]
                process = subprocess.run(command, cwd=root,
                                         env=dict(os.environ, SIM_PREP_DIAGNOSTIC="1"),
                                         text=True, capture_output=True)
                if process.returncode:
                    raise RuntimeError(f"{command}: {process.stderr}")
                digest = file_sha256(output)
                reference = expected.setdefault(count, digest)
                if digest != reference:
                    raise AssertionError(f"diagnostic result changed: {variant}/{arm}/{count}")
                row = {"variant": variant, "arm": arm, "samples": count,
                       "result_sha256": digest,
                       "load": tagged_json(process.stderr, "SIM_PREP_LOAD_DIAGNOSTIC "),
                       "batch": tagged_json(process.stderr, "SIM_PREP_DIAGNOSTIC ")}
                rows.append(row)
                output.unlink()
                print(variant, arm, count, row["batch"], flush=True)
    write_json(args.output / "records.json", rows)


if __name__ == "__main__":
    main()
