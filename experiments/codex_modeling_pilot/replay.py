#!/usr/bin/env python3
"""Replay saved candidates with the frozen engine and independent evaluator.

This command replays execution/scoring, not the hosted Codex generation calls.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
from runner import read_json, run_candidate, write_json


def verify_frozen():
    frozen = read_json(HERE / "frozen-inputs.json")
    for relative, expected in frozen["sha256"].items():
        actual = hashlib.sha256((HERE / relative).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"frozen experiment input changed: {relative}")
    source = read_json(HERE / "source-manifest.json")
    for entry in source["files"]:
        # Only executing source files are needed when replaying a normal checkout.
        if not entry["path"].startswith("src/"):
            continue
        content = (REPO / entry["path"]).read_bytes()
        actual = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
        if actual != entry["git_blob_sha"]:
            raise ValueError(f"pinned engine source changed: {entry['path']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submissions", type=Path, default=HERE / "submissions")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    verify_frozen()
    if args.out.exists() and any(args.out.iterdir()):
        parser.error("output directory must be empty; previous evidence is never overwritten")
    args.out.mkdir(parents=True, exist_ok=True)
    tasks = read_json(HERE / "public/tasks.json")["tasks"]
    summary = {"schema": "codex-modeling-pilot-summary/v1", "arms": {}, "trials": []}
    failed = False
    for arm in ("A", "B", "C"):
        counts = {"executable_tasks": 6, "compiled": 0, "executed": 0,
                  "models_accepted": 0, "clarification_accepted": 0,
                  "unsupported_accepted": 0, "missing_or_invalid_files": 0,
                  "compile_seconds": 0.0, "execution_seconds": 0.0}
        for task in tasks:
            tid = task["task_id"]
            path = args.submissions / arm / f"{tid}.json"
            try:
                candidate = read_json(path)
                if candidate.get("task_id") != tid:
                    raise ValueError("filename/task_id mismatch")
                report = run_candidate(candidate, args.out / arm / tid, score=True)
                accepted = bool(report["candidate_valid"] and not report["error"]
                                and not report.get("evaluation_error")
                                and (report.get("evaluation") or {}).get("accepted"))
                trial = {"arm": arm, "task_id": tid, "status": candidate["status"],
                         "accepted": accepted, "compiled": report["compiled"],
                         "executed": report["executed"], "error": report["error"],
                         "evaluation_error": report.get("evaluation_error"),
                         "failed_check_ids": [c["id"] for c in (report.get("evaluation") or {}).get("checks", []) if not c["passed"]],
                         "timings_seconds": report["timings_seconds"],
                         "fingerprints": report["fingerprints"]}
                if tid <= "T06":
                    counts["compiled"] += int(report["compiled"])
                    counts["executed"] += int(report["executed"])
                    counts["models_accepted"] += int(accepted and report["executed"])
                elif tid == "T07":
                    counts["clarification_accepted"] += int(accepted)
                else:
                    counts["unsupported_accepted"] += int(accepted)
                counts["compile_seconds"] += report["timings_seconds"].get("compile_with_persistence", 0)
                counts["execution_seconds"] += report["timings_seconds"].get("execution", 0)
            except Exception as exc:
                counts["missing_or_invalid_files"] += 1
                trial = {"arm": arm, "task_id": tid, "accepted": False,
                         "error": {"type": type(exc).__name__, "message": str(exc)}}
            summary["trials"].append(trial)
            failed |= not trial["accepted"]
        summary["arms"][arm] = counts
    write_json(args.out / "summary.json", summary)
    print(json.dumps(summary["arms"], ensure_ascii=False, indent=2))
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
