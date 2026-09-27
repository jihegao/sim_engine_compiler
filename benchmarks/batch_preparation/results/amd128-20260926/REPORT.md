# Issue #6: batch Plan preparation on AMD128

## Scope and frozen inputs

The baseline is `e9b6391fffd918e0f6e742bd1ef0e1312921b769` in a fresh,
isolated AMD128 checkout. The candidate runtime moves seed-independent Plan
validation and static relationships into an immutable `PreparedBatchPlan`.
No dispatch algorithm or Plan schema changes are part of this experiment.

F35 uses the pinned canonical input and `event-time-v2` Plan. Capacity-16,
remote-16 and shared-remote-pools are synthetic competition fixtures. The
scan arm has no resource index. Cache scanning and candidate dispatch share
the same v2 indexed Plan. The three arms use the same semantic Plan
fingerprint. Every result comparison includes the complete sample result;
Full results include trace, random requests, metrics, terminal state, and
resource ledger.

The formal F35 Summary run used baseline source
`e9b6391fffd918e0f6e742bd1ef0e1312921b769` and candidate source
`8136c66070e0cbe7cfebf79c6ea632958e7b7914`. Full and the synthetic
matrix use candidate source `d4c18e8a5fdd3be46e9862bcd0df1eb1cf29eaaa`;
intervening commits modify benchmark tooling. A subsequent commit adds tests
and a stricter report gate. The release runtime binary is unchanged.
Baseline/candidate CLI SHA-256 values are
`8cb8388037c4a031dc51e0f430717206438c7cd73e67dd5f2a0650e2bd13826f`
and `9c6a8800ef0f0b5f4c801235d52e7bb0a101d1b528eea512f6b0f61d3f04a03b`.
F35 input SHA-256 is
`a506b7dc2bead97fd1268eab34d67432ba5307a82d934016f20d09166533b70d`;
scan/indexed Plan SHA-256 values are
`beab59ac007f566d5e864346ddde6b5194420fae47e9eec9d0f710c76244163c`
and `2e9259761bf18768947e68c6456cfe5724b525e4858462839b6d9ed14344ccb7`.
The AMD128 runtime toolchain is `rustc 1.98.1` on Linux x86-64; the host has
64 physical cores in one NUMA node and 125 GiB RAM.

## Reproduction boundary

The formal AMD128 rows are new-process, uninstrumented CLI process wall.
Each configuration warmed once, then ran six alternating baseline/candidate
pairs. The process includes Plan-file read and validation, execution,
serialization, and JSON write. The OS page cache was not flushed. The CLI
process RSS comes from GNU time. The Plan compile measurement was made
separately on macOS with the pinned LLVM/MLIR plugin and is not combined with
AMD128 runtime ratios. Diagnostic patches ran only in separate builds.

## Semantic verification

The formal Summary and Full matrices each have 324 measured CLI rows: three dispatch arms,
three sample counts, the applicable 1/2/4/8 worker counts, six paired repeats,
and two source revisions. For every case/count, the serialized `samples` array
has the same SHA-256 across source revisions, dispatch arms and worker counts.
For a fixed worker count, the complete CLI output file is byte identical.
The seed sequence repeats `0,1,7,7`; `sample_index` stays in request order.
These exact result checks include each sample's random requests, metrics,
terminal state and resource ledger. Full additionally includes the required
trace; its six-pair matrix is reported separately below.

The measured AMD128 candidate passes 19 Rust library tests and all binary
tests; the final local branch adds and passes a twentieth multi-Plan group
ordering/parity test. The suite also covers duplicate-seed ordering, reused
prepared handles, static spare deduplication, phase ordering and invalid
Plan/index rejection. The Linux
Python binding passes all nine tests in each isolated checkout. The
three-arm differential suite checks the F35 seeds `0/1/7`, both observation
levels and semantic profiles, dense local contention, shared remote pools,
and invalid/missing v2 dependencies. That suite is run with the pinned
LLVM/MLIR plugin; a missing plugin is treated as a skipped test rather than
as semantic acceptance. The public prepared constructor rejects a damaged
index checksum or invalid aircraft/component reference before any sample;
candidate dispatch also rejects an index missing a required remote-capacity
dependency, even when its checksum is recomputed.

## Cost attribution

The separate diagnostic JSON loader measured the indexed F35 Plan at one
thread. Three 32-sample runs gave these medians (ms):

