#!/usr/bin/env python3
"""Replay repair submissions with the frozen first-pilot hidden contract.

This controller-only convenience wrapper was added after repair submission;
the scorer, mapping, inputs and feedback were frozen before participation.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROUND = HERE.parent
REPO = ROUND.parents[1]
sys.path.insert(0, str(REPO))
from experiments.codex_modeling_pilot.runner import read_json, write_json, run_candidate
from experiments.codex_modeling_round2.replay import verify_frozen


def replay(out):
    verify_frozen()
    frozen = read_json(ROUND / "repair-frozen-inputs.json")
    for relative, sha in frozen["sha256"].items():
        if hashlib.sha256((ROUND / relative).read_bytes()).hexdigest() != sha:
            raise ValueError(f"repair frozen input changed: {relative}")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise ValueError("output directory must be empty")
    mapping = read_json(HERE / "private/task-id-map.json")
    summary = {"schema": "codex-modeling-round2-repair-summary/v1",
               "scoring": "first-pilot strict requirement/behavior contract",
               "task_id_mapping": mapping,
               "initial": [], "trials": [], "by_condition_revision": {}}
    runs = [("initial", "r0", HERE / "public/initial")]
    runs += [(arm, rev, HERE / "submissions" / arm / rev)
             for arm in ("N", "D", "T") for rev in ("r1", "r2")]
    for arm, rev, source in runs:
        for tid, pilot_tid in mapping.items():
            trial = {"condition": arm, "revision": rev, "task_id": tid,
                     "compiled": False, "executed": False, "accepted": False}
            try:
                candidate = read_json(source / f"{tid}.json")
                if candidate["task_id"] != tid:
                    raise ValueError("filename/task_id mismatch")
                mapped = copy.deepcopy(candidate)
                mapped["task_id"] = pilot_tid
                run = run_candidate(mapped, out / arm / rev / tid, score=True)
                trial.update(compiled=run["compiled"], executed=run["executed"],
                             error=run["error"], evaluation_error=run.get("evaluation_error"),
                             fingerprints=run["fingerprints"], timings_seconds=run["timings_seconds"])
                score = run.get("evaluation") or {}
                trial["accepted"] = bool(run["candidate_valid"] and run["executed"]
                                         and not run["error"] and not run.get("evaluation_error")
                                         and score.get("accepted"))
                trial["failed_check_ids"] = [c["id"] for c in score.get("checks", []) if not c["passed"]]
            except Exception as exc:
                trial["error"] = {"type": type(exc).__name__, "message": str(exc)}
            summary["initial" if arm == "initial" else "trials"].append(trial)
        rows = [x for x in summary["initial"] + summary["trials"]
                if x["condition"] == arm and x["revision"] == rev]
        summary["by_condition_revision"][f"{arm}/{rev}"] = {
            "expected": 6, "compiled": sum(x["compiled"] for x in rows),
            "executed": sum(x["executed"] for x in rows),
            "accepted": sum(x["accepted"] for x in rows)}
    write_json(out / "summary.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = replay(args.out)
    print(json.dumps(result["by_condition_revision"], indent=2))
    # The intentionally bad initial models are expected to fail acceptance.
    raise SystemExit(int(any(not x["accepted"] for x in result["trials"])))
