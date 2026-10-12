#!/usr/bin/env python3
"""Private execution/controller boundary for the round-two assessment."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
from experiments.codex_modeling_pilot.runner import read_json, run_candidate, write_json
from experiments.codex_modeling_round2.evaluator import apply_changes, evaluate


def load_cases():
    return read_json(HERE / "private/cases.json")


def empty_directory(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    if any(path.iterdir()):
        raise ValueError(f"output directory must be empty: {path}")
    return path


def execution_summary(run):
    return {key: run[key] for key in ("candidate_valid", "compiled", "executed", "error", "fingerprints", "timings_seconds")}


def evaluate_candidate(candidate, out_dir, case, *, include_interventions=True):
    """Run fresh saved IR via frozen pilot runner; score only after execution.

    No final scoring or hidden intervention output is returned to author agents.
    This function is exclusively for the controller and private control tests.
    """
    started = time.perf_counter()
    out = empty_directory(out_dir)
    run = run_candidate(candidate, out / "base", score=False)
    score_started = time.perf_counter()
    score = evaluate(candidate, run["result"], case)
    scoring_seconds = time.perf_counter() - score_started
    write_json(out / "assessment.json", score)
    interventions = []
    if include_interventions and case["category"] in ("modeling", "composition"):
        for intervention in case.get("interventions", []):
            entry = {"id": intervention["id"], "accepted": False}
            if not run["executed"]:
                entry["skipped_reason"] = "baseline candidate did not execute"
                interventions.append(entry)
                continue
            try:
                changed = copy.deepcopy(candidate)
                changed["model"] = apply_changes(candidate["model"], intervention["changes"])
                target = out / "interventions" / intervention["id"]
                altered_run = run_candidate(changed, target, score=False)
                altered_case = dict(case, constraints=[], behavior=intervention["behavior"], interventions=[])
                score_started = time.perf_counter()
                altered_score = evaluate(changed, altered_run["result"], altered_case, behavior_only=True)
                altered_scoring = time.perf_counter() - score_started
                scoring_seconds += altered_scoring
                entry.update(execution_summary(altered_run))
                entry.update(accepted=bool(altered_run["executed"] and not altered_run["error"] and altered_score["accepted"]),
                             assessment=altered_score, scoring_seconds=altered_scoring)
                write_json(target / "assessment.json", altered_score)
            except Exception as exc:
                entry["error"] = {"type": type(exc).__name__, "message": str(exc)}
            interventions.append(entry)
    primary_ok = bool(run["candidate_valid"] and not run["error"] and score["accepted"])
    report = {"schema_version": "codex-modeling-round2-trial/v1", "task_id": case["task_id"],
              "category": case["category"], "candidate_status": candidate.get("status") if isinstance(candidate, dict) else None,
              "accepted": primary_ok and all(row["accepted"] for row in interventions),
              "baseline_accepted": primary_ok, "assessment_kind": score["assessment_kind"],
              "semantic_review_required": score["semantic_review_required"],
              **execution_summary(run), "checks": score["checks"], "interventions": interventions,
              "scoring_seconds": scoring_seconds, "total_controller_seconds": time.perf_counter() - started}
    write_json(out / "trial.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--answered", action="store_true", help="Assess against preregistered clarification answer contract")
    args = parser.parse_args()
    try:
        candidate = read_json(args.candidate)
        book = load_cases()
        cases = {c["task_id"]: c for c in book["development"] + book["holdout"]}
        case = cases[candidate["task_id"]]
        if args.answered:
            case = case["clarification"]["answered_case"]
        report = evaluate_candidate(candidate, args.out, case)
        print(json.dumps({"task_id": report["task_id"], "accepted": report["accepted"],
                          "assessment_kind": report["assessment_kind"], "out": str(args.out)}, ensure_ascii=False))
        return int(not report["accepted"])
    except Exception as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
