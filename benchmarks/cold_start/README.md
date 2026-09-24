# spare_mvp cold-start AOT and Plan-cache experiment

Date: 2026-09-21

Status: Rust canonical-input lowering and a versioned binary Plan cache are
implemented and measured. Rust Project→canonical Adapter migration is **not**
implemented. The first-start and repeat-model conclusions must therefore be
reported separately.

## Fixed source boundary

- `spare_mvp`: commit `5352a0d7757cbac012c75d516d1a7ac4ff15aa2a`, clean AMD128 checkout.
- Project: `project-j16-8aircraft-43day-availability-20260727-copy-2`.
- Runtime candidate: sim-engine commit `1779e31` plus this experiment,
  `event-time-v2`, summary observation, seed `0`.
- Formal performance host: AMD128 Linux x86_64. Rust build time is excluded.
- Each performance cell has 3 warmups and 30 measured repetitions. Tables use
  medians; raw rows and binary identity are in
  `results/amd128-project-cache-o5-20260921.json`.

## Adapter profile

Seven uninstrumented repetitions produced these medians:

| Stage | Median |
|---|---:|
| `ProjectJsonExporter.export` | 542.885 ms |
| `SimulationAdapter.compile_scenario` | 177.601 ms |
| canonical input schema validation | 44.065 ms |
| canonical input fingerprint | 3.829 ms |
| Project→validated canonical total | 768.338 ms |

This confirms that the old 0.735 s “Adapter” bucket is actually dominated by
Project export/normalization plus Adapter work, not database I/O. Under
`cProfile` (whose times must not be added to the uninstrumented medians), the
Exporter spent 0.833 s cumulative in JSON Schema validation and 0.816 s in
`deepcopy`; Adapter compilation spent 0.712 s cumulative in `deepcopy`.

Raw stage rows and the top 50 cumulative functions are in
`results/amd128-adapter-profile-20260921.json`.

## Rust AOT and cache result

| Fixed canonical/Project stage | AMD128 median |
|---|---:|
| current Python Plan compile | 17.173 ms |
| Rust AOT Plan compile only | 10.137 ms |
| Rust cache miss, through binary Plan output | 25.422 ms internal / 28.337 ms process wall |
| Rust cache miss + O5 summary execution | 98.234 ms internal / 101.674 ms process wall |
| pre-Adapter Project cache hit, Plan output | 8.557 ms internal / 10.664 ms process wall |
| pre-Adapter Project cache hit + O5 summary execution | 84.821 ms internal / 88.339 ms process wall |

The cache-hit execution row contains Project JSON read/parse/fingerprint,
binary cache decode, RunState initialization, O5 execution, result construction
and file output. Its execution substage was 60.990 ms and initialization was
7.685 ms. It does not invoke `ProjectJsonExporter`, `SimulationAdapter`, or the
canonical Plan compiler.

The older upstream `44.4 ms` compiled-route measurement and this repository's
`17.173 ms` Python Plan compiler are different implementations and measurement
boundaries. The directly comparable result here is 17.173→10.137 ms, only
about 1.69× for lowering and a 7.04 ms absolute saving. This independently
confirms that Plan compilation alone cannot materially change the roughly
0.85 s first-start path.

Combining the separately measured Project→validated-canonical median with the
Rust miss+run median reconstructs about 0.867 s for the still-Python first
path. This is a stage reconstruction, not a single integrated timing. By
contrast, the repeat-model cache hit was directly measured at 88.339 ms process
wall, about 9.8× below that reconstructed first path and inside the proposed
0.08–0.15 s target.

## Cache identity and safety

The `sim-engine-plan-cache/v2` envelope has a binary magic header and bincode
payload. It records and validates:

- canonical Project JSON SHA-256;
- explicit Adapter/schema/runtime-config contract version supplied by the caller;
- canonical input SHA-256;
- Rust compiler version;
- Plan schema version and semantic profile;
- Plan fingerprint.

The pre-Adapter key contains the Project fingerprint, Adapter-contract digest,
compiler version and semantic profile. Cache decode rejects mismatches and
trailing bytes. Writes use a same-directory temporary file followed by rename.

## Semantic evidence

- Rust AOT output equals the parsed Python Plan for all five checked-in
  B1/B2/B3/F35 fixtures.
- F35 Plan fingerprint for legacy remains
  `7a0915f399c91bef78171c8d37cb6e6961fd8fa261a5419eeb3633fc62286c3d`.
- The O5 Plan is structurally equal after normalizing only
  `semantic_profile`; its distinct identity is enforced by tests and cache
  validation.
- Existing O5 differential evidence still owns runtime equivalence. This
  experiment did not generate a new legacy oracle.

## Reproduce

Profile the fixed upstream boundary:

```bash
/path/to/python3.12 benchmarks/cold_start/profile_spare_mvp.py \
  --spare-mvp-root /home/g/Models/spare_mvp \
  --database /home/g/Models/spare_mvp/runs/system-start/spare_mvp.sqlite3 \
  --project-id project-j16-8aircraft-43day-availability-20260727-copy-2 \
  --output /tmp/adapter-profile.json
```

Benchmark Rust AOT/cache after producing a clean Project JSON through the
upstream exporter:

```bash
PYTHONPATH=src python3.12 benchmarks/cold_start/run_benchmark.py \
  --project-json /path/to/clean-project.json \
  --warmups 3 --repeats 30 \
  --output /tmp/cold-start.json
```

## Unimplemented boundary

The 2.5–4× first-start target remains unverified because the canonical Adapter
is still Python. A valid Rust Adapter must port the upstream clean-Project
schema validation, normalization, stable-ID/reference resolution, unit
conversion, provenance/default diagnostics and canonical-input construction.
It must compare canonical bytes and diagnostics against the fixed upstream
contract; a smaller F35-only Project interpreter would violate the integration
boundary and is intentionally not included here.
