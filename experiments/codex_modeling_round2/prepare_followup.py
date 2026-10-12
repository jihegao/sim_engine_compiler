#!/usr/bin/env python3
"""Controller-only: seal primary submissions and supply fixed simulated answers.

Implements the preregistered interaction policy without executing model tasks
or revealing any private acceptance result to the author.
"""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from experiments.codex_modeling_pilot.runner import read_json, write_json
from experiments.codex_modeling_round2.evaluator import evaluate
from experiments.codex_modeling_round2.replay import verify_frozen


def prepare(arm, repeat):
    verify_frozen()
    cases = read_json(HERE / "private/cases.json")["holdout"]
    source = HERE / "submissions" / arm / repeat
    out = HERE / "followup-prompts" / arm / repeat
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise ValueError("followup prompt directory already populated")
    sealed = {}
    answers = []
    screens = []
    for case in cases:
        tid = case["task_id"]
        path = source / f"{tid}.json"
        candidate = read_json(path)
        if candidate.get("task_id") != tid:
            raise ValueError("filename/task_id mismatch")
        sealed[str(path.relative_to(HERE))] = hashlib.sha256(path.read_bytes()).hexdigest()
        if case["category"] != "clarify":
            continue
        score = evaluate(candidate, None, case)
        screens.append({"task_id": tid, "automatic_screen_passed": score["accepted"]})
        if score["accepted"]:
            answers.append({"task_id": tid, "user_answer": case["clarification"]["simulated_answer"]})
    write_json(out / "answers.json", answers)
    write_json(out / "controller-record.json", {"sealed_at_utc": datetime.now(timezone.utc).isoformat(),
               "primary_sha256": sealed, "initial_clarification_screens": screens,
               "answered_count": len(answers), "fixed_denominator": 4})
    rel = f"experiments/codex_modeling_round2/followups/{arm}/{repeat}"
    text = f"""The primary 24 responses are sealed. Do not modify any of them.
This is the preregistered simulated-user clarification follow-up, separately scored.
Only additional input: experiments/codex_modeling_round2/followup-prompts/{arm}/{repeat}/answers.json.
Do not read controller-record.json, private data, results, or other authors.
Use these exact user answers together with your own original requests and the
public documents already allowed in your assigned prompt. No other business
information is supplied. For each answered task, produce a complete candidate
with the same task_id at {rel}/<task_id>.json. If a necessary gap remains,
identify it honestly. You may serialize JSON and read your own follow-up files.
Keep the original A/B/C execution allowance: A/B no compilation or execution;
C at most three public validations per answered model, initial plus two revisions.
"""
    if arm == "C":
        text += f"""Preserve attempts at {rel}/attempts/<task_id>-v0.json (v1,v2 if revised).
Use only:
PYTHONPATH=src:/workspace/scratch/b3b3538782dd/pilot-deps python experiments/codex_modeling_round2/validate.py --candidate {rel}/attempts/<task_id>-v0.json --out experiments/codex_modeling_round2/feedback/followups/{arm}/{repeat}/<task_id>-v0
Inspect only your own resulting feedback. Never invoke private evaluation.
"""
    text += f"""Write {rel}/log.json with real UTC start/end times, files read,
validation_calls and revisions. Maximum stage wall time 600 seconds, record
any overrun. No additional model ID or cost data is available. Finish after
the answered tasks; this stage does not disclose primary acceptance scores.
"""
    (out / "prompt.txt").write_text(text, encoding="utf-8")
    return {"arm": arm, "repeat": repeat, "answers": len(answers), "prompt": str(out / "prompt.txt")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("arm", choices=["A", "B", "C"])
    parser.add_argument("repeat", choices=["r1", "r2", "r3"])
    args = parser.parse_args()
    print(json.dumps(prepare(args.arm, args.repeat), ensure_ascii=False))
