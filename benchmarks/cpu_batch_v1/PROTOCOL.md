# Issue #6 CPU batch baseline protocol v1

Status: **prepared, not run**.  This document freezes the measurement design;
it contains no performance result.  The formal window is owned by the main
coordinator and may start only after the PR22 handoff and the semantic gate
below have completed.

## Question and boundary

This baseline asks how the supported CPU batch path scales on one host when the
total F35 workload is fixed and only the worker count changes.  The primary
claim is strong scaling at `N=64`, separately for `full` and `summary`
observation and separately for the pure-Rust executable and the public PyO3
`sim_engine_compiler.run_batch` boundary.

The measured runtime must remain the default, unindexed waiting-job scan.  Do
not pass `--dependency-dispatch`, do not materialize a resource dispatch index,
and do not change runtime, compiler, RNG, scheduling, serialization, or
allocation behavior.  This protocol does not benchmark compilation throughput,
the canonical Monte Carlo API, a candidate optimization, a persistent
`PreparedBatchPlan` handle, GPU execution, or another machine.  It must not be
combined with the historical J35 measurements or used for a SIMLOX comparison.

PR #19 is documentation-only and remains unmerged at protocol freeze.  Its
adoption report establishes that one `PreparedBatchPlan` is already shared by
the ordinary Rust batch call, not that the path is fast.  This work is based
directly on `595cb5eee9987324b19a8c3566f201f937e05f15` and has no dependency on
PR #19.

## Frozen subject

The run manifest must record and verify these identities before any timed cell:

| Item | Frozen identity |
| --- | --- |
| Repository commit | `595cb5eee9987324b19a8c3566f201f937e05f15` |
| Host | `g-1503-amd128` |
| Canonical input | `tests/fixtures/spare_mvp/f35-43day-5352a0d/simulation-inputs.json` |
| Canonical input file SHA-256 | `a506b7dc2bead97fd1268eab34d67432ba5307a82d934016f20d09166533b70d` |
| Canonical semantic input digest | `6b7730e1203dbbf0f04fed56bdebb1a58a7ff6c013c76ea2e63e86649de6c2f6` |
| Fixture project digest | `220f41d8a4e71e1a4c6a91143c100368c0cdd1440cbdcbace57a28ae56582fa5` |
| Upstream source commit | `5352a0d7757cbac012c75d516d1a7ac4ff15aa2a` |
| Plan profile | `event-time-v2` |
| Work policy | `stable-topological-serial` |
| RNG profile | `legacy-sequential-v1` |
| Duration | `61920` minutes (43 days) |
| Dispatch mode | default unindexed scan; candidate dispatch disabled |
| Rust toolchain | `1.90.0`, as pinned by `rust/runtime/rust-toolchain.toml` |

The checked-in fixture Plan is `legacy-minute-v1`; it is an input to the
pre-run semantic check, not the timed Plan.  Before the formal window, compile
the same frozen canonical input once to an `event-time-v2` Plan using the
supported compiler.  Persist that exact Plan without an index, its byte
SHA-256, semantic fingerprint, byte count, compiler command, compiler binary or
module hashes, and the canonical-to-Plan lineage.  No timed process may compile
or rewrite the Plan.  This compilation is pre-window preparation and is not a
measured performance stage.  A missing or mismatched identity is a fail-closed
gate.

Build release artifacts before the formal window with the explicitly pinned
`+1.90.0` toolchain from the existing `rust/runtime/rust-toolchain.toml`.
Persist the exact `stage-c-benchmark` and `sim-engine-runtime` executable
SHA-256 values, PyO3 extension SHA-256, Python wheel or editable-install
provenance, `rustc -Vv`, `cargo -V`, Python version, Cargo lockfile SHA-256, and
relevant source file hashes.  An already present binary must not be accepted
merely because its name matches.  Builds, tests, and dependency installation
are completed before the formal window and are outside all timing values.

## Machine and placement freeze

