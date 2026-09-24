# Rust AOT aircraft-support compiler

This crate lowers canonical `aircraft-support-v1-input-v1` JSON into the same
versioned `ExecutionPlan` used by the Python reference and Rust runtime. Domain
rules stay in `aircraft_support.rs`; the generic runtime does not dispatch on a
domain name.

The CLI defaults to the accepted experimental `event-time-v2` profile and
writes a versioned binary Plan cache. The integrated cache format is
`sim-engine-plan-cache/v3`; the filename includes the format version so older
v2 files are not loaded and a new v3 entry is built from canonical input:

```bash
cargo build --release --manifest-path rust/compiler/Cargo.toml
rust/compiler/target/release/sim-engine-compiler-aot \
  tests/fixtures/spare_mvp/f35-43day-5352a0d/simulation-inputs.json \
  /tmp/f35.seplan \
  --cache-dir /tmp/sim-engine-plan-cache \
  --json-output /tmp/f35-plan.json
```

For a pre-Adapter repeat-model lookup, pass the Project JSON and the exact
Adapter/schema/runtime-config contract identity. The Project is only parsed and
canonically fingerprinted here; this compiler does not interpret Project
fields or replace the upstream `SimulationAdapter`:

```bash
rust/compiler/target/release/sim-engine-compiler-aot \
  /path/to/canonical-inputs.json /tmp/f35.seplan \
  --cache-dir /tmp/sim-engine-plan-cache \
  --project-json /path/to/project.json \
  --adapter-contract-version spare-mvp-5352a0d/aircraft-support-v1-project+input \
  --run-output /tmp/result.json
```

Cache loading fails closed on cache format, compiler version, Plan version,
semantic profile, canonical-input fingerprint, Project fingerprint and Adapter
contract identity. A changed Project or contract creates a different cache
path; a mismatched envelope is rejected rather than reused.

Five checked-in B1/B2/B3/F35 fixtures require parsed Plan equality with the
Python compiler. The O5 Plan must differ from the legacy Plan only in
`semantic_profile`, which also changes the Plan fingerprint.

## Python Monte Carlo boundary

The PyO3 extension is built from this crate because canonical lowering belongs
here and the dependency remains one-way (`compiler -> runtime`). Existing
`run_plan` and `run_batch` calls remain available. The heterogeneous entrypoint
is:

```python
from sim_engine_compiler import run_canonical_batch

envelope = run_canonical_batch(
    [{
        "sample_index": 0,
        "seed": 7,
        "sweep": {"failureRate": 1.1},
        "canonical_inputs": simulation_inputs,
    }],
    worker_threads=8,
    cache_dir="runs/sim-engine-cache",
)
```

Inputs are grouped by canonical SHA-256. Each group shares one immutable Plan
and prepared runtime layout, while all groups execute in one bounded Rayon
pool. The response contains stable-ordered `samples`, `failed_samples`,
`engine_metadata`, `plan_cache_status`, per-group cache identities, timings and
the actual worker count. Each successful sample includes top-level `metrics`
plus the full summary `result` (`sample_requests`, empty `trace`, metrics,
terminal state, time and stop reason). Cache envelopes are accepted only after
format/compiler/profile/source/Plan-fingerprint validation; invalid bytes are
never executed and are rebuilt solely from the supplied canonical input.

The production Linux wheel targets CPython 3.12+ via PyO3 `abi3-py312`. On a
Linux x86_64 builder with Python 3.12 and `uv`, run:

```bash
bash scripts/build_linux_wheel.sh
sha256sum dist/*.whl
```

The script embeds `git rev-parse HEAD` as `engine_metadata.build_commit`, uses
the locked Cargo graph, and emits a `manylinux_2_28` wheel under `dist/`.
