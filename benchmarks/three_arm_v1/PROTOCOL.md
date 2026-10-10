# Issue 6: same-kernel three-arm pilot v1

Task: `engine-issue6-three-arm-9737822-v1`. This protocol defines a new bounded
research slice based on PR25 `9737822`; PR25's 921.5-second F35 window is closed
and will not be repeated. Issue 9 thresholds and adoption status are unchanged.

## Semantic admission (independent from performance)

Freeze canonical input, upstream manifest, Business IR, Core IR, both Plan
files, runtime/stage binary hashes, Rust 1.90.0, compiler/plugin identities,
source commit/tree and test logs. The actual J35 source is the committed
43-day Project export from spare_mvp `0e709bdcc2d692d9cfed49b9037c76ef71aefe33`,
canonical file SHA256 `ff830e6c021b74491bb58fd902a46ed5bc852e7170f27300ff40c028e33e2793`.
Reverify this provenance, do not infer it from a label. Synthetic loads are
separate, bounded models and never presented as J35.

For each performance workload, compare current Python reference on
legacy-minute-v1 against Rust legacy full; then compare Rust legacy full to
current event-time-v2 full, normalizing only profile-specific plan_fingerprint.
Python reference does not execute O5. Compare all three Rust arms full-tree
exactly, including every trace event, sample request, metric, terminal state
and resource/inventory/reservation ledger. Summary must differ only by trace=[];
no undefined metric is excluded from internal Python/Rust comparisons.

Integers, timestamps, identities, strings, list order, RNG sequence/rate and
all unlisted values use exact equality. The sole allowed floating discrepancy
at Python/Rust boundary is `sample_requests[*].value_minutes` (exponential
libm transform): relative 2e-15, absolute 1e-12. This narrow allowance is not
applied to Rust/Rust, profile, thread, observation or instrumentation comparisons.
Report raw equality separately from tolerance acceptance. Reject NaN/infinity.
Any newly observed field mismatch blocks admission rather than enlarging tolerance.

Cover seeds 0,1,7 and duplicate [7,0,7,1], threads 1 and 3, Full/Summary;
retain the current F35/B1-B3 regressions plus shared supplier pools, separate
personnel/equipment blockers, transport arrival, cancellation/refund, and
cutoff boundaries. Unknown operations, unsupported profile/backend, missing
index and incomplete dependencies must reject. Reuse variants alter only
model/Business IR task frequency, capacity and process steps, reload the
persisted IR and rebuild derived indices with the same scheduler binary.

## Measurement protocol

One formal window, at most 1200 seconds including warmups, output and monitoring.
No resume/retry or second formal window. Freeze the full ordered matrix before
starting; timeout or interference closes the window, preserving partial data.
All builds, tests, profiles and agent CPU work stop before timing, with explicit
acknowledgements. Record processes, load, affinity/topology, and before/after
machine snapshots; monitor foreign build/test/benchmark overlap during timing.
Reject normalized one-minute load above 0.05 (6.4 on the observed 128 CPUs),
and record host-visible process/CPU snapshots. This supports observed absence
of known interference, not exclusive host ownership.

Bounded pilot: J35 plus low-contention, sparse-affected, dense-affected synthetic
loads at 4,16,64 aircraft with a common synthetic 222-minute horizon. J35
retains its original 61,920-minute horizon. Sparse cases
partition resources and stagger release times. Same event-time-v2, legacy-sequential-v1,
stable-topological-serial, summary. J35 also has a separate full cell group.
Every group uses seeds [0,1,7], workers=1, three repeats, rotating arm order
(scan/cache/candidates; cache/candidates/scan; candidates/scan/cache).
Thus 11 groups, 99 cells. Taskset 0-7; one fresh stage-c process per cell,
one warmup, one measured repeat. Per-cell timeout 30 seconds, 10-second
postflight reserve. Admit a new cell only with >=40 seconds remaining.
No 32/256-sample or thread-scaling claim: those matrices are unmeasured here.

Reuse the existing stage-c-benchmark and its shared PreparedBatchPlan path for
all arms. Full scan uses Plan without index; cache uses otherwise identical
indexed Plan; candidates adds only --dependency-dispatch. O5, observation,
threads, seed order, output and preparation policy remain fixed within a ratio.
No Python-binding/hot-handle/MLIR-versus-direct-generator performance claim.

Preserve stage-c's actual boundaries: plan_read_ns, plan_parse_validate_ns,
fingerprint_ns, single-sample initialization/execution/serialization,
batch_execution_ns, batch_serialization_ns, batch_write_ns, and its second
in-process end_to_end_batch_ns execution. Batch execution bundles shared
preparation, pool creation, per-sample initialization and execution: these are
not separately recoverable. Whole-process wall and GNU time peak RSS include
warmup, single probe, both batch executions and writes. RSS is not incremental
allocation and is not subtracted. Compiler process wall/RSS are separate
preparation diagnostics, not mixed into execution ratios or a formal compiler
speedup claim. No amortization or break-even claim is made.

Work counters come from separate profiled runs, checked equal to unprofiled
results. Instrumentation changes cost: never use profile times as primary
performance times. Disabled profiling still leaves conditional guards in the
compiled runtime; this experiment does not claim zero instrumentation overhead
relative to older binaries. All three arms use the same new binary. Report waiting set exposure/peak, visits including full-mode
replay, guards, cache hits, index traversal and maintenance, merge/sort work,
and events. A lowered guard count alone is not a complexity improvement.

## Prospective performance threshold and adoption decision

For each case/observation, classify cache/scan, candidates/scan and
candidates/cache using the exact paired-ratio rules below. Report every
preregistered cell and incomplete/unmeasured range. Three repeats and three
unique seeds form a pilot, not confidence intervals or broad adoption evidence.
Negative results may complete the research slice. Default optimization
adoption, merge and issue closure remain unauthorized.

## Admission refinements before any measurement

The only window may open after independent review and a passed semantic gate
artifact containing every declared case/check, a hash inventory of retained
raw evidence, verified J35 provenance and completed regression/reuse/rejection
checks. The actual freeze must contain exactly the 11 groups above. Gate,
Plans, both binaries, source revision, protocol and evidence hashes must match
at preparation and window opening. Missing/incomplete evidence, unsupported
capability or failed comparison forbids timing.

Build with `cargo +1.90.0`; run every stage-c cell with
`RUSTUP_TOOLCHAIN=1.90.0`. Record `rustc +1.90.0 -Vv` and `cargo +1.90.0 -V`.
Stage-c's rustc field is a runtime subprocess query, not embedded build
provenance: verify it reports rustc 1.90.0 and retain build commands separately.


Pre-register diagnostic counters for all ten unique performance inputs,
seed 0, all three arms, both Full and Summary, current O5 profile: 60 profiled
runs before formal timing, each checked against its unprofiled result. These
are single-sample workload explanations, never claimed as batch totals.

Threshold calculations use paired arm/control ratios, separately for
`batch_execution_ns`, `end_to_end_batch_ns`, and whole-process max RSS.
A benefit requires median execution ratio <=0.95, median end-to-end ratio
<=0.95, each end-to-end ratio <1, and median RSS ratio <=1.05.
A median execution or end-to-end ratio >=1.05, or median RSS ratio >1.05,
is a regression (report which measure); otherwise label no demonstrated
benefit/inconclusive. Equality at a boundary follows these inequalities.
Apply this identical rule for cache/scan, candidates/scan, and
candidates/cache. This is a bounded pilot classification, never a default
adoption authorization. Report absolute compiler diagnostic costs only;
no amortization or break-even claim is made in this slice.