| Phase | Baseline | Candidate |
| --- | ---: | ---: |
| Plan file read | 0.500 | 0.593 |
| JSON parse into Plan | 8.656 | 8.476 |
| External load validation | 10.320 | 10.407 |
| Plan fingerprint | 2.817 | 2.936 |
| Batch validation | 8.444 | 8.555 |
| Batch static preparation | 0.277 | 0.310 |
| Sample validation, all 32 | 397.914 | 0 |
| Sample static relationships, all 32 | 13.620 | 0 |
| Total sample initialization, all 32 | 658.057 | 388.434 |

The 256-sample indexed diagnostic run counted 256 baseline sample validations
at 3,177.3 ms and sample static builds at 114.4 ms. Candidate preparation
validated once at 8.3 ms; total sample initialization fell from 5,260.1 ms
to 3,076.7 ms. These are instrumented phase sums, not end-to-end gains. The
JSON loader's validation and the batch entry's validation remain two fixed
checks (about 10.3 ms and 8.5 ms in the 32-sample diagnostic); neither is
counted as eliminated per-sample work. The binary cache loader also retains
its envelope/fingerprint/Plan validation before the batch boundary. The
candidate's dynamic remainder is larger than the baseline's remainder after
subtracting validation/static counters. Lost cache warming from repeated
validation is one possible cause. The three 32-sample repetitions reproduce
this pattern, but do not isolate a hardware-cache cause.

The uninstrumented Stage C 32-sample indexed-scan Summary medians (ms) are:
Plan read 0.522/0.500, parse plus validation 17.968/17.185, fingerprint
2.911/2.835, isolated one-sample initialization 15.283/15.351, isolated
execution 66.217/66.881, one-sample serialization 3.357/3.427,
batch execution 2,728.111/2,706.733, batch serialization 144.108/141.317,
and write 35.014/34.647 (baseline/candidate). The separate end-to-end Stage C
pass was 3,198.420/2,956.765 ms. These phases run in sequence with cache
effects and should not be summed to reproduce the separate end-to-end pass.
For Full, batch serialization grows to 439.323/435.217 ms and write to
107.405/107.342 ms, while the Stage C end-to-end pass is
4,762.566/4,515.902 ms. Compilation on macOS is separately recorded in
`../compile-macos-20260926/`. Six-run canonical-to-indexed-Plan process-wall
medians are 269.677 ms for F35, 112.862 ms for capacity-16, 117.291 ms for
remote-16, and 125.899 ms for shared remote pools. These measurements used
the pinned LLVM/MLIR 23.1.1 plugin and regenerated byte-identical Plans;
they are not AMD128 runtime components. The AMD128 host did not have that
plugin, so no AMD128 compile time is claimed.

The hot benchmark holds one validated F35 indexed Plan and compares six
interleaved public-batch calls with six calls through that handle. It excludes
process startup, file load and output serialization from `run_ns`. The
256-sample 1/2/4/8-thread median run times are 21.646/10.953/5.014/2.615 s
for the public call and 21.626/10.926/4.964/2.587 s for the prepared call.
Median paired gains are only +0.18%, +0.07%, +0.35%, and +0.66%; whole-process
peak RSS is 3.31–3.35 GiB. One-time preparation is about 8.4 ms. This extra
hot-handle gain is separate from removing 256 per-sample validations.

Both isolated checkouts installed the Linux PyO3 extension under Python
3.12.13; each passed all nine `test_python_binding` tests. The paired binding
driver warms each new worker process once, then times the Python
`run_batch(plan_bytes, seeds)` call, including native parse/run/serialization
and Python result decoding but excluding process startup and Plan-file read.
Six-pair median gains for 32 samples are +0.48% (5/6 positive) at one thread
and +2.05% (6/6) at eight threads. For 256 samples they are -0.83% (0/6)
and -2.63% (1/6), respectively. The 256-sample call medians are
26.730/26.949 s at one thread and 7.786/7.984 s at eight threads
(baseline/candidate). This warm binding result has no stable batch gain and
must not be combined with the cold CLI gain.

## End-to-end and memory results

F35 O5 + Summary, 32 samples, uninstrumented new-process CLI process wall:

| Arm | 1 thread | 2 threads | 4 threads | 8 threads |
| --- | ---: | ---: | ---: | ---: |
| No-index scan | -0.25% (2/6) | -0.62% (1/6) | +0.51% (3/6) | +3.12% (5/6) |
| v2 indexed scan | +7.78% (6/6) | +5.80% (6/6) | +4.00% (6/6) | +1.12% (3/6) |
| v2 candidate dispatch | +7.07% (6/6) | +6.04% (6/6) | +2.07% (6/6) | -2.30% (0/6) |

