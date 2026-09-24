# Strict input validation follow-up

Status: tracked separately from the O5/MLIR integration. These are known gaps in the production aircraft-support compatibility compiler; the integration PR does not change input acceptance or error behavior.

The three probes below are saved in `legacy_results.json` and are reproducible with `legacy_cases.py --f35`. They currently compile instead of returning explicit validation errors:

| Probe | Invalid input | Required behavior |
|---|---|---|
| `negative-work-duration` | A support job has `durationMinutes: -3`. | Reject with a path-specific nonnegative-duration diagnostic before creating an Execution Plan. |
| `unknown-equipment-component-reference` | An activity refers to `equipment_id: "nonexistent"`. | Reject with an unresolved component reference diagnostic that names the activity and field. |
| `duration-unit-string` | A minute-typed field contains `durationMinutes: "3 hours"`. | Reject the wrong type/unit explicitly; do not coerce or accept an ambiguous unit string. |

## Acceptance for the follow-up

- Add one negative conformance test per probe and assert both the typed error and source path.
- Validate these invariants in the compiler boundary before Execution Plan creation; preserve supported source normalization only when it is explicit and tested.
- Re-run the probes and the existing positive F35 oracle comparisons. Record the compiler commit, canonical input fingerprint, and diagnostic text.
- Keep these results separate from the O5 runtime and MLIR index correctness checks.

Evidence source: `experiments/ir_validation/legacy_results.json`, probes `negative-work-duration`, `unknown-equipment-component-reference`, and `duration-unit-string`.
