# Bounded aircraft event profile v1

`aircraft-bounded-events/v1` is an opt-in Python reference contract for the
twenty aircraft candidate chains. It adds continuous-time work/resource,
formation, maintenance and item-flow semantics that the existing minute Plan
cannot express faithfully. The existing aircraft product CLI, minute profiles,
Rust backend and their operation contracts remain unchanged.

This is a **restricted aircraft domain profile**, not a general-purpose
instruction set, a native SIMLOX interpreter, or a claim of full native parity.
There is no dispatch by case ID. Independent contract tests compose the same
operations with different fleet sizes, capacities, work breakdowns, maintenance
clocks, stock levels and transport routes.

## Entry and IR boundaries

```python
from sim_engine_compiler.integrations.spare_mvp.bounded import import_bounded_business
from sim_engine_compiler.domains.aircraft_support.bounded import lower_bounded, operation_contracts
from sim_engine_compiler.compiler.bounded_layout import compile_bounded
from sim_engine_compiler.domains.aircraft_support.bounded_runtime import BoundedAircraftRuntime

business = import_bounded_business(simulation_inputs)
core = lower_bounded(business)
plan = compile_bounded(core, operations=operation_contracts())
result = BoundedAircraftRuntime(plan).run()
```

Canonical inputs use `aircraft-bounded-input/v1`, an explicit profile, and
authored `model` entities. They are imported through `integrations/spare_mvp`;
neither Project JSON nor native table exports are interpreted. Existing
`aircraft-support-v1` input and Plan contracts do not silently select this path.

Business IR retains stable symbols, source paths and hours. Domain lowering
produces symbolic Core tables, integer microsecond operands, explicit step
breakdowns and the complete registered operation contract. Generic layout
resolves references to dense indexes and emits a source map. Each layer has
its own version and checksum; Plan records canonical, Business and Core
fingerprints. Serialization round-trips are exercised before execution. The
immutable document stores bytes; mutable dictionaries returned by `payload`
are copies. Per-run state, calendar, jobs, reservations, item locations and
parameters are outside the Plan.

`python-bounded-reference` is the only backend. Rust/product bundle adoption is
not claimed. Unknown fields, operations, profiles, units (all input time fields
end in `_hours`), references, duplicate identities, cyclic task dependencies,
nonfinite values and unsupported backends reject explicitly. A deserialized
Plan is independently validated before any event executes.

## Time, ordering and bounded operations

Time is rounded once to integer microseconds, never to minutes. Events are
ordered by `(tick, phase, insertion sequence)`. At the same time, completion
and arrival operations use phase 0, fault/PM drivers 5, mission notices 10,
dispatch 20, early feasibility cutoff 30 and final cutoff 40. Zero-time work
may enqueue an earlier phase at the same tick and then wake dispatch again;
this local convergence is bounded by the event budget. In particular, a work
completion and resource release at a launch cutoff can dispatch before the
cutoff; cancelling a partial task invalidates its old completion token.

All operations consume validated entity indexes or owned runtime tokens and
produce trace events, RunState updates and calendar events. `OPS` and
`operation_contracts()` register their state read/write sets, ordering, empty
random-request sets, backend and limits. The following are their domain
preconditions and effects:

| Operations | Preconditions and effect |
| --- | --- |
| `notify`, `dispatch` | Fixed mission demand; allocate free or turning aircraft by mission priority and stable identity, create work once, dispatch FIFO jobs, launch only a full prepared formation with successful completed dependencies. |
| `work_done` | Live job/token/step; release the exact atomic lease, complete the step and wake successors. Empty breakdown uses the scalar duration; a nonempty serial breakdown replaces it. |
| `early_deadline`, `deadline` | Waiting mission; at `start + delay - scalar` cancel an incomplete allocation or a permanently insufficient resource capacity. Temporary occupancy may wait until the final launch cutoff. This is the bounded fixed-capacity rule, not a universal native cancellation algorithm. |
| `mission_return`, `turnround_done` | Live launched mission/start token or turning aircraft; release mission ownership, accumulate flight exposure, trigger repair/PM/turnround, wake allocation. A zero-duration turnround is represented by the return transition. |
| `fault`, `damaged_arrival` | Explicit external driver hitting a healthy flying asset. Fault marks the mission aborted but retains its scheduled return. Damaged arrival ends a single-aircraft mission immediately. Neither operation generates failures nor computes native damage/return flight dynamics. |
| `repair_done` | Landed direct-repair asset; clear the failure and release the aircraft after the duration captured at repair creation. |
| `pm_due`, `pm_done` | Calendar PM waits for a free landed asset; calendar interval resets at completion. Flight PM accumulates only flight and checks its threshold on return, resets on completion. No in-flight PM interruption is modeled. |
| `remove_done` | Replacement repair with a mounted physical item; detach once, route the failed item to its repair node, allow fitting only after removal and spare arrival. |
| `item_repair_start`, `item_repair_done` | Detached item in repair transit/repair; finish repair into physical stock and discharge one eligible outstanding demand. |
| `supply_arrival`, `fit_done` | Correct in-transit/reserved physical item; clear the original backorder once, fit only a removed aircraft and install the item once. |
| `in_transfer` | New physical identity at a valid stock node; increment nominal and on-hand stock once. Ordinary issues change on-hand stock only; there is no reorder policy. |
| `set_repair_duration` | Existing direct-repair object, no repair in progress; change only the duration used by later repairs. Arbitrary live state edits, distributions and in-progress changes reject. |

Capacity acquisition is all-or-nothing across the step's resource list; release
uses an owned lease exactly once. Physical items have one explicit location:
installed, stock, reserved, supply transit, repair transit or item repair.
Capacity, reservation ownership, installed identity, stock membership and
physical item conservation are checked after every calendar event.

Each table/step list has at most 1,000 entries, report output at most 10,000
intervals, time within signed 64-bit microseconds, and the calendar at most
100,000 executed events. Horizon handling is inclusive for events at the bound;
unfinished state is preserved. No threads, subprocesses, external services or
random draws occur in the runtime.

## Native comparison scope

The companion `simulation-case-library` v2 suite executes 20 chains/35 native
variants, with a separately compiled parameter change and invalid-input control
for every chain. Expected observations are read only after base execution.
State integrals are also reconciled independently against flight and lease
events. Input, IR, Plan, source mapping, trace, observation, comparison and
control artifacts are saved with fingerprints.

Fifteen cases compare deterministic mapped native observations. D01, E01, E02
and I02 condition on published fault timestamps. I05 conditions on published
damaged-aircraft arrival timestamps; its damage generation and return-time
algorithm are outside acceptance. These five use the distinct
`external-events/v1` input contract. Driver times are input conditions and do
not count as response acceptance. Repair finishes, work durations, stock flow,
backorders, physical identities and resulting state are computed independently.
There is no claim of native RNG equivalence, distributional agreement, newly
executed native runs, all native report columns, automatic NL-to-IR success,
SysML tooling, or human gold approval.

The repository's published native receipts and signoffs remain the authority
for bounded source observations. Access to their original Windows raw logs is
not implied by reading those receipts. A fully native stochastic model is a
separate acceptance gate.

## Verification

```bash
PYTHONPATH=src python -m unittest discover -s tests/conformance -p test_bounded_events.py -v
```

23 executable contract tests cover at least two independent compositions of
resources, replacement, fleet and maintenance behavior, plus time boundaries,
dependency/priority changes, parameter changes, conservation, immutable plans,
invalid references, stale events, unsupported backends and calendar limits.
The companion suite supplies native-observation acceptance separately from
these operation reuse tests. No existing profile source is modified.
