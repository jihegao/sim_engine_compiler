# IR-native event profile (experimental, not legacy aircraft compatibility)

This profile has explicit integer `tick` time and an inclusive horizon. It does
not implement the canonical spare_mvp adapter, flight-exposure failure laws,
legacy-minute phases, partial resource reservations, or legacy RNG. Legacy
conformance must be tested separately against the existing runtime.

## Python entry points

`compile_business(raw)` validates and copies Business IR;
`lower_core(business)` materializes generic Core IR;
`compile_plan(core)` returns a frozen `Plan` with immutable tuple tables;
`plan.to_dict()` serializes it for Rust;
`run_plan(plan, seed=0, trace=True)` creates private mutable state.
`build_plan(raw)` composes the three compiler passes.
`Runtime(plan, seed, trace)` initializes one sample; `.run()` executes it once.
The constructor includes arrays, waiter sets, and initial event scheduling;
execution starts at the first event pop. This supports separate timing.

Business IR uses `schema='business/v1'`, `profile='ir-native-event-v1'`,
`domain='aircraft'|'production'`, `model_id`, `revision`, `time_unit='tick'`,
`horizon` and optional `rules`. Supported rules are exactly
`selection='first_available'`, `acquisition='atomic'`, `stock_abort='consume'`.
Aircraft uses `fleet`, `missions`, `maintenance`; production uses `machines`,
`jobs`, `outages`. Common tables are `resources` and `arrivals`.

* Asset: `{id,initial_state:0|1}` (default 0).
* Resource: `{id,kind:'capacity'|'stock',initial:nonnegative_integer}`.
* Mission/job: `{id,release:integer|null,duration:[lo,hi],eligible:[asset_id],
  needs:{resource_id:positive_integer},after:[process_id],repeat_delay:int|null}`.
  Defaults: release 0, eligible/needs/after empty, repeat_delay null. Empty
  eligible means asset-free work. A positive repeat_delay reactivates the same
  process after completion without pre-enumerating its future executions.
* Maintenance/outage: `{id,asset,at,duration:[lo,hi],needs:{...},repeat_every:int|null}`. It lowers to
  a `set_state` event and a process named `restore:<id>` with release null,
  required_state 1, finish_state 0, interruptible false. Its candidate is the
  named asset. Positive repeat_every repeats the event, default null means
  once only. Mission/job processes require and finish in state 0 and are
  interruptible.
* Arrival: `{id,time,resource,quantity}`. Resource must be stock, quantity > 0.

References, duplicate IDs, unsupported keys/rules/operations/profiles/units,
negative or noninteger time, impossible capacity needs and cyclic `after`
dependencies are rejected. No arbitrary expressions or generated code execute.
All scalar times, durations and quantities fit nonnegative signed 64-bit
integers. Stock addition beyond this range raises an explicit runtime error.
An event scheduled beyond the horizon is omitted; future time addition beyond
int64 necessarily falls beyond the allowed horizon and must never wrap around.
Lifecycle loops via repeated state-change events are allowed; only the declared
process predecessor graph must be a DAG. Recurrence reuses a fixed process slot
with an incrementing generation; no horizon-based trace expansion is needed.

## Serialized execution plan

`schema='plan/v1'`, `profile='ir-native-event-v1'`, `time_unit='tick'`, `horizon`,
`model_id`, `revision`, `business_fingerprint`, `core_fingerprint`,
`fingerprint`, `source_map`, and the following indexed tables:

* `assets`: `{id,initial_state}`.
* `resources`: `{id,kind,initial}`.
* `processes`: `{id,candidates:[asset_idx],required_state,finish_state,
  needs:[[resource_idx,qty]],duration:[lo,hi],after:[process_idx],
  release:integer|null,interruptible:bool,repeat_delay:integer|null}`.
* `events`: `{id,time,op:'set_state'|'add_stock',target:index,value:int,
  trigger:process_idx|null,repeat_every:integer|null}`.
* `successors`: lists of process indices derived from `after`.

The runtime contains no domain dispatch. Assets have a state (0 available,
1 disabled) and an exclusive owner, maintained separately. All candidate
selection is runtime first-fit in declared order. Acquisition of asset and all
resources is atomic; capacity returns on finish or interruption; stock is
consumed at start and is not refunded on interruption. This is a deliberate new
profile, not an optimization of legacy reservation semantics.

## Event and waiting semantics

Initial released-process activation events are enqueued in process-table order,
then explicit events in event-table order. Every event is ordered by `(time,
monotonic insertion_sequence)`. At the same tick this FIFO order is the semantic
rule; no implicit repair-first or failure-first phase exists. The horizon is
inclusive. Process status codes: 0 dormant, 1 waiting, 2 running, 3 complete,
4 aborted. There are separate activation and retry events. Initial release and
state-event trigger enqueue activation. An activation changes dormant→waiting;
for complete/aborted it additionally increments generation and resets
selected/started/finished/sampled to -1. Activation while waiting/running is
ignored. Successful activations and retry events attempt acquisition
immediately. Retry events only affect waiting processes. Dependency readiness
means every predecessor completed count > 0 (first-completion dependency),
even if the predecessor is now running another cycle.

