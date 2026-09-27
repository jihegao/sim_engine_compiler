# ABM source semantics v1

Status: restricted opt-in extension of `abm-tick-v1`. It exists for source
conformance cases such as NetLogo Segregation; it is not a NetLogo interpreter.
Plans without the extension retain their existing payload, fingerprint, and
runtime behavior.

## Plan contract

An extended payload adds exactly one top-level member:

```json
{
  "source_semantics": {
    "schema_version": "abm-source-semantics/v1",
    "initialization": [],
    "stop_timing": "before_tick"
  }
}
```

The member is omitted for legacy plans. An empty initialization list is valid
for fixed-initial-state conformance cases. Initialization and ordinary phase
IDs share one namespace. Initialization phases use the ordinary phase shape,
require `read_view: "current"` and `commit_mode: "immediate"`, and execute once
at tick `-1` before the first stop observation. Each phase fixes its actor set at
phase start. A child created in one initialization phase is visible to later
initialization phases and to tick 0, but never joins its creator phase.

An extended initialization or ordinary phase may add a non-null `where`
expression. The member is omitted for an unfiltered phase. The expression must
be pure: a nested `random` expression is rejected. It is evaluated for all
candidate actors against the phase-start snapshot before any traversal-key draw.

Initialization patch phases may use:

```json
{
  "op": "sprout",
  "guard": null,
  "kind": "person",
  "count": 1,
  "vars": {
    "heading": {"op": "random", "distribution": "uniform",
                "address": "schelling.initial-heading", "args": [0, 360]}
  },
  "address": "schelling.person"
}
```

`guard`, `count`, and `vars` use the patch as their expression context. Child
identity is
`<patch-id>::<address>::init::<phase-id>::<ordinal>` and therefore uses stable
business IDs rather than dense layout indices. The child starts at the exact
patch center. Source setup must explicitly sample and persist heading as shown;
its request is addressed by the stable patch ID and is validated by a supplied
tape in controlled cases. `sprout` is rejected outside patch initialization phases;
initialization supports only `set`, `increment`, and `sprout`.

The source movement operation is an ordinary `move` with this exact additional
member:

```json
{
  "op": "move",
  "guard": null,
  "mode": "local_rejection",
  "x": null,
  "y": null,
  "neighborhood": null,
  "address": null,
  "heading_step": null,
  "local_rejection": {
    "turn_address": "schelling.turn",
    "distance_address": "schelling.distance",
    "turn_bounds": [0, 360],
    "distance_bounds": [0, 10],
    "attempt_budget": 1024
  }
}
```

It is accepted only in an ordinary agent phase with current reads, immediate
commits, and toroidal topology. Every attempt draws a uniform right turn and a
uniform distance. It updates heading and continuous position before testing the
current occupancy of `patch-here`; the mover is excluded. A rejection retains
the new heading and position for the next attempt. Success snaps position to the
patch center and preserves heading. Exhaustion raises
`random_attempt_budget_exhausted`; it never silently stays or teleports.

Each attempt emits `move_attempt` with `ordinal` (zero based), `turn`,
`distance`, `from`, `trial_position`, `patch: [x,y]`, `accepted`,
`heading_before`, and `heading_after`. An accepted attempt is followed by the
existing `moved` event representing the centering write, from the trial position
to the patch center.

With `stop_timing: "before_tick"`, conditions are checked at the start of each
prospective transition, including tick 0, and not after a completed transition.
Their expression must be pure (nested random draws are rejected), and evaluation
uses the diagnostic phase label `before_tick` at every check.
If the last allowed transition makes the condition true, the result remains
`stop_reason: "max_ticks"`; the post-state and completed tick still exist.

## Strict random value tape

The tape is a run argument and is never embedded in a Plan:

```json
{
  "schema_version": "abm-random-tape/v1",
  "requests": [{
    "tick": 0,
    "phase": "move",
    "address": "schelling.turn",
    "entity_id": "person-a",
    "occurrence": 0,
    "distribution": "uniform",
    "args": [0, 360],
    "value": 90.0
  }]
}
```

Initialization requests use tick `-1`. Entries are consumed in order and must
match tick, phase, stable entity ID, address, occurrence, distribution, and
arguments. Supplied values must be finite and inside their distribution domain.
Missing, mismatched, and unused requests raise `random_tape_missing`,
`random_tape_mismatch`, and `random_tape_unused`, respectively. Without a tape,
the existing stable named RNG is used.

Python accepts the envelope through
`run_abm_plan(..., random_tape=tape)` or an optional `random_tape` member on a
batch request. Existing two-member batch requests remain valid. Result
`random_requests` retains the pre-existing shape, including `sequence`, and
records the supplied values.

## Deliberate limits

This version fixes the turn and distance bounds above, requires a torus for the
retrying movement kernel, and adds no general recursion, source-language
evaluation, sequential PRNG emulation, running-world mutation, or importer.
Weighted source similarity is represented with the existing explicit
aggregation/expression primitives; division by zero remains a runtime error and
must not be replaced by a sentinel under the source metric name.