The preparation inspection found one AMD Ryzen Threadripper PRO 3995WX socket,
64 physical cores, 128 logical CPUs, SMT width 2, and one NUMA node containing
logical CPUs `0-127`.  The process affinity and effective root cpuset both
allowed `0-127`; the current session did not expose a readable CPU quota, so a
claim of “no quota” is not permitted.  Memory cgroup limit was `max` at
inspection.  The governor was `schedutil` and boost was enabled.

Every formal process is pinned with `taskset -c 0-7`.  Those are eight distinct
physical cores; their SMT siblings `64-71` are excluded.  Worker counts are
therefore exactly `1, 2, 4, 8`, bounded by physical cores and held within one
NUMA node.  Do not change governor, boost, NUMA policy, or system tuning during
the window.  Record immediately before and after the window: `lscpu -e`, NUMA
topology, process/effective cgroup cpuset and quota files when readable,
`/proc/meminfo`, load average, governor, boost, kernel, and competing processes.
If another build, test, benchmark, or known CPU-heavy job overlaps, abort the
window and retain the partial evidence rather than filtering it afterwards.

Before opening the window, retain a full `ps` process inventory and two live
`top` snapshots, and obtain explicit stop acknowledgements for collaborating
agent tests, builds, and benchmarks.  During the formal window, retain live
`top` sampling at 5-second intervals and scan for known test/build/benchmark
tools at 30-second intervals.  These controls support only a
controlled/best-effort statement that no known CPU-heavy overlap was observed;
they cannot prove the operating system had zero background load.  Do not stop
ordinary desktop, remote-access, network, or unrelated OS services to create a
cleaner result.

## Seeds, cells, and order

Persist `seeds-n64.json` containing exactly:

```json
[0,1,7,7,0,1,7,7,0,1,7,7,0,1,7,7,0,1,7,7,0,1,7,7,0,1,7,7,0,1,7,7,0,1,7,7,0,1,7,7,0,1,7,7,0,1,7,7,0,1,7,7,0,1,7,7,0,1,7,7,0,1,7,7]
```

This is `[0,1,7,7] * 16`; the duplicate `7` is deliberate.  Persist its byte
SHA-256 and pass the identical list, in the identical order, to every `N=64`
cell.  The small probes use the prefixes of length 1 and 8.  They characterize
startup/crossover behavior only and must not enter speedup or efficiency
claims.

The harness must persist a complete `measurement-list.json` before timing.  Its
immutable ordered cells are:

1. For repeat 0 use workers `[1,2,4,8]`; repeat 1 uses `[8,4,2,1]`; repeat 2
   uses `[2,4,8,1]`.
2. Within each repeat, measure `summary` then `full` for a worker before moving
   to the next worker.
3. For each observation/worker cell, run pure Rust then PyO3.  Each backend is
   reported independently; adjacency does not authorize a cross-backend ratio.
4. After all `N=64` cells, run the diagnostic `N=1, workers=1` and
   `N=8, workers=8` cells in that order, for `summary` then
   `full`, pure Rust then PyO3.  Each small cell has one warmup and one measured
   invocation and no repeated scaling statistic.

Thus the formal list contains 48 main measured cells (3 repeats × 4 workers ×
2 observations × 2 backends) and 8 small measured cells.  Each cell is one
fresh process, performs exactly one untimed warmup call followed by exactly one
primary timed batch call, and is wrapped once for whole-process RSS.  The Rust
tool's additionally timed single-sample and second end-to-end executions remain
secondary stage diagnostics and are not counted as extra matrix cells.  The
order may not be shortened, reshuffled, or resized after seeing a result.  The
one formal window has a hard 1,200-second deadline.  Freeze a 60-second per-cell
admission reserve, a 60-second subprocess timeout, and a 10-second postflight
reserve in `manifest.admission_policy` as `window_deadline_seconds: 1200`,
`cell_time_budget_seconds: 60`, `postflight_budget_seconds: 10`, plus a plain
language `meaning`.  The 60 seconds are a conservative admission cap, not a
claim or guarantee that an unknown cell will complete, and are not derived from
an extra `N=64` pilot.  No `N=64` preparation run is allowed.

