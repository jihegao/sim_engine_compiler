# Rust AOT aircraft-support compiler

This crate lowers canonical `aircraft-support-v1-input-v1` JSON into the same
versioned `ExecutionPlan` used by the Python reference and Rust runtime. Domain
rules stay in `aircraft_support.rs`; the generic runtime does not dispatch on a
domain name.

The CLI defaults to the accepted experimental `event-time-v2` profile and
writes a versioned binary Plan cache:

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
