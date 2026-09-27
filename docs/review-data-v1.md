# Offline model review data v1 (issue #10, bounded slice)

Implemented: persisted, validated Business or symbolic Core → deterministic
`model-review-data/v1` JSON, using `review-exporter/v1`. The exporter delegates
identity/schema/profile/operation and bundle association checks to the public
PR20 identity API. It does not require the original canonical Python object.

Dependency: **unmerged PR20**, exact commit
`c42d2679c6652a3f5e2d43c9ddc877ee5a388656`. This is a stacked change based on
`codex/engine-identity-contract-v1`, not a new identity authority.

## Support matrix

| Input or capability | v1 support |
| --- | --- |
| `aircraft-business-ir/v1` persisted JSON | Primary input; reviewed directly from saved sections |
| `simulation-core-ir/v2` persisted JSON | Primary input; edited valid Core can stand alone |
| `legacy-minute-v1`, `event-time-v2` | Supported aircraft profiles |
| Compatibility phase operations | Registered exact contracts only, named/versioned partial nodes |
| Unindexed aircraft Plan and `compiler-lineage/v2` | Optional association bundle only, not a primary design view |
| Entities/relations/processes/predecessors/state | Persisted static definitions, not live process instances |
| Rules/conditions/resources/parameters/units | Curated static projection; unavailable detail remains unknown/partial |
| Production experiment `business/v1`, `core/v1`, `ir-native-event-v1` | Explicitly unsupported; no reinterpretation as aircraft |
| ABM, indexed Plans, unknown operations/profiles | Explicitly rejected |
| SysML parser/renderer, trace capture, UI/service | Not implemented |

The exact supported schema versions, profiles, operation names and view names
are included in every API report's `support` object. The underlying compiler,
runtime, RNG and canonical Adapter semantics are unchanged.

## Identity, provenance and interpretation

`input_identity` is the public artifact-inspection report. Its artifact/content
fingerprints identify the supplied revision; missing human revision labels,
domain-package versions and compiler-producer versions remain `null/unknown`.
The current installed compiler version is not retroactively assigned as the
producer of an older artifact. Exporter version is separate and explicit.

Each view node preserves qualified layer/kind/element identity, independent of
array position. Artifact field locators are separate from available upstream
`source_path`. Neither persisted field presence nor a row's source path proves
that a user explicitly supplied a scalar. The vocabulary is
`explicit/default/normalized/derived/unknown`; old artifacts without evidence
remain `unknown`. A displayed unit is a curated field interpretation, not
invented source metadata. Unknown units remain unknown.

Core phase operations retain their versioned names and conservative effects.
They are not exact rules, state-machine transitions or executable-equivalence
claims. Cycles, choices and random behavior stay named rules; future paths and
runtime-created processes are never enumerated. Selected views are finite
projections, not a claim of complete semantic coverage.

Standalone Business/Core exports are valid to review but `status: partial`.
The `diagnostics` list includes code, severity, stage, path or element locator,
message and reason. Missing provenance and missing bundle are warnings. Unknown
profiles/operations produce `unsupported`; malformed or mixed revisions produce
`invalid`, with no admitted views or review mappings.
Rejected exports use `views: {}` rather than seven empty admitted views.
Successful selections enumerate `coverage.selected_views` and `omitted_views`;
even an all-view export is a partial semantic projection.

## Cross-layer links

`bundle` accepts raw persisted `business`, `core`, `plan`, `lineage` artifacts.
It never accepts a self-asserted verification report. The primary input must
exactly match the corresponding bundle artifact. Existing `inspect_bundle`
reproduces associations and verifies compiler lineage. Only a complete
`association_status: verified` bundle publishes review mappings; missing layers,
layout-order ambiguity or invalid associations publish none.

Business→Core mappings preserve the inspector's one-to-many arrays and
`persisted-source-path` basis; they do not prove precise rule equivalence.
Core→Plan links retain stable qualified symbols plus revision-specific Plan
locators with `verified-compiler-lineage/v2` basis. A Plan array index is a
locator, **never a business identity**. An edited standalone Core is not used
to reconstruct or guess its original Business template; its claimed source
fingerprint alone is not a verified association.
The nested bundle inspector may describe a Plan artifact's own array locators;
these are not cross-layer associations. Only the top-level review `mappings`
publish admitted relationships, and incomplete/invalid bundles clear both
top-level and nested provisional mappings.

`view_fingerprint` binds projected views. `export_fingerprint` binds the entire
report except itself. Input array reordering may change revision fingerprints
and locators, but cannot rename stable entities. Rule changes must change the
view/revision they affect. There are no timestamps in deterministic exports.

## Offline Python API

```python
import json
from pathlib import Path
from sim_engine_compiler.review import export_review

fixtures = Path("tests/fixtures/identity_contract/f35")
core = json.loads((fixtures / "core.json").read_text())
review = export_review(core)  # no canonical input, model execution or network
assert review["status"] == "partial"
assert review["mappings"]["core_to_plan"] == []

bundle = {name: json.loads((fixtures / f"{name}.json").read_text())
          for name in ("business", "core", "plan", "lineage")}
linked = export_review(core, bundle=bundle, views=["entities", "rules", "resources"])
assert linked["association_status"] == "verified"
```

## Offline CLI / cloud workspace example

Use a clean checkout of this stacked branch in any Linux/cloud terminal with
the pinned Python test environment installed. No API key, internet service,
model endpoint, local database or legacy source checkout is needed to export.
Dependency installation is a separate setup step. Keep persisted input fixtures
read-only and generated output outside the source fixture directory:

```sh
generated_dir=$(mktemp -d)
PYTHONPATH=src .venv/bin/python -m sim_engine_compiler.review export \
  tests/fixtures/identity_contract/b1/business.json > "$generated_dir/b1-review.json"
PYTHONPATH=src .venv/bin/python -m sim_engine_compiler.review export \
  tests/fixtures/identity_contract/f35/core.json \
  --business tests/fixtures/identity_contract/f35/business.json \
  --core tests/fixtures/identity_contract/f35/core.json \
  --plan tests/fixtures/identity_contract/f35/plan.json \
  --lineage tests/fixtures/identity_contract/f35/lineage.json \
  > "$generated_dir/f35-linked-review.json"
```

Repeat `--view` to select supported views. Empty, duplicate or unknown view
selections fail closed. CLI emits JSON to stdout; success/partial exit 0,
invalid/unsupported exit 2. Duplicate JSON keys, non-finite values and excessive
nesting are rejected; each input file is limited to 32 MiB. The command never
writes model inputs or executes a simulation.

## Verification boundary

Tests use the existing hash-frozen B1 and real F35 persisted fixtures, with
meaningful entity, predecessor, resource, parameter and rule assertions.
Controls cover independent Core edits, stale/missing/tampered lineage,
primary/bundle mismatch, table reordering, missing provenance, unknown
operations/profiles/views and production isolation. The CI collection/JUnit
verifier requires every new review test module to actually execute without
skips, retaining the existing mandatory Rust/PyO3/MLIR steps.

This is an initial review-data slice, not completion of issue #10 or a SysML
deliverable. Local optional MLIR skips are not acceptance for that path; use
the exact-head remote CI receipt for mandatory integration results.
