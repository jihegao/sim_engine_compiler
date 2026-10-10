# Public identity foundation v1 (#10 / #11)

This is an offline Python package contract, not a SysML renderer, runtime
instrumentation layer, query service or proof of business correctness. It adds
no runtime fields and changes no Plan, scheduler, RNG or observation defaults.
The executable validators are authoritative; this document describes their
supported scope. Issues #10 and #11 remain open for export, collection and
query slices.

## Supported scope

| Input / consumer | v1 support | Boundary |
|---|---|---|
| Persisted aircraft Business v1 | Identity and validation | No hidden canonical input; available source paths preserved |
| Persisted aircraft Core v2 | Independent validation and identity | Core may be edited independently; original Business cannot be reconstructed |
| Unindexed aircraft Plan v1alpha2 + matching layer bundle | Verified layer association | Fingerprints alone are insufficient; relationships and layout must agree |
| Plan with `resource_dispatch_index` | Explicitly unsupported in identity v1 | Semantic fingerprint excludes this index; no silent acceptance without independent index validation |
| Coarse compatibility operations | Named, versioned operation coverage | Partial design mapping, not a complete rule-level representation |
| Existing aircraft result / Full trace | Offline run/sample/event references | Explicit caller binding is not authenticated execution provenance |
| Summary, absent/truncated/filtered trace | Structured evidence limitations | Missing observations cannot support a complete explanation |
| ABM / production experimental profiles | Explicit unsupported boundary | No implicit aircraft mapping, no claim of their complete design/trace support |
| Rust | Existing artifact/result input may be inspected by Python | No new native Rust identity API or runtime collection in this slice |

Aircraft profiles are `legacy-minute-v1` and `event-time-v2`, with
`stable-topological-serial` work and `legacy-sequential-v1` RNG. The layer
versions remain unchanged. Inspection produces versioned identity reports;
unknown schemas, profiles and operations do not fall back to a best-effort
aircraft interpretation.

Indexed Plans return `unsupported_resource_dispatch_index_identity_contract`.
This is a limitation of the **new Python identity inspector**, not a removal of
the existing Rust runtime's indexed Plan support. Use a separately validated,
original unindexed artifact bundle for this slice; do not strip an index and
pretend the resulting content digest authenticates the original indexed file.

Output contracts are `model-artifact-identity/v1`, `model-bundle-identity/v1`,
`simulation-run-identity/v1`, `simulation-event-references/v1` and
`simulation-event-reference-resolution/v1`. Status is one of `valid`, `partial`,
`invalid`, `unsupported`; diagnostics are stable machine-readable distinctions,
not text that consumers must parse. The exact JSON digest is a consistency
check, **not a signature or source authentication**.

## Artifact and bundle API

```python
import json
from pathlib import Path
from sim_engine_compiler.identity import inspect_artifact, inspect_bundle

root = Path("tests/fixtures/identity_contract/b1")
layers = {name: json.loads((root / f"{name}.json").read_text())
          for name in ("business", "core", "plan", "lineage")}
core_identity = inspect_artifact(layers["core"])
bundle_identity = inspect_bundle(**layers)
```

Only persisted JSON values are accepted. Inspection does not mutate inputs.
Reports include a schema version, status and structured diagnostics containing
`code`, `severity`, `stage`, `path`, `element_id` and `message`. Missing layers
and unsupported mapping coverage are distinct from invalid or conflicting
artifacts. Exact content digests are not interchangeable with existing semantic
Plan fingerprints; neither is a dense layout index a business identity.

A matching complete bundle can have `association_status="verified"` while its
overall `status="partial"`: compiler compatibility operations are too coarse
for full domain-rule mapping. A `partial` report by itself does not establish
verified association. Missing layers do not acquire inferred identity data.

Business IDs and Core symbols are preserved. A business element may relate to
several Core/Plan elements; Plan paths are revision-specific addresses. Layout
reordering may change paths and content fingerprints without changing existing
stable IDs. This does not authorize sorting away profile-sensitive execution or
RNG order. A standalone edited Core remains valid even when its old Business
association is no longer demonstrable.

Source location is separate from value origin: an available path does not prove
a value was explicit rather than defaulted, normalized or derived. Missing
producer versions or origin classifications must remain unknown; the inspecting
package version must never be substituted for the original producer identity.
Business entities, rule definitions, compiler operations and runtime process
instances are distinct categories. Missing rule or instance mappings are not
fabricated from a label or temporal adjacency.

