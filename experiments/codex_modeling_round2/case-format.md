# Round 2 case format (controller and grader only)

Public files `public/development.json` and `public/holdout.json` contain arrays of
objects with **only** `task_id` and `request`. Do not expose this document, private
cases, generator, categories, reference models, interventions, or mutations to
modeling agents. Task requests are business prose, not field-copy exercises.

`private/cases.json` is an object with `schema_version`, `method`, `development`,
and `holdout`. Each case has:

- `task_id`, `category`: `modeling`, `composition`, `clarify`, or `unsupported`.
- `request`: exact public business request.
- `requirements`: list of `{id,text}` for traceability.
- `reference_model`: hand-authored bounded model for internal controls only.
  For clarification this is the model **after** the preregistered answer;
  unsupported has null.
- `constraints`: list of declarative business assertions described below.
- `behavior`: hand-calculated trace assertions, never runtime-derived.
- `manual_derivation`: explicit arithmetic and business reasoning.
- `interventions`: held-out counterfactuals, each `{id,changes,behavior,manual_derivation}`.
- `mutations`: incorrect candidate changes, each `{id,changes,expected_failed_ids}`.
- `clarification` (if applicable): `{questions:[{concept,keyword_groups,field_aliases}],simulated_answer,answered_case}`.
  `answered_case` repeats the complete executable contract with category modeling
  and the original task_id; the controller uses it after the fixed answer.
  Each keyword group is a list of alternatives; all groups must match in a
  question or short reason. This is automatic screening, not a semantic judge.
- `unsupported` (if applicable): `{keyword_groups,capability_gap}`. All groups
  must match refusal explanation. Report this as automatic screening.

## Constraint forms

Every constraint has an `id` (a requirement ID with a descriptive suffix):

- `{"op":"eq","select":"missions[id=Patrol]/duration_hours","expected":0.5}`
- `{"op":"ids_eq","select":"aircraft","expected":["Falcon","Kite"]}`
  checks exactly the set of IDs, independent of row ordering.
- `{"op":"process_work","mission":"Patrol","expected":[{"duration_hours":0.2,"demands":{"Crew":1}}]}`
  resolves that mission's process. Empty steps means scalar duration with no
  demands. Merge only adjacent positive-duration steps with NO resource demands;
  ignore zero-duration/no-demand steps, and compare this normalized serial work
  sequence. Resource-bearing steps remain separate because intermediate
  release/reacquire can affect FIFO competition. Scalar and a resource-free
  explicit step can be equivalent. Do not assert process IDs or step IDs.
  Zero-duration resource steps must not be silently erased.

Selectors are slash-separated dictionary keys, list integer indexes (`steps/0`),
or table selectors (`aircraft[id=Falcon]`). A special selector
`mission_process[id=Patrol]` resolves the process referenced by that mission.
Numeric comparison tolerance may be 1e-9 hours; event `time_ticks` must match
rounded integer microseconds for asserted `hour` values. No full-model equality.

## Behavior assertions

Each item is `{id,kind,where,project,expected}`. `where` filters event fields by
exact equality; `project` extracts an ordered row per matching event. Expected
rows are compared in emitted order unless `unordered:true` is present.
`hour` expectations are also checked against event `time_ticks`.
An empty expected list requires absence of the selected event.

## Mutations and interventions

`changes` is a list of `{select,value}` assignments using the selector above.
An intervention creates a fresh isolated copy of the submitted model, recompiles
all IR layers, and runs the unmodified reference engine. It receives only its
own behavior assertions plus generic result/ledger/terminal checks; baseline
structural constraints and baseline expected trace do not apply to that changed
model. It is hidden from the generation agent. Mutation controls must violate
at least one named requirement/behavior assertion or reject compilation.

## Terminal and generic checks

All hand-authored executable scenarios finish by the horizon with every aircraft
ready, healthy and unassigned; zero active jobs, no outstanding resource leases,
no backorders. Check exact requested aircraft/resource identities, runtime
invariants, and independently reconstruct acquisitions/releases from trace.
The output's source-input fingerprint must bind to the actual compiled model.
For unsupported first responses no executable model is accepted. For clarify,
score both the initial necessary question and the final model after the fixed
answer; keep these metrics separate from complete-information modeling.
