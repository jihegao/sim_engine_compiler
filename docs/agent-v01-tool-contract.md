# Agent tool contract for aircraft v0.1

This is an offline tool workflow for coding or modeling agents. It does not
require an Agent service, MCP server or online model. A human or Agent may
propose an edit; compiler validation and observed runs decide what is accepted.

1. `sim-engine inspect MODEL.simpack --business-output business.json` verifies
   the original bundle and exports its exact Business revision. Keep the
   original bundle immutable for comparison.
2. Edit only the intended `payload` field in a copy of `business.json`.
   Preserve business IDs, source paths, semantic profile and unrelated rules.
3. `sim-engine seal draft.json revised-business.json` explicitly produces a
   new persisted Business fingerprint after executable domain validation.
4. `sim-engine validate revised-business.json` must return `status=valid`.
   Reject any other status and inspect diagnostic `code`, `stage`, `path`.
5. `sim-engine compile revised-business.json revised.simpack` creates a new
   immutable bundle. Preserve its `bundle_id` and `plan_fingerprint`.
6. Run baseline and revised bundles with the same seed, observation and
   horizon using `sim-engine run ... --output ...`. For repeated samples use
   `batch --seeds ...`; repeated seed values retain distinct sample indexes.
7. `sim-engine diff before.json after.json` reports observed changes. State
   the exact source edit, bundle and Plan IDs, seed, changed metrics and first
   trace/terminal difference. Do not infer correctness from Agent judgement or
   from a single summary metric.

All command output is JSON. The CLI exits 2 for invalid input or unsupported
contract and 3 for native execution failure. Failed `validate` and `compile`
must not be treated as runnable artifacts. `seal` deliberately creates a new
revision; `compile` never silently repairs a stale Business fingerprint.
Unknown operations, profiles, units, references and indexed Plans are not
features to work around by deleting fields or rewriting metadata. Report the
diagnostic and request an explicit compiler/domain capability change.

The public Python SDK offers the same functions under `sim_engine_compiler`.
`ProductError` exposes `code`, `stage`, `path`, `message`. For automated flows,
pin package version `0.1.0` and preserve the original and edited `.simpack`
files with their run records. This workflow does not authorize edits to a
running model revision or claim that self-contained hashes authenticate a
publisher.