The window includes every formal warmup, measured cell, small probe, result
serialization/write, and monitor action.  The harness records monotonic start
and deadline and starts a fresh cell only when remaining window time is at
least `60 + 10 = 70` seconds; every subprocess still has a hard 60-second
timeout.  The reserved final 10 seconds cover the bounded `machine_after`
snapshot and atomic final state write.  The postflight snapshot routine is
invoked once, limits each command to the remaining postflight deadline, and
does not extend the window.  If the final real deadline check has elapsed, the
state becomes `incomplete` with stop reason
`window_deadline_exceeded_during_postflight`.  Any cell timeout, nonzero exit,
or invalid evidence permanently closes this unique window, retains the valid
partial records, and marks all remaining preregistered cells `incomplete`.
There is no retry, resume, added budget, smaller-N substitution, Full omission,
or second unreported window.

The coordinator may send SIGINT or SIGTERM to the measurement driver when a
known competing CPU-heavy job is detected. Handlers are installed before the
formal clock starts. They close the window as incomplete, terminate only the
driver-owned current subprocess session/process group, and preserve current
failure and completed-cell evidence. No unrelated process is stopped. The
same run directory cannot resume. Interruptions during pre/postflight also
retain an incomplete state; they are not reclassified as successful timing.

## Semantic admission gate

The following gate is untimed and must pass on the exact release artifacts and
timed Plan.  Any failure stops performance measurement; it does not trigger an
optimization or a relaxed comparison.

1. The accepted Python reference executes only `legacy-minute-v1`; it does not
   execute or independently oracle `event-time-v2`.  For seeds `0`, `1`, and
   `7`, first compare that Python reference with pure Rust and PyO3 using the
   frozen checked-in legacy Plan in Full observation.  Use exactly the existing
   F35 baseline policy in
   `tests/differential/test_rust_runtime.py::test_f35_required_seeds_match_python_reference_full_result`:
   `first_divergence(..., float_rel_tol=2e-15, float_abs_tol=1e-12)`.  This is a
   pre-existing Python-reference boundary allowance, not a new benchmark
   tolerance.  Apply no other ignored field, normalization, or tolerance.
   Persist two separate facts for each comparison: whether the raw trees were
   strictly equal and whether `first_divergence` accepted them under those
   exact tolerances.  A tolerance-accepted result must not be described as
   bitwise or strict full-tree equality.
2. For the same seeds and each backend, compare the complete Full result tree
   from `legacy-minute-v1` with the complete Full result tree from the frozen
   timed `event-time-v2` Plan.  Normalize only the expected
   `plan_fingerprint` identity difference caused by the profile-specific Plan;
   every other field, collection order, event, metric, RNG request/tape,
   terminal state, seed, and engine-semantic value must remain exactly equal
   with no floating tolerance.  This chained differential admits O5 for
   timing; it must not be reported as the Python/SimPy reference executing O5.
3. For each backend, compare Full and Summary for the same seeds using strict
   equality with no floating tolerance: Summary `trace` must be exactly `[]`,
   and every contract field retained in Summary (`plan_fingerprint`, `seed`,
   `time`, `stop_reason`, `sample_requests`, `metrics`, and `terminal_state`)
   must equal Full exactly.  Trace omission is the only observation-level
   difference allowed by the existing contract.
4. Run the duplicate list `[7,0,7,1]` with workers 1 and 8 for both observations
   and both backends.  Require identical per-sample results, exact input-order
   `sample_index` values `[0,1,2,3]`, exact seed order, and equality between
   worker counts by strict full-tree equality with no tolerance or normalized
   field.  Isolated RunState admission comes from the independently emitted
   single-sample results, equal duplicate-seed results in distinct sample
   positions, stable input order, and unchanged decoded trees when the worker
   count changes.  Python object identity such as `is not` is not evidence of
   runtime-state isolation.
5. Reject a Plan whose byte digest, semantic fingerprint, profile, duration,
   source digest, phase order, or index presence differs from the frozen
   manifest.  Confirm candidate dispatch is false in every Rust report and is
   unavailable through the selected public PyO3 call.

