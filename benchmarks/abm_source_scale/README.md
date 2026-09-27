# ABM current-read-view scale check

This bounded measurement evaluates the Rust runtime change that avoids cloning
the full world for each ordinary `current` read-view operation. It is a runtime
check for the Schelling source candidate in CSABench Issue #18, **not** a
NetLogo source-equivalence result, a Python speedup, or a general performance
adoption decision.

## Semantic gate before timing

- Measured base: compiler `main` commit
  `2822a807ed35321aac061a6e058969ad845f51f1`. The PR was later rebased
  onto `bf3df6b258d5acf6d8b0abdb07cbf9ef61f44a34`, whose intervening
  change did not touch the Rust runtime or its Cargo inputs.
- Candidate: the Rust change in this branch. `phase_start` still reads a phase
  snapshot; `local_rejection` still takes an operation snapshot because rejected
  attempts mutate the live mover. The added differential test checks immediate
  `current` writes against buffered `phase_start` writes in Python and Rust.
- `cargo +1.90.0 test --locked --release --manifest-path rust/runtime/Cargo.toml`
  passed, including 34 library tests. After the rebase and with the frozen
  Python reference source intact, the compiler suite passed with 448 tests,
  14 skips and 9 native binding tests deselected. The nine binding tests remain
  unverified in this isolated checkout.
- All six measured Rust result files have the same SHA-256:
  `6191f7bc85bc9980adbdf571423056fce642aa38e0183edccc4cefef6a4c332f`.
  This is exact file equality for the measured Plan and seed, not source-model
  equivalence.

## Input and timing boundary

- Committed input: `schelling_51x51_10tick_plan.json`, SHA-256
  `bedaec0309861c4bcab818d11c37290f06f120e34c31ddbadca0126e9d291d20`.
  Its Plan fingerprint is
  `a2b9215761ebc88a1ac69eb5992dc2534809c475daac0c79713b3baace03d479`.
  The candidate was built by CSABench's Schelling source-candidate builder with
  density 70, similarity threshold 30, 51×51 patches and a 10-tick horizon.
- Seed: 12347. Each process loaded the Plan and wrote the full JSON result;
  time includes process startup, Plan read/parse, execution, serialization and
  file write. There was no trace/profiler instrumentation. This is a one-seed,
  one-Plan end-to-end runtime check; compile time is outside the boundary.
  The ABM CLI does not expose a stage profile, so Plan load, initialization,
  execution, serialization and write are listed as included stages but not
  assigned individual time claims here.
- Host: AMD Ryzen Threadripper PRO 3995WX, 128 logical CPUs, Linux x86_64.
  The process was pinned to logical CPU 0 with `taskset -c 0`. Each invocation
  had a 240-second wall-time cap. `/usr/bin/time` recorded elapsed/user/system
  seconds and maximum RSS. Raw per-run figures are in `measurements.json`.
- Baseline release binary SHA-256:
  `316eeb625a4297b580821cb836d2ce90dee876efbbc7db2770cbcaf033ea536e`.
  Candidate release binary SHA-256:
  `8b35a8416acc5d7ea7c54180e21c94467323462661ba31c384720c142ea4f7e2`.
  Both used the same release Cargo manifest and lockfile on the same host.

The uninstrumented alternating sequence was base, candidate, candidate, base,
base, candidate, with the six runs serial and no compiler test concurrent.
Baseline wall times were 163.59, 164.32 and 163.79 seconds (median 163.79);
candidate wall times were 3.94, 3.93 and 3.95 seconds (median 3.94), about
41.57× lower elapsed time for this workload. Baseline maximum RSS was
172,880–172,884 KiB; candidate maximum RSS was 167,936 KiB. This result
supports removing the per-operation state clone on this plan. It does not
establish a speedup for other ABM plans, other domains, Python execution or
the eventual 100-tick source-equivalence ensemble.

Reproduction after building each exact revision's release binary:

```bash
/usr/bin/time -f 'wall=%e user=%U sys=%S rss_kb=%M' \
  taskset -c 0 ./rust/runtime/target/release/sim-engine-runtime \
  benchmarks/abm_source_scale/schelling_51x51_10tick_plan.json \
  /tmp/schelling-result.json --seed 12347
```

Do not replace historical compiler benchmark results with this bounded check.

## Python reference scale diagnostic (subsequent change)

The Python reference previously copied the entire world for every `current`
operation and again on each `set`/`increment` action. On a freshly compiled
51×51, density-70, threshold-30, one-tick Plan (seed `700000001`), the pinned
Python checkout timed out at 180 seconds while a sampled stack repeatedly
showed `copy.deepcopy` inside `_state_copy`. The Python change now reads the
live state for `current` operations and write targets while preserving the
deep `phase_start` snapshot. It is generic to the ABM profile and does not
dispatch on model identity.

On the same Plan, the modified Python reference completed in 5.39 seconds.
Its complete decoded result matched the independent Rust result exactly:
21,346 events, 11,308 random requests, metrics and final state. A tape
derived from each backend replayed exactly on the other backend. These are
development diagnostics, **not** a controlled Python performance benchmark;
the pre-change bound is a timeout, not a measured execution time. The
Schelling source model is not involved in this backend comparison.

A 100-tick-horizon Plan for threshold 30, seed `700000001`, stopped at tick 13
with `all-happy`. Python and Rust again produced exactly equal decoded results:
131,948 events and 14,570 random requests. This covers the full source
candidate world and a multi-tick run. At threshold 50 with the same seed and
horizon, both stopped at tick 16 with exactly equal results: 165,330 events
and 25,548 random requests. The two cases do not cover all parameters or seeds.

The separate historical SIMLOX A01/A02 pairing uses a frozen engine-source
baseline. The new Python ABM bytes are recorded as an explicit, SHA-pinned
checkout delta; the old baseline hash remains unchanged. Fresh pairing output
now records both the frozen baseline and executed-source fingerprints. This
does not retroactively change old evidence or imply SIMLOX native acceptance.
