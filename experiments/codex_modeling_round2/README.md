# Codex requirement-to-IR experiment, round 2

This experiment follows the first hosted Codex modeling pilot. It replaces field-oriented requests with business prose and evaluates the resulting bounded aircraft model configurations through the existing **Business IR → Core IR → Execution Plan → Python runtime** pipeline.

The model authors supply normalized model inputs, not compiler implementation or new operations. Engine source and first-pilot files are unchanged. The scope remains the synthetic `aircraft-bounded-events/v1` profile; this is not native SIMLOX equivalence, arbitrary complex-system modeling, or a deployed Riffoid service.

## Design

There are four development tasks and 24 formal tasks. Formal tasks contain only neutral IDs and business requests, with no public category labels. The private split is eight business-modeling tasks, eight mechanism-composition tasks, four missing-information tasks and four unsupported-capability tasks.

| Arm | Inputs | Authoring execution allowance |
| --- | --- | --- |
| A | Schema and business requests | No execution; one submission |
| B | A plus mechanism cards | No execution; one submission |
| C | B plus public compiler/runtime diagnostics and trace | Initial candidate plus at most two feedback-driven revisions |

Each arm has three fresh-context repetitions, for **216 initial task responses**, including **144 complete-information model opportunities**. All 24 tasks share a context within a repetition. Task order is shuffled deterministically by repetition and is identical across arms for that repetition. These responses are not independent statistical samples.

Every executable formal task has a hidden parameter intervention with independently hand-derived expected behavior. The intervention recompiles a copy of the submitted model with specified parameter changes; it tests the encoded mechanism under a changed scenario, not the author's ability to revise that scenario. The scorer checks critical business constraints, event timing, input binding, terminal state and resource ledgers. It accepts selected harmless representation differences, including resource-free preparation splitting, but is not a general semantic-equivalence solver.

Missing-information responses receive an automatic concept screen. Eligible authors receive the same preregistered simulated-user answers and submit follow-up models under the same arm's execution allowance. Follow-up completion has a fixed denominator of four cases per run, including cases that failed to ask. These are simulated interactions, not actual user interventions, and are excluded from the 216 primary responses.

Text responses also receive a separate, group-blinded AI semantic review. Automatic screening and AI review are reported separately; neither is represented as human review.

## Independent repair experiment

Six first-pilot scenarios supply erroneous models that all compile and execute but fail the frozen first-pilot acceptance contract. Three fresh participant contexts receive identical requirements and initial models, with different feedback:

| Condition | Feedback |
| --- | --- |
| N | Receipt only; no compilation or execution |
| D | Compilation diagnostics only; no execution |
| T | Execution trace plus limited preregistered public behavior probes |

Every condition submits revision 1, receives its assigned feedback, then submits revision 2, which may be unchanged. Final hidden scoring is never fed back. This is a one-repetition, six-case repair comparison derived from the first pilot, separate from the 24 formal modeling tasks. Final repair scoring uses the first pilot's stricter configuration and behavior contract; public probes cover only a subset. See `repair/README.md`.

## Freeze and isolation

`protocol.json` records the design before generation. `repair-frozen-inputs.json` freezes the repair treatment before its participants started. `frozen-inputs.json` freezes the formal modeling inputs, scorer and prompts after development calibration and before formal generation.

Final preflight found an underspecified nominal preparation-duration convention. `main-amendments.json` records its clarification in the main schema before formal generation; reference answers and engine semantics were unchanged. The already frozen repair treatment was not modified.

Participants receive only their allowed public files and own outputs. The filesystem is shared and access restrictions are instructions, not OS-enforced isolation. File-access and tool-call logs are agent reports. The exact hosted model snapshot, sampling state, token usage and cost are unavailable; all agents inherit the same session-model setting, with no separate API key configured.

`prepare_followup.py` and `repair/replay.py` are later controller convenience wrappers implementing the preregistered interaction/scoring policy. The underlying answer rubric, scorer, task mapping and feedback contracts were already frozen. Their addition is documented rather than backdated into the original freeze.

## Files and results

- `results/report.md`: observed results, failure analysis and interpretation.
- `results/summary.json`: primary and follow-up scores with fixed denominators.
- `results/repair-summary.json`: initial, revision-1 and revision-2 repair results.
- `results/control-tests.txt`: evaluator positive/negative and isolation controls.
- `results/evidence.tar.gz`: full runtime receipts, persisted IR, traces, public feedback and scoring records.
- `results/evidence-manifest.json`: archive and per-file SHA-256 hashes.
- `public/`, `prompts/`, `submissions/`, `followups/`: published instructions and saved author responses.
- `private/`: hand-authored control models, behavior expectations, interventions and mutations, withheld during generation.
- `review/`: methodology review and blinded AI review materials.

Development and formal scenarios share the same bounded mechanism family. The formal set is a set of new instances and selected combinations, not evidence of unseen-domain generalization. B's cards overlap with A's schema. C also changes compute and revision opportunity, so its treatment is not an equal-cost isolation of feedback alone.

## Replay

Use this branch, Python 3.12 and SimPy 4.1.1. The first-pilot experiment must be present at its pinned contents. Source and frozen-input hashes are checked by replay.

```bash
python -m venv .venv
.venv/bin/python -m pip install simpy==4.1.1
PYTHONPATH=src .venv/bin/python -m unittest discover \
  -s experiments/codex_modeling_round2 -p test_evaluator.py -v
PYTHONPATH=src .venv/bin/python experiments/codex_modeling_round2/replay.py \
  --out /tmp/codex-round2-main \
  --followups experiments/codex_modeling_round2/followups
PYTHONPATH=src .venv/bin/python experiments/codex_modeling_round2/repair/replay.py \
  --out /tmp/codex-round2-repair
```

Output directories must be empty. A nonzero exit indicates rejected submissions or execution/scoring errors; the deliberately incorrect repair initial models are expected to fail and do not cause a nonzero exit themselves. Replay reproduces saved-candidate execution and scoring, not hosted model generation. The experiment's control tests do not substitute for the repository's full CI suite.