## Offline CLI

```sh
PYTHONPATH=src .venv/bin/python -m sim_engine_compiler.identity artifact \
  tests/fixtures/identity_contract/f35/core.json
PYTHONPATH=src .venv/bin/python -m sim_engine_compiler.identity bundle \
  --business tests/fixtures/identity_contract/b1/business.json \
  --core tests/fixtures/identity_contract/b1/core.json \
  --plan tests/fixtures/identity_contract/b1/plan.json \
  --lineage tests/fixtures/identity_contract/b1/lineage.json
```

The CLI reads files and emits JSON to stdout; it never executes a model or
writes artifacts. Invalid/unsupported reports exit with code 2; valid/partial
reports exit 0. Consumers must inspect the association and coverage fields,
not equate a successful process exit with complete mapping. Duplicate JSON
keys and invalid JSON numbers are rejected rather than silently normalized.

## Run and event identity rules

`build_run_identity`, `inspect_run_identity`, `project_event_references` and
`resolve_event_reference` provide the offline run boundary. A caller-assigned
run identity and `sample_index` distinguish repeated seeds. Event identity uses
the original recorded sequence within that sample, never its position in a
filtered list. Filtering may remove evidence, not renumber surviving events.

```python
from sim_engine_compiler.identity import (
    build_run_identity, project_event_references, resolve_event_reference,
)

# `layers` is the persisted bundle loaded above. This identifies a request;
# it does not execute it. Each independent run needs a distinct caller run_id.
request_identity = build_run_identity(
    "experiment-001", 0, 7, layers["plan"], bundle=layers,
    observation="full",
)
# `result` must be an existing result for this request, loaded independently.
projection = project_event_references(request_identity, result)
if projection.get("events"):
    resolution = resolve_event_reference(projection, projection["events"][0]["event_id"])
```

`selected_sequences` filters original trace sequences and `truncated=True`
declares already incomplete evidence; these options do not change a simulation.
The observed result end `time` must be finite, nonnegative and no greater than
the requested horizon. Every event must lie between zero and that end time
(and within the horizon). A missing result time permits only partial evidence;
it is not inferred from the last event. Earlier natural completion is allowed:
equality with the requested horizon is not required. The projection retains
`evidence_binding.time_binding` (`request_horizon`, nullable `result_time`) so
the resolver can recheck these bounds. This checks temporal compatibility, not
whether an unobserved stop condition actually held: `stop_reason` is not
cross-validated against model termination rules in this offline slice.

A complete full trace has sequences `1..N` in original order (including an
empty trace when no events were recorded). Gaps or a non-1 starting sequence
produce `trace_sequence_incomplete`; reordering produces
`trace_sequence_reordered`. Both downgrade coverage to partial, with diagnostics,
without renumbering or sorting events. Explicit filtering cannot upgrade an
already incomplete trace, and the resolver independently checks any complete
coverage claim. A removed suffix without a gap cannot be detected from these
unauthenticated inputs alone; callers must declare truncation.

The contract cannot detect a caller who forges every raw input and digest. It
validates internal consistency and reports observable binding limits, rather
than granting provenance based on an unauthenticated report's `status` field.

Only actual recorded facts may be projected. When an event lacks an observed
trigger/cause, the relation is unknown; the preceding event is not its cause.
Missing trace, Summary observation, truncation, a foreign sample or an unresolved
reference produces machine-readable evidence limitations. A supplied result
cannot be promoted to authenticated execution evidence merely because its
caller supplied the expected Plan identity. New runtime capture, complete
blocking explanations, cached-guard provenance and bounded query services are
future #11 work.

## Validation and next consumers

```sh
PYTHONPATH=src .venv/bin/python -m pytest -q tests/conformance/test_identity*.py
```

Fixed [B1/F35 artifacts](../tests/fixtures/identity_contract/README.md) are loaded
from disk. Positive and negative checks cover layer mismatch, recomputed
checksums on invalid associations, edited Core, unknown operations/profiles,
source limitations, stable references and duplicate seeds. Existing aircraft
and ABM regression tests remain separate from identity checks.

#10 may consume verified bundle links to create design exports; missing layers
must remain visible. #11 may consume the same identity boundary for collection
and querying, without claiming that currently missing runtime relationships
have already been observed. Native Rust API support requires its own explicit
contract and tests. None of these follow-ups is performance acceptance, a
SIMLOX-equivalence claim, or authorization to enable new collection by default.