For pure Rust semantic-gate runs, use the frozen `sim-engine-runtime` CLI to
write the actual Full/Summary result JSON.  The stage-c executable retains only
digests and indexes, so its reports are insufficient evidence for whole-tree
semantic admission.  PyO3 gate runs use the public `run_plan`/`run_batch`
results.  Persist commands, raw result trees, stdout/stderr, comparison reports,
and output digests.  The gate writes `report.json` and `report.sha256`; the
measurement harness must revalidate the frozen manifest digest, disabled
dispatch setting, all-pass checks, and the exact admitted raw-file set with
each file's SHA-256 and byte count before opening the window.  Do not use
expected observations as runtime inputs.

This semantic gate, manifest binding, and raw-file hash inventory establish
local artifact integrity and repeatable admission on this checkout.  They are
not a third-party attestation, an independent external replication, or proof
that the host was uncontended.  Compilation, release builds, and admission-gate
runs are unmeasured preparation even though their artifacts are mandatory.

## Supported entrypoints and timing meaning

### Pure Rust

Use the existing release `stage-c-benchmark` binary:

```text
taskset -c 0-7 /usr/bin/time -v stage-c-benchmark PLAN REPORT \
  --seeds SEED_CSV --worker-threads W --warmups 1 --repeats 1 \
  --observation-level full|summary
```

Do not pass `--dependency-dispatch`.  The primary warm execution value is the
reported `batch_execution_ns`.  It includes per-call Plan preparation from the
already parsed Plan, Rayon pool construction, all per-sample RunState creation,
and execution.  It does not include Plan file read, JSON parse/validation,
fingerprinting, result serialization, write, process startup, or the tool's
separate single-sample probe.  The tool performs an untimed batch warmup and,
inside its record, a single-sample measurement before the batch; this cache
history must be disclosed with every result.

Retain its reported `plan_read_ns`, `plan_parse_validate_ns`, `fingerprint_ns`,
`run_state_initialization_ns`, `single_sample_execution_ns`,
`single_sample_serialization_ns`, `batch_execution_ns`,
`batch_serialization_ns`, `batch_write_ns`, and `end_to_end_batch_ns` without
relabeling.  `run_state_initialization_ns` describes only the explicit single
sample.  It is not the batch's aggregate initialization time.  Batch Plan
preparation, pool creation, per-sample initialization, and execution are not
separately available.  `end_to_end_batch_ns` is a second in-process execution
from Plan read through write, not process cold start.  Compilation is absent.

The `prepared_batch_benchmark` is permitted only as a separately labeled
diagnostic outside the primary matrix.  It measures a persistent handle not
available from the public Python API and must not replace or be mixed into the
default-path scaling result.

### PyO3

Use only the public Python call:

```python
sim_engine_compiler.run_batch(
    plan_bytes,
    seeds,
    worker_threads=W,
    observation_level="full" or "summary",
)
```

The fresh-process offline wrapper loads the frozen Plan bytes before the
warmup, invokes the public call once untimed, then measures one call with
`time.perf_counter_ns()`.  The measured call includes Python argument handling,
Plan string/bytes conversion, native Plan parse/validation and preparation,
Rayon pool construction, RunState initialization and execution, Rust JSON
serialization/transfer, and Python `json.loads`.  Those components are bundled
and unavailable individually; do not estimate them by subtracting Rust values.
Plan file read, Python import/process startup, and wrapper output write are
outside `call_ns` and must be separately identified as such.  There is no public
persistent `PreparedBatchPlan` handle and no candidate-dispatch switch on this
entrypoint.

Before the measured call, the wrapper also parses the Plan for identity and
validates/hashes the warmup result. These checks are outside `call_ns` but are
part of the process cache history and whole-process wall/RSS, not zero-cost
work. After measurement it compares both result trees and produces proofs.

The minimal offline harness still required after protocol freeze must:

