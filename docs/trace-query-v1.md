# Offline trace query v1 — issue #11 bounded slice

This is a read-only query of independently persisted result, request and Plan.
It neither runs a simulation nor changes instrumentation, RNG calls, scheduling,
trace collection, metrics, ledgers or terminal state. It is not full issue #11
acceptance and makes no performance/collection-overhead claim.

The identity and review dependencies from PR20 and PR23 are merged in `main`.
This slice is integrated on main commit
`2822a807ed35321aac061a6e058969ad845f51f1`. No migration of existing run/Plan
contracts is required.

## Support and evidence matrix

| Input or capability | v1 treatment |
| --- | --- |
| Python reference or Rust runtime, aircraft-support, unindexed `legacy-minute-v1` Plan, Full | Recorded event queries; always partial evidence. `backend=rust-runtime` is admitted |
| Python or Rust `event-time-v2` / O5 | Explicit `unsupported_backend_profile`; neither collector is admitted for this profile |
| Any other backend | Explicit `unsupported_backend` |
| Restricted `multi-server-queue-v1` result, Python or Rust | Recorded queue events with Business/Core/Plan links when the full bundle recompiles; no stable event IDs |
| Summary request | No event facts, `summary_observation` evidence insufficiency; not a claim of Python Summary collection |
| Old result without trace | No event facts, `trace_not_captured` |
| Missing raw Plan | No facts, `missing_plan`; no reconstruction from result |
| Indexed Plan, other domains/profiles | Rejected by public identity admission |
| Missing result sample/profile/run/backend fields | Caller-asserted binding, not authenticated execution |
| Raw matching Business/Core/Plan/lineage | Public APIs revalidate; exact references may link only if the result also records the matching Plan fingerprint |
| Missing lineage/partial bundle or missing result Plan fingerprint | No verified design links |
| Wrong Plan, mixed revision, inspection report used as raw bundle | Invalid; no events |
| Unknown event kind | Selected event explicitly `capability_limited`; no invented event semantics |

The supported finite event vocabulary and typed entity roles are frozen in
`trace_query/facts.py` from the pinned Python reference `_emit` call sites.
Process references come from explicit `process_id`/`job_id` fields, or the
versioned job-entity contract of those finite kinds. Conflicting recorded
references remain unknown. A job ID is not parsed into a design identity.

## API and request

```python
from sim_engine_compiler.trace_query import query_trace

report = query_trace(
    saved_result, saved_request, saved_plan,
    bundle=raw_bundle,  # optional raw artifacts, never an inspection report
    query={"time_start": 10, "time_end": 20, "limit": 25,
           "max_event_bytes": 65536},
)
```

The raw request requires `run_id`, `sample_index`, `seed` and
`backend: "python-reference"`. Optional fields are `observation` (`full`, the
default, or `summary`), `horizon` (default Plan duration), `parameters` (JSON
object), `engine_version`, `domain_package_version` and `source_truncated`
(boolean, default false). Unknown request/query keys are errors. Integer fields
reject booleans; all JSON numbers must be finite. Parameters and optional
versions are caller assertions, not reconstructed runtime provenance.

Result-recorded Plan fingerprint/seed/sample/profile and any recorded
run/backend/observation are cross-checked, never silently overwritten. The public
run identity explicitly says `proves_runtime_consumed_plan: false`.
Duplicate seeds are legal: stable identity is the declared run/sample pair.
Callers must allocate unique run/sample pairs; unsigned result files cannot
prove their assignment. Results and requests receive separate content digests.

## Filters, pagination, budgets and resolution

Version: `simulation-trace-query/v1`. Exact single-value filters are `run_id`,
`sample_index`, `entity`, `process`, `rule_id`, `event_id`; they are conjunctive.
Time window is **[time_start, time_end)**, with an inclusive lower and exclusive
upper endpoint. Absent bounds mean zero and unbounded respectively. Equal
endpoints are a valid empty window. Filtering preserves the supplied trace order,
including an explicitly diagnosed reordered trace; it never silently sorts or
renumbers events.

`offset` (default 0) and `limit` (default 100, range 0–1000) apply after filters.
`max_event_bytes` (default 65536, range 2–1048576) caps the **selected `events`
array's canonical JSON UTF-8 representation only** (`sort_keys=True`, compact
separators, `ensure_ascii=False`). It includes brackets and commas. Selection
stops before the first event that would exceed the budget, preserving a prefix;
it does not skip a large event to select a later one. A budget of 2 can emit an
empty array. The CLI's transport JSON uses ASCII escapes and whitespace and is
not itself this canonical byte representation.

This is neither a total-envelope/wire-byte limit, input-memory/CPU limit, runtime
collection budget nor proof that the original trace was bounded. The CLI limits
each input file to 128 MiB; the API is an in-memory API. Metadata, supplied request
parameters and diagnostics are outside the event-array budget. Do not use it as
a hostile-input sandbox or collection-overhead guarantee.

