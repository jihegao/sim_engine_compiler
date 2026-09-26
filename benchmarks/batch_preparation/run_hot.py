#!/usr/bin/env python3
"""Measure repeated public and prepared-handle batches in one Rust process."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from run_benchmark import plan_path, seeds, write_json
from run_cold import file_sha256


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--counts", default="1,32,256")
    parser.add_argument("--threads", default="1,2,4,8")
    parser.add_argument("--repeats", type=int, default=6)
    args = parser.parse_args()
    counts = [int(value) for value in args.counts.split(",")]
    threads = [int(value) for value in args.threads.split(",")]
    if args.repeats < 1 or any(value < 1 for value in counts + threads):
        parser.error("counts, threads and repeats must be positive")
    root = args.candidate_root.resolve()
    plan = plan_path(root, "f35", "cache", None)
    binary = root / "rust/runtime/target/release/prepared_batch_benchmark"
    args.output.mkdir(parents=True, exist_ok=True)
    identity = {
        "boundary": "one process and one validated PreparedBatchPlan; repeated public vs prepared calls, run and serialization reported separately",
        "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                                        text=True, capture_output=True, check=True).stdout.strip(),
        "binary_sha256": file_sha256(binary), "plan_sha256": file_sha256(plan),
        "counts": counts, "threads": threads, "warmups": 1,
        "repeats": args.repeats, "observation_level": "summary",
    }
    write_json(args.output / "identity.json", identity)
    records = []
    for count in counts:
        for workers in ([1] if count == 1 else threads):
            if workers > count:
                continue
            report = args.output / f"hot-{count}-{workers}.json"
            command = ["/usr/bin/time", "-v", str(binary), str(plan), str(report),
                       "--seeds", ",".join(map(str, seeds(count))),
                       "--worker-threads", str(workers), "--warmups", "1",
                       "--repeats", str(args.repeats), "--observation-level", "summary"]
            process = subprocess.run(command, cwd=root, text=True, capture_output=True)
            if process.returncode:
                raise RuntimeError(f"{command}: {process.stderr}")
            data = json.loads(report.read_text())
            hashes = {row["sample_sha256"] for row in data["rows"]}
            if len(hashes) != 1 or len(data["rows"]) != args.repeats * 2:
                raise AssertionError(f"hot result mismatch: {report}")
            rss = next((int(line.rsplit(":", 1)[1].strip()) * 1024
                        for line in process.stderr.splitlines()
                        if "Maximum resident set size (kbytes):" in line), None)
            records.append({"samples": count, "threads": workers,
                            "peak_rss_bytes": rss, "report": report.name,
                            "sample_sha256": next(iter(hashes)),
                            "preparation_ns": data["preparation_ns"]})
            print(count, workers, round(data["preparation_ns"] / 1e6, 3), flush=True)
    write_json(args.output / "records.json", records)


if __name__ == "__main__":
    main()