F35 O5 + Summary, 256 samples, same metric:

| Arm | 1 thread | 2 threads | 4 threads | 8 threads |
| --- | ---: | ---: | ---: | ---: |
| No-index scan | -0.36% (0/6) | -0.54% (0/6) | +0.36% (4/6) | -0.17% (3/6) |
| v2 indexed scan | +7.73% (6/6) | +6.73% (6/6) | +4.75% (6/6) | +0.90% (3/6) |
| v2 candidate dispatch | +7.03% (6/6) | +6.15% (6/6) | +4.81% (6/6) | +2.43% (5/6) |

Each cell shows the median of six paired percentage gains and the number of
positive pairs. For indexed scanning at 256 samples, median peak RSS ratios
for 1/2/4/8 threads are 0.9994, 0.9997, 1.0000, and 0.9995;
absolute peaks are about 3.18 GiB. The single-sample
gains are -0.80% for scan, +6.34% for indexed scan, and +7.02% for candidate
dispatch, each from six pairs. The complete Summary matrix passed its
324-row completeness and exact-result checks. No indexed-scan 256-sample
Summary pair has RSS more than 5% above its baseline pair.

At 256 samples, O5 + Summary indexed scanning delivers the following
new-process throughput (`samples / median process wall`):

| Threads | Baseline samples/s | Candidate samples/s |
| ---: | ---: | ---: |
| 1 | 9.50 | 10.28 |
| 2 | 16.76 | 17.98 |
| 4 | 27.23 | 28.52 |
| 8 | 39.09 | 39.38 |

The candidate's eight-thread throughput is 3.83 times its one-thread
throughput. This is fixed-total-sample scaling, with serialization and
write included; it is not a per-sample trajectory speedup.

F35 Full, 32 samples, uninstrumented new-process CLI process wall:

| Arm | 1 thread | 2 threads | 4 threads | 8 threads |
| --- | ---: | ---: | ---: | ---: |
| No-index scan | -0.54% (0/6) | -0.34% (1/6) | +0.24% (3/6) | +0.99% (4/6) |
| v2 indexed scan | +4.71% (6/6) | +2.61% (6/6) | +1.94% (4/6) | +0.94% (4/6) |
| v2 candidate dispatch | +4.70% (6/6) | +3.60% (6/6) | +2.65% (6/6) | +0.72% (4/6) |

F35 Full, 256 samples, same metric:

| Arm | 1 thread | 2 threads | 4 threads | 8 threads |
| --- | ---: | ---: | ---: | ---: |
| No-index scan | -0.76% (1/6) | -0.43% (1/6) | +0.26% (3/6) | -0.64% (2/6) |
| v2 indexed scan | +4.58% (6/6) | +3.41% (6/6) | +1.73% (6/6) | -0.75% (1/6) |
| v2 candidate dispatch | +4.85% (6/6) | +3.77% (6/6) | +2.85% (6/6) | +0.78% (6/6) |

The single-sample Full paired gains are -2.59%, +5.45%, and +4.48% for
scan/indexed scan/candidate dispatch. At 256 samples, indexed-scan Full
throughput is 5.88/9.30/13.05/15.63 samples/s before and
6.16/9.60/13.27/15.55 samples/s after at 1/2/4/8 threads. The Full output
is 1.867 GiB for 256 samples; process peak RSS is about 9.77 GiB and the
indexed-scan paired RSS ratios are 1.0000, 1.0000, 0.9998 and 0.9999, with
zero pairs above 1.05. All 324 Full rows passed completeness and complete
result hashing. Full's larger serialization/write share reduces the visible
gain, including an eight-thread indexed-scan regression.

### Resource competition cases

The three synthetic cases contribute another 1,944 measured rows (six
baseline/candidate pairs in every case, arm, observation level, sample count
and applicable thread count). The matrix passed exact-result hashes across
all three arms and all worker counts. The table shows indexed-scan Summary
median paired gains; each cell's six pairs are retained in `paired-synthetic`.