Coverage reports source projection coverage plus input, matched and selected
counts, and disjoint omissions by filter, page and byte budget. Their sum equals
`omitted_event_count`. Admitted reports remain `partial`: selected facts never
prove unrecorded causes or complete/authenticated execution. Empty results do
not prove that the modeled event never occurred.

`resolve_event_ids` accepts up to 32 unique stable IDs. An `event_id` filter also
gets a resolution. Resolution statuses are `selected`, `omitted` (reason filter,
page or budget), `not_recorded` (unresolved in supplied trace, not proof of
nonexistence), and `cross_sample`. IDs come from the public identity projector's
original recorded sequence, never the filtered/page index. Resolution is scoped
to the single validated run/sample; no cross-run joining is performed.

## What a fact means

`design_links.status=verified` means a static symbol/source-path match against a
validated bundle whose Plan fingerprint is also recorded by the result. It is
not proof that the runtime actually consumed that Plan, or causal evidence.
Without a result-recorded Plan fingerprint the static `review_identity` may
remain available, but event-to-design links are unavailable even for a valid bundle.

Each selected event retains public identity fields plus `trace-event-facts/v1`:
recorded fields/details, typed process reference, verified-or-unavailable design
links, and explicit evidence gaps. Source-path equality is a **design association**,
not a cause, dependency or unique triggering rule. Static coarse phase operations
do not prove that a specific runtime guard was evaluated. No adjacency-based
causal edges, invented candidate/guard/cache state or new random draws occur.

Capacity wait, shortage, cancellation and transport details are exposed only as
recorded. Absent details stay absent. Even when a wait detail contains `reason`,
it is the recorded reason, not a reconstructed counterfactual explanation.
Missing trigger/guard evidence remains unknown, and request/run metadata is
clearly distinct from event-recorded facts.

Duplicate sequences are invalid. Internal deleted sequences and reordering are
diagnosed as partial; declared truncation is partial. **Unsigned continuous tail
deletion cannot be detected**: a retained sequence 1..N and matching digests prove
only the supplied bytes, not that later events were never recorded. This limit is
machine-readable on every envelope, including invalid/unsupported reports.

## Reproducible offline CLI and #10 review association

The command writes only stdout; callers choose a new output location. Do not
redirect stdout over an input. A request and a query are ordinary JSON files:

```json
{"run_id":"b1-example","sample_index":0,"seed":7,"backend":"python-reference"}
```

```json
{"time_start":0,"time_end":20,"limit":25,"max_event_bytes":65536}
```

Assuming `runs/example/result.json` is an independently saved real run and
`runs/example/request.json` describes that run:

```bash
.venv/bin/python -m sim_engine_compiler.trace_query runs/example/result.json \
  --request runs/example/request.json \
  --plan tests/fixtures/identity_contract/b1/plan.json \
  --query runs/example/query.json
```

For a raw bundle, assemble a JSON object whose `business`, `core`, `plan`,
`lineage` values are the loaded JSON objects from the same persisted revision,
and pass `--bundle runs/example/raw-bundle.json`. The API route is:

```python
import json
from pathlib import Path
from sim_engine_compiler.review import export_review

source = Path("tests/fixtures/identity_contract/b1")
raw_bundle = {name: json.loads((source / f"{name}.json").read_text())
              for name in ("business", "core", "plan", "lineage")}
design = export_review(raw_bundle["core"], bundle=raw_bundle)
trace = query_trace(saved_result, saved_request, raw_bundle["plan"], bundle=raw_bundle)
assert trace["review_identity"]["export_fingerprint"] == design["export_fingerprint"]
```

An offline Cloud-side consumer can display the selected recorded facts alongside
the #10 design view using that exact review fingerprint and `view_id`. It must
retain `association_status`, process basis, gaps, omissions and partial status;
there is no server, UI or live Cloud integration in this delivery. Do not pass
`design` back as a raw bundle. Missing evidence must remain visible in the client.

CLI success/partial exits 0; invalid/unsupported exits 2. File errors and duplicate
JSON keys produce the same versioned machine envelope. `--help` describes flags.

## Verification and remaining issue #11 work

The four required test modules cover CLI persistence/read-only behavior, hostile
inputs and omission controls, facts/design association, and actual B1/B3/F35
Python executions. Real F35 seeds 0/1/7 use the full fixed horizon; source file
and complete result digests must remain unchanged by queries. An independent
review record accompanies the slice. CI requires collection-to-execution parity
and no skipped tests in any new module, retaining Rust/PyO3/mandatory MLIR gates.

The parent identity changes are bounded to recorded-event projection. Omitted ID
selection uses the already validated unique sequence set instead of comparing
every event with the entire included list; projected values and order are
unchanged. Projection also validates every event's `details` as an object or
null before any query filter, page, or output budget can hide malformed input.
Neither change adds simulation-runtime work.

Still unimplemented: new guard/candidate/cache collection, runtime collection
budgets, authenticated run manifests, richer rule/causal semantics, Rust/O5 query
acceptance, and collection/query-overhead measurements. No issue closure, merge,
native Windows/SIMLOX operation, paid pilot or research acceptance is implied.