Completion carries process generation and is ignored on status/generation
mismatch. Completion increments completed count and enqueues next activation
at now+repeat_delay if configured, then notifies waiting successors and resource
waiters in a single sorted union. Aborts do not automatically repeat.

Blocked processes register on all candidate assets and all requested resources,
even when a different condition currently blocks them. Capacity release,
asset release/state change and stock arrival collect a union of corresponding
waiters; eligible waiting process indices are enqueued in increasing order,
deduplicated while a request is already pending. Completion notifies successors
and resource/asset waiters in a single sorted union.

`set_state` acts only if the state changes. An interruptible owner is aborted
and releases capacity; a noninterruptible owner is a runtime error on a state
change. Then the state changes, the optional trigger activation is enqueued,
and targeted waiters are notified (trigger before waiters). An aborted process
does not retry unless subsequently activated by an explicit trigger.
Its already-scheduled completion event remains in the queue but is ignored by
status/generation. If state already equals the requested value, no trigger is
emitted. A repeating explicit event enqueues its next event before processing
the current event, even if the state change is a no-op.

`add_stock` adds quantity and notifies only waiters on that resource. Restoration
processes complete by setting their asset to state 0. The completion event's
capacity release and asset state change are visible to requests queued after it.

## Portable RNG and observable result

Seed is an integer in `[0,2^32-1]`. Each process samples only after successful
acquisition. Its stream identity is its stable business process ID, never its
dense index: FNV-1a32 over UTF-8 `str(seed)+'|'+id+'|'+str(generation)` (first
generation 0), initial 2166136261,
each step `((h xor byte)*16777619) mod 2^32`. Apply xorshift32 once:
`x ^= x<<13; x ^= x>>17; x ^= x<<5` with uint32 masking after each operation.
The duration is `lo + x % (hi-lo+1)`. This toy integer-uniform RNG exists for
portable reproducible conformance; it is not a validated Monte Carlo generator.
Fixed durations do not consume a random request. No RNG tape is sampled on retry.

Result fields: `profile`, `fingerprint`, `seed`, `assets` (integer final states),
`owners` (process index or -1), `resources` (integer final amounts),
`status` (integer codes), `selected` (asset index, -1 for none/not selected),
`started`, `finished` (tick or -1), `sampled` (duration or -1), `generation`
(initial 0), `completed` (initial 0), and `trace`. Aborts leave finished=-1.
Trace entries are fixed arrays `[time,kind,process_or_event_id,asset_id_or_empty,
value]`: start(duration), complete(0), abort(0), state(new_state),
stock(new available total), random(sampled_duration). The random entry
immediately precedes start. State entries use the explicit event ID and target
asset ID; stock entries use the explicit event ID and empty asset ID.
Completion trace follows updates with no separate state trace for finish_state;
abort trace precedes explicit state trace. Generation is inferred from process
activation order in trace; it is not appended to stable process IDs.
With trace disabled, trace is `[]`; all semantic state and sampled durations
must remain identical. A `diagnostics` object records execution counters and is
excluded from cross-engine semantic equality (implementations may do different
amounts of work). No wait/retry trace entries are emitted.

Zero-duration jobs are allowed. A default 10,000,000 popped-event budget rejects
excessive execution. Recurrence has positive delays and a finite horizon. This prototype has no cancellation
API, parallel steps inside one process, transport routes, shared asset occupancy,
hot model/state edits, cache persistence, or incremental recompilation.


## Immutability and work counters

Plan fingerprint hashes all serialized plan fields except fingerprint itself.
Semantic comparisons include fingerprint but exclude diagnostics.
Python Plan and its nested records are frozen dataclasses with tuple relations;
source_map is stored as immutable tuples. Each Runtime owns fresh mutable arrays,
waiter sets, generation counters and event heap. Exporting `.to_dict()` creates
an independent JSON-compatible object; modifying it does not change the Plan.
Python executes typed compiler-produced plans and does not expose an untrusted
serialized Plan loader. Its runtime checks envelope tags and operation support;
these checks are not a complete validator for manually forged dataclass objects.
Rust supplies the independently validated serialized plan boundary.

`events_popped`, `request_attempts`, `candidate_checks`, `waiter_visits` and
`stale_completions` count actual runtime work. They are not domain metrics.
First-fit candidate search can be linear in candidates, and a genuinely shared
resource can wake many waiters; this profile makes neither operation constant
time. No idle-horizon tick loop exists. Initialization and output still scale
with the number of represented assets and processes.
