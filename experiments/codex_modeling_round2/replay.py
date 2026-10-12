#!/usr/bin/env python3
"""Private replay of all 24 holdout tasks x three arms x three fresh contexts.

Missing trials are explicit failures. Optional clarification followups retain a
fixed denominator, separate from conditional completion among answered cases.
Replaying candidates reproduces execution/scoring, not hosted model generation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
from experiments.codex_modeling_pilot.runner import read_json, write_json
from experiments.codex_modeling_round2.controller import empty_directory, evaluate_candidate, load_cases

ARMS = ("A", "B", "C")
REPEATS = ("r1", "r2", "r3")


def verify_frozen():
    frozen = read_json(HERE / "frozen-inputs.json")
    for relative, expected in frozen["sha256"].items():
        actual = hashlib.sha256((HERE / relative).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"frozen experiment input changed: {relative}")
    source = read_json(HERE / "source-manifest.json")
    for entry in source["files"]:
        if not entry["path"].startswith("src/"):
            continue
        content = (REPO / entry["path"]).read_bytes()
        actual = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
        if actual != entry["git_blob_sha"]:
            raise ValueError(f"pinned engine source changed: {entry['path']}")


def summarize(trials):
    categories = {}
    for category in ("modeling", "composition", "clarify", "unsupported"):
        rows = [r for r in trials if r["category"] == category]
        categories[category] = {"expected_trials": len(rows),
                                "accepted": sum(bool(r.get("accepted")) for r in rows),
                                "compiled": sum(bool(r.get("compiled")) for r in rows),
                                "executed": sum(bool(r.get("executed")) for r in rows),
                                "missing_or_invalid": sum(bool(r.get("submission_error")) for r in rows),
                                "assessment_kind": "automatic_concept_screen" if category in ("clarify", "unsupported") else "requirement_behavior_checks"}
    model_rows = [r for r in trials if r["category"] in ("modeling", "composition")]
    return {"categories": categories, "executable_expected": len(model_rows),
            "executable_accepted": sum(bool(r.get("accepted")) for r in model_rows),
            "baseline_compile_seconds": sum(r.get("timings_seconds", {}).get("compile_with_persistence", 0) for r in trials),
            "baseline_execution_seconds": sum(r.get("timings_seconds", {}).get("execution", 0) for r in trials),
            "interventions_expected": sum(len(r.get("interventions", [])) for r in model_rows),
            "interventions_accepted": sum(bool(i["accepted"]) for r in model_rows for i in r.get("interventions", [])),
            "semantic_review_note": "Language screens are not semantic correctness; blind AI review is reported separately."}


def replay(submissions, out, *, followups=None):
    verify_frozen()
    out = empty_directory(out)
    cases = load_cases()["holdout"]
    if len(cases) != 24 or len({c["task_id"] for c in cases}) != 24:
        raise ValueError("round2 requires exactly 24 distinct preregistered holdout tasks")
    if (sum(c["category"] in ("modeling", "composition") for c in cases) != 16
            or sum(c["category"] == "clarify" for c in cases) != 4
            or sum(c["category"] == "unsupported" for c in cases) != 4):
        raise ValueError("holdout must contain 16 executable, 4 clarification, and 4 unsupported tasks")
    summary = {"schema_version": "codex-modeling-round2-summary/v1", "expected_trials": 216,
               "primary": [], "by_arm": {}, "by_arm_repeat": {}, "followups": [], "followup_by_arm": {}}
    for arm in ARMS:
        for repeat in REPEATS:
            for case in cases:
                tid = case["task_id"]
                trial = {"arm": arm, "repeat": repeat, "task_id": tid, "category": case["category"], "accepted": False}
                try:
                    candidate = read_json(Path(submissions) / arm / repeat / f"{tid}.json")
                    if not isinstance(candidate, dict) or candidate.get("task_id") != tid:
                        raise ValueError("filename/task_id mismatch")
                    trial.update(evaluate_candidate(candidate, out / "primary" / arm / repeat / tid, case))
                except Exception as exc:
                    trial["submission_error"] = {"type": type(exc).__name__, "message": str(exc)}
                    trial["interventions"] = [{"id": i["id"], "accepted": False, "skipped_reason": "missing/invalid submission"}
                                              for i in case.get("interventions", [])]
                summary["primary"].append(trial)
            subset = [r for r in summary["primary"] if r["arm"] == arm and r["repeat"] == repeat]
            summary["by_arm_repeat"][f"{arm}/{repeat}"] = summarize(subset)
        summary["by_arm"][arm] = summarize([r for r in summary["primary"] if r["arm"] == arm])
    summary["all_primary_passed"] = all(r["accepted"] for r in summary["primary"])
    summary["all_executable_passed"] = all(r["accepted"] for r in summary["primary"] if r["category"] in ("modeling", "composition"))

    if followups is not None:
        lookup = {(r["arm"], r["repeat"], r["task_id"]): r for r in summary["primary"]}
        for arm in ARMS:
            for repeat in REPEATS:
                for case in cases:
                    if case["category"] != "clarify":
                        continue
                    tid = case["task_id"]
                    primary = lookup[(arm, repeat, tid)]
                    row = {"arm": arm, "repeat": repeat, "task_id": tid,
                           "initial_screen_passed": primary["accepted"], "answered": False,
                           "accepted": False, "end_to_end_screen_and_model_passed": False}
                    path = Path(followups) / arm / repeat / f"{tid}.json"
                    if path.exists():
                        row["answered"] = True
                        try:
                            candidate = read_json(path)
                            if not isinstance(candidate, dict) or candidate.get("task_id") != tid:
                                raise ValueError("followup filename/task_id mismatch")
                            answered_case = case["clarification"]["answered_case"]
                            row.update(evaluate_candidate(candidate, out / "followups" / arm / repeat / tid, answered_case))
                            row["end_to_end_screen_and_model_passed"] = primary["accepted"] and row["accepted"]
                        except Exception as exc:
                            row["submission_error"] = {"type": type(exc).__name__, "message": str(exc)}
                    else:
                        row["missing_followup"] = True
                    summary["followups"].append(row)
            rows = [r for r in summary["followups"] if r["arm"] == arm]
            summary["followup_by_arm"][arm] = {
                "fixed_denominator": len(rows),
                "end_to_end_screen_and_model_passed": sum(r["end_to_end_screen_and_model_passed"] for r in rows),
                "answered_count": sum(r["answered"] for r in rows),
                "answered_model_accepted": sum(r["accepted"] for r in rows if r["answered"]),
                "note": "Fixed denominator includes missed questions; conditional completion uses answered_count. Initial language stage still needs semantic review."}
    write_json(out / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submissions", type=Path, default=HERE / "submissions")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--followups", type=Path)
    args = parser.parse_args()
    summary = replay(args.submissions, args.out, followups=args.followups)
    print(json.dumps({"by_arm": summary["by_arm"], "followup_by_arm": summary["followup_by_arm"]}, ensure_ascii=False, indent=2))
    failed = not summary["all_primary_passed"]
    if args.followups is not None:
        failed |= any(not r["end_to_end_screen_and_model_passed"] for r in summary["followups"])
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
