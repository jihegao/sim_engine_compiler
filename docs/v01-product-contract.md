# v0.1 aircraft compiler product contract (Issue #29)

Status: repository v0.1 implementation with local conformance and installed-wheel
acceptance on 2026-09-29. The executable validators are authoritative. A public
tagged release and Riffology deployment acceptance have not been claimed; the
latter is a separate gate in `riffology-cloud#122`.

## Supported release range

| Dimension | v0.1 admission rule |
|---|---|
| Product | `sim-engine-compiler` Python package `0.1.0`; Rust compiler and runtime crates `0.1.0` |
| Platform | Linux x86_64, Python ≥3.12 with the CPython stable ABI; tested with 3.12.13 and 3.14.7; Rust 1.90.0 build toolchain; wheel target `manylinux_2_28` |
| Model | Aircraft support only, `aircraft-support-pack/v0.1`; synthetic B1 example is shipped in the wheel |
| Layers | `aircraft-business-ir/v1` → `simulation-core-ir/v2` → `aircraft-support-plan/v1alpha2`, `compiler-lineage/v2` |
| Execution | `legacy-minute-v1` or `event-time-v2`; `legacy-sequential-v1` RNG; `stable-topological-serial` work |
| Plan optimization | No `resource_dispatch_index` in a v0.1 bundle. Indexed Plan identity remains unsupported by PR #20. |
| Backends | Installed Rust native runtime for public `run`/`batch`; Python SimPy remains the independent semantic reference |

The aircraft phase operations in `ir/compatibility_operations.json` are
**restricted compatibility operations**, not general engine primitives. The
domain pack registers the supported profiles, versions, operations and backend
matrix. Its validated Business edit range is the existing aircraft v1 schema;
unknown operations, profiles, invalid units and references are rejected by the
existing IR/domain validators. No new operation or scheduling semantics are
introduced by this release boundary. A new case requiring new semantics needs
its own operation review and independent contract tests.

## Public entry points

The installed `sim-engine` command provides `inspect`, `validate`, `seal`,
`compile`, `run`, `batch`, `diff` and `example`. `seal` is an explicit step for
an edited Business payload: it checks lowering and emits a new fingerprint.
`validate` and `compile` reject a previously sealed envelope whose payload was
changed without resealing. This prevents a stale revision identity from being
silently reused. The `example` command writes a B1 Business revision and an
initial bundle using package resources, without a source checkout.

Equivalent Python SDK functions are exported from `sim_engine_compiler`:
`inspect_model`, `validate_business`, `seal_business`, `compile_bundle`,
`load_bundle`, `run_bundle`, `batch_bundle` and `diff_runs`. Invalid persisted
Business input returns a validation report; other rejected calls raise
`ProductError` with `code`, `stage`, `path` and `message`. CLI commands emit
JSON reports or results on stdout. Rejections emit `sim-engine-error/v1` JSON
on stderr and exit 2; native execution failure exits 3. A valid inspection
may report `mapping_coverage=partial` because current aircraft operations are
coarse. It requires `association_status=verified` to admit a bundle.

The existing `scripts/*.py`, `python -m sim_engine_compiler.identity` and
`sim-engine-runtime` executable remain low-level development and compatibility
tools. Product consumers use the installed `sim-engine` command or SDK. The
public CLI never interprets upstream Project JSON; the only canonical import
continues through `integrations/spare_mvp`.

## `.simpack` format and rejection rules

A bundle is a deterministic ZIP with exactly `manifest.json`, `business.json`,
`core.json`, `plan.json` and `lineage.json`. The manifest contains schema,
compiler/runtime/domain-pack versions, IR versions, time/RNG/work profile,
per-file SHA-256 values, layer fingerprints and a content-derived bundle ID.
Loading checks the exact v0.1 version matrix, ZIP member list/size, JSON
syntax and duplicate keys, all file checksums, Plan index absence and PR #20's
independent Business→Core→Plan/lineage association. Old or future versions
do not fall back to a best-effort interpretation. A bundle with a replaced
layer remains invalid even if its ZIP checksums are recomputed.

Digests prove internal consistency, not publisher authenticity. A `run` or
`batch` result carries the bundle ID, compiler/runtime/domain-pack identity,
IR/profile versions, Plan and Business fingerprints, request seed/sample IDs,
the native result/trace, diagnostics and result digest. The included PR #20
request identity still labels its execution evidence `caller_asserted`; the
product wrapper has checked the native result's Plan fingerprint and seed but
does not claim a cryptographic execution attestation.

`diff` compares two single-run records only when seed, observation level and
horizon match. It reports observed trace/terminal/metric differences. Summary
observation can have an empty trace, so an absent trace difference does not
imply unchanged behavior or causal equivalence.

## Offline acceptance command sequence

Run these with the **installed wheel**, in a directory outside this checkout:

```sh
sim-engine example /tmp/aircraft-v01
sim-engine inspect /tmp/aircraft-v01/baseline.simpack
sim-engine run /tmp/aircraft-v01/baseline.simpack --seed 0 --run-id before \
  --output /tmp/aircraft-v01/before.json >/dev/null
# Edit only the payload of business.json; for B1, change the first support
# activity's first job durationMinutes from its original value to 30.
sim-engine seal /tmp/aircraft-v01/business.json /tmp/aircraft-v01/edited-business.json
sim-engine validate /tmp/aircraft-v01/edited-business.json
sim-engine compile /tmp/aircraft-v01/edited-business.json /tmp/aircraft-v01/edited.simpack
sim-engine batch /tmp/aircraft-v01/edited.simpack --seeds 0,0,7 \
  --output /tmp/aircraft-v01/batch.json >/dev/null
sim-engine run /tmp/aircraft-v01/edited.simpack --seed 0 --run-id after \
  --output /tmp/aircraft-v01/after.json >/dev/null
sim-engine diff /tmp/aircraft-v01/before.json /tmp/aircraft-v01/after.json
```

The B1 model is a hand-calculable **synthetic** fixture, derived from
`tests/fixtures/synthetic/b1-daily-operations.json` and packaged as a saved
Business revision. It does not reproduce an unavailable upstream workload.
The supported business edit changes the Plan fingerprint and actual mission
and support outcomes without rebuilding Rust.

## Acceptance separation

1. Product conformance: executable package tests, existing aircraft/identity
   Python and Rust regressions, and adversarial bundle controls.
2. Distribution: build a wheel, install it in a fresh virtual environment,
   run the sequence above after moving the bundle to another directory, and
   record wheel hash, Python/Rust versions, command exit codes and results.
3. Integration: Riffology consumes only this public contract, persists fixed
   bundle/Plan and result identities, and verifies a real deployed edit →
   compile → run → reopen path. Record this separately in its issue.

Online CI status, SIMLOX cases, GPU/WASM, new performance claims and a second
domain are outside this v0.1 acceptance slice.

`scripts/build_linux_wheel.sh` uses the pinned manylinux_2_28 container image
because the development host's glibc-linked build did not pass Maturin's
manylinux_2_28 audit. The Riffology historical service path uses CPython
3.11.14 and cannot install this wheel. Its separately provisioned simulation
interpreter is CPython 3.14.2; Riffology must add the wheel and pinned SimPy
dependency to the image/lock chosen for compiler-backed runs. The local 3.14.7
container smoke establishes wheel ABI compatibility, not deployed Riffology
acceptance or that image's exact package closure.