- create and verify the immutable Plan/seeds/measurement manifests;
- execute exactly the cell list using the frozen 60-second cell cap plus
  10-second postflight reserve (70-second start threshold), and close the whole
  window on the first timeout, nonzero exit, or evidence failure;
- use a fresh pinned process per cell, capture `/usr/bin/time -v`, stdout,
  stderr, exit status, and monotonic timestamps;
- parse rather than alter the two supported entrypoints' output, verify result
  digests/sample indexes, and write one raw JSON record per cell atomically;
- record cold whole-process wall time separately from warm in-process call time;
- never import runtime internals, reuse a private handle, enable dispatch, or
  implement a scheduling algorithm.

No runtime or compiler edit is authorized to obtain missing stage timings.

## Cold, warm, RSS, and unavailable measures

“Warm” means only that the same fresh cell process completed one identical
untimed batch call immediately before the timed call.  It does not imply a
dropped filesystem cache, fixed CPU frequency, pre-faulted output, or reused
persistent handle across cells.  “Cold process” is the external wall clock for
that fresh process, including interpreter or executable startup, imports,
warmup, the tool's own extra work, measured call, and evidence write.  It is
reported as operational overhead, never subtracted to invent process startup or
another component.  Filesystem caches are left in their natural host state;
cache dropping is forbidden.

Capture maximum resident set size with GNU `/usr/bin/time -v` around every
fresh process.  This is the high-water RSS for the whole process including
startup, libraries, warmup, the Rust tool's single-sample probe, measured work,
and output handling.  It is not incremental batch allocation and cannot be
subtracted across worker counts.  The binding worker deliberately retains the
PyO3 warmup result so it can prove complete-tree equality with the measured
result.  PyO3 whole-process RSS may therefore contain both result trees plus
proof construction, encoding, and evidence writes.  It is not batch-incremental
allocation and must not be divided by, subtracted from, or expressed as an
incremental-memory ratio against Rust RSS.  Allocation counts, per-thread peak
memory, and batch-only RSS are unavailable and must remain unreported.

| Stage | Pure Rust stage-c | Public PyO3 |
| --- | --- | --- |
| Canonical compilation | not measured; performed once before window | not measured |
| Plan file read | reported, in-process | outside `call_ns` |
| Parse/validate/fingerprint | reported separately | bundled in `call_ns` |
| Batch preparation / pool construction | bundled in `batch_execution_ns` | bundled in `call_ns` |
| Per-sample RunState initialization | only single-sample probe reported; batch split unavailable | bundled, split unavailable |
| Execute | bundled with batch setup | bundled in `call_ns` |
| Serialize | reported separately | bundled with transfer/decode |
| Transfer / Python decode | not applicable | bundled, split unavailable |
| Write | reported separately | wrapper-only, outside `call_ns` |
| In-process end to end | reported as a second execution | `call_ns` only, with boundaries above |
| Process cold wall / RSS | external whole-process values | external whole-process values |

## Analysis and reporting

For the primary `N=64` matrix, calculate within each backend and observation:

- throughput: `64 / (warm_batch_seconds)`;
- paired-repeat speedup at worker `w`: `T(repeat,1) / T(repeat,w)`;
- paired-repeat efficiency: `speedup / w`.

For Rust, `warm_batch_seconds = batch_execution_ns / 1e9`; for PyO3 it is
`call_ns / 1e9`.  Summarize the three raw repeats using median, minimum,
maximum, and median absolute deviation.  Retain and publish every raw value,
cell order, output digest, exit status, warmup status, external wall time, and
RSS.  Do not average Full with Summary, Rust with PyO3, or small probes with
`N=64`.  Cross-backend absolute times may be displayed side by side but do not
form a speedup claim because their timing boundaries differ.

Report timeout, semantic-gate failure, nonzero exit, identity drift, result
mismatch, background-load overlap, or missing stage as such.  A partial matrix
supports only the cells actually completed; it must not be presented as the
Issue #6 baseline.  The protocol is successful even if scaling is flat or
negative—the result is measurement, not an adoption gate.
