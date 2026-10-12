# Codex model-authoring pilot

This experiment tests whether hosted Codex agents can turn bounded, synthetic system requirements into complete model payloads consumed by this repository's existing compiler and runtime.

The executed path is **model payload → Business IR → Core IR → Execution Plan → Python bounded runtime**. Each IR is persisted and reloaded before the next stage. The model authors supply the model payload; the existing compiler constructs the three IR documents. No engine code is changed.

This is an initial feasibility experiment, not a demonstration of arbitrary complex-system modeling, native SIMLOX equivalence, or production reliability. It uses `aircraft-bounded-events/v1`, deterministic durations, and externally supplied fault times. It does not train or fine-tune a model.

## Experimental design

| Arm | Available information | Execution feedback during authoring |
| --- | --- | --- |
| A | Schema guide and tasks | None; one submission |
| B | A plus reusable mechanism cards | None; one submission |
| C | B plus public compiler/runtime feedback | Initial validation plus at most two revisions per executable task |

All three arms use fresh agent contexts and inherit the current Codex Work session model. The host does not expose an exact model snapshot, token counts, cost, or inference-only timing; those values remain null. This uses existing hosted Codex agents without a separately configured OpenAI API key. It does not expose the session model as a reusable external inference endpoint.

Each arm handles the same eight tasks in one context. T01–T06 require executable models; T07 requires asking for missing resource capacity; T08 requires identifying unsupported endogenous random fault sampling. These three kinds of result are reported separately. C's additional execution and revision opportunity is part of its treatment, so this is not a comparison at equal compute cost.

The 13 files listed in `frozen-inputs.json` were hashed before generation. Agent prompts prohibit reading the private scorer, expected outcomes, engine implementation, and other arms. This is instruction-based isolation on a shared filesystem, not an enforced security boundary. Agents may inspect their own outputs. C may inspect only its public validation artifacts, never final evaluation feedback.

## Scoring and evidence

The private evaluator checks required model structure and independently hand-derived observable behavior, including trace events, stale-event suppression, resource balance, and end states. Compiler acceptance alone is insufficient. Correct controls and deliberately incorrect mechanisms verify the evaluator before model generation.

- `protocol.json`: preregistered scope, model metadata, budgets, and limitations.
- `public/`: tasks, schema guide, and mechanism cards.
- `private/oracles.json`, `evaluator.py`, `test_evaluator.py`: independent final assessment and controls; withheld during generation.
- `prompts/`: exact participant instructions, including the original environment paths.
- `submissions/`: saved candidates, authoring logs, and C's immutable attempts.
- `results/summary.json`: primary scores from the submitted candidates.
- `results/report.md`: observed results and interpretation.
- `results/evidence.zip`: full execution receipts, persisted IR, traces, diagnostic feedback, and scoring details.
- `controller-log.json`: dispatch/completion observations and elapsed-time accounting.

T07's follow-up uses the preregistered simulated user answer `resources/staff/capacity = 2`. It is a separate demonstration, not part of the primary executable-model score. The answered scenario has the same requirements as T01; a clearly labeled copy is assessed against that contract.

## Replay execution and scoring

Use a checkout containing this experiment and the pinned engine revision recorded in `source-manifest.json`, with Python 3.12 and SimPy 4.1.1 available:

```bash
python -m venv .venv
.venv/bin/python -m pip install simpy==4.1.1
PYTHONPATH=src .venv/bin/python -m unittest discover \
  -s experiments/codex_modeling_pilot -p test_evaluator.py -v
PYTHONPATH=src .venv/bin/python experiments/codex_modeling_pilot/replay.py \
  --out /tmp/codex-modeling-pilot-replay
```

The output directory must be empty. Replay verifies frozen experiment inputs and the executing engine source hashes, then runs and scores all 24 saved submissions. A nonzero exit means one or more submissions were rejected or an operational error occurred; inspect `summary.json`. Replaying stored candidates does not reproduce hosted model generation, whose exact snapshot and sampling state are unavailable.

To validate a new candidate without invoking the final scorer:

```bash
PYTHONPATH=src .venv/bin/python experiments/codex_modeling_pilot/runner.py validate \
  --candidate candidate.json --out /tmp/new-model-feedback
```

Do not describe generation wall time as inference latency or the small runtime measurements as a throughput benchmark. The original 40 bounded runtime conformance tests and 16 evaluator tests are scoped checks; they do not substitute for the repository's complete CI suite.