| Case and samples | 1 thread | 2 threads | 4 threads | 8 threads |
| --- | ---: | ---: | ---: | ---: |
| Capacity-16, 32 | +11.1% | +9.7% | +6.1% | +3.2% |
| Capacity-16, 256 | +14.3% | +12.1% | +5.6% | +5.2% |
| Remote-16, 32 | +12.8% | +8.8% | +9.4% | +3.4% |
| Remote-16, 256 | +15.0% | +14.0% | +11.1% | +8.4% |
| Shared remote pools, 32 | +29.2% | +17.2% | +23.3% | +12.5% |
| Shared remote pools, 256 | +52.2% | +43.4% | +36.2% | +25.9% |

Indexed-scan Full gains at 256 samples are +3.9/+2.5/+2.4/+1.3% for
capacity-16, +4.0/+2.7/+0.1/-3.4% for remote-16, and
+25.9/+21.8/+18.2/+7.0% for shared remote pools (1/2/4/8 threads).
For shared remote pools at 256 samples and one thread, indexed-scan Summary
process wall falls from 49.60 to 23.58 ms, whereas no-index scan stays near
23.3 ms. The very large percentage is mainly removal of repeated indexed
Plan validation from a tiny model; it does not imply a faster dispatch
algorithm. The complete scan/candidate matrices, paired variability and RSS
are in `paired-synthetic/summary.json`. No indexed-scan cell has a paired
RSS increase above 5%; the no-index shared-pool Summary cell at 256 samples,
four threads, has three such pairs and is retained as a measurement caveat.

## Three-arm comparison and adoption decision

The indexed-scan excess relative to no-index scanning at one thread falls
from 0.397 s to 0.125 s for 32 samples (68.6% of that excess removed) and
from 2.948 s to 0.801 s for 256 samples (72.8% removed). This difference of
three-arm medians is an attribution estimate, not a separate causal timing of
validation. Candidate dispatch remains slower than indexed scanning after
shared preparation: at 256 samples and one thread their median process walls
are 26.270 s and 24.894 s, respectively.

The default-path gate is not met across 1/2/4/8 threads: indexed scanning
misses 5% at 4/8 threads for both 32 and 256 samples, and its eight-thread
cells have only 3/6 positive pairs. No-index scanning has no stable gain.
The candidate implementation remains experimental; no merge into main is
justified by this matrix. Full strengthens that decision: the indexed-scan
256-sample eight-thread cell regresses, and even the one-thread Full gain is
below 5%. The warm Python binding also regresses at 256 samples. The
instrumented reduction in validation time is real, but it is not a general
end-to-end batch speedup across these configurations.

## Limits and next experiment

The shared-remote-pools, capacity-16 and remote-16 cases are synthetic; they
do not establish SIMLOX semantic equivalence. A SIMLOX efficiency comparison
requires a paired minimal-model semantics/output table first. A later issue
#6 experiment should scale Plan size and contention to compare scan, indexed
scan and candidate dispatch on this common preparation baseline.

## Inspectable evidence

Each formal directory below contains `identity.json` with source, input,
Plan, binary and toolchain identity, `records.jsonl` with every paired raw
wall/RSS/result-hash row, and `summary.json` with medians, paired gains, MAD,
throughput inputs and adoption checks. The multi-GiB Full output files were
hashed and deleted after each run; their SHA-256 values remain in every row.

- [F35 Summary](paired-f35-summary/summary.json) and
  [F35 Full](paired-f35-full/summary.json): complete 324-row matrices each.
- [Synthetic contention](paired-synthetic/summary.json): complete 1,944-row
  matrix for capacity-16, remote-16 and shared remote pools.
- [Stage C paired phases](paired-stagec-f35-32/summary.json): separate
  32-sample, one-thread Summary/Full segmented measurements.
- [Diagnostic counters](diagnostic-f35/records.json), with
  [repeat 2](diagnostic-f35-repeat2/records.json) and
  [repeat 3](diagnostic-f35-repeat3/records.json): separate patched builds.
- [Prepared-handle hot runs](hot-f35-cache-summary/records.json) and
  [Python binding paired calls](binding-f35-cache-summary-256-1/records.jsonl)
  (other binding counts/threads are sibling directories).
- [macOS compile records](../compile-macos-20260926/records.json),
  [Rust test log](validation-rust-macos.txt) and
  [MLIR differential log](validation-mlir-macos.txt).

`baseline-e9b6391/` contains an earlier unpaired, baseline-only Stage C
capture of 306 rows. It was intentionally stopped before completing its
planned matrix and is diagnostic context only; all adoption claims above use
the complete uninstrumented paired CLI matrices. Reproduction commands and
measurement definitions are in [the experiment README](../../README.md).
