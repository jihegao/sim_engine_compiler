# Strict input validation follow-up

Status: the three gaps below are now rejected by Python canonical compilation and Rust AOT. See [the scoped validation contract](../../docs/strict-work-input-validation.md). The original experiment results remain historical evidence and are not rewritten.

The three probes below are saved in `legacy_results.json` and are reproducible with `legacy_cases.py --f35`. At the time of the original probes they compiled instead of returning explicit validation errors:

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
