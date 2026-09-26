# Issue #6: J35 batch preparation on AMD128

## Frozen real-case input

The primary case is the committed `spare_mvp` J35 43-day availability Project
export, `exports/project-case-large.json`, from upstream commit
`0e709bdcc2d692d9cfed49b9037c76ef71aefe33`. Its SHA-256 is
`dd37321d012145b3b1554f23f58bca4d70843bfd49cc22233d4969be2f247569`.
The upstream `SimulationAdapter.compile_scenario` generated canonical
`simulation_inputs`; the established headless oracle override disabled
visualization frames after schema validation. The frozen input has eight J35
aircraft, 424 components, 104 mission occurrences, 13 support activities,
two resource nodes and a 61,920-minute horizon. Its SHA-256 is
`ff830e6c021b74491bb58fd902a46ed5bc852e7170f27300ff40c028e33e2793`.
The [source manifest](source/manifest.json) records the upstream schema and
Adapter provenance. No local database is included.

The O5 scan and indexed Plans have the same semantic content; the indexed
Plan adds only `resource_dispatch_index` v2 with 810 dependencies and 898
candidate rules. The scan/indexed file SHA-256 values are
`bcc161c53821002026e9d04bd4b88dd8b5b19b9aaf9dd4039fcd2d25ce561b2e`
and `e31fa22cb22451808a1eb3846b560ad51cb0b8b75418800ab3732c2857c9be17`.
The shared semantic Plan fingerprint is
`d510e74f5ae4a10ff2bae01457879e4fc43bc8576a394f96314220243cb0778c`.

## Semantic acceptance

The [Plan differential](validation/validation.json) compares seeds 0/1/7
across the Python reference, Rust legacy and O5 profiles, all three dispatch
arms, and Full/Summary. Complete Rust sample results match across arms;
Full contains the required trace, and Summary differs only by its empty trace.
The [upstream oracle comparison](validation/oracle-validation.json) also
matches business trace, random-request projection, defined core metrics,
terminal state and resource ledger for all three seeds. With zero spare
demand in seeds 1/7, upstream reports `spare_fill_rate=null` while the Plan
path reports `1.0`; both raw values are retained, and this undefined 0/0
metric is excluded from the oracle comparison. No simulation behavior or
runtime metric was changed for this benchmark.
The J35 indexed Plan also rejects a damaged checksum before creating any
sample output (`resource dispatch index checksum mismatch`); the existing
runtime tests cover missing dependencies and invalid references.

## Measurement boundary

AMD128 has 64 physical cores in one NUMA node. The baseline is the isolated
`main@e9b6391fffd918e0f6e742bd1ef0e1312921b769` checkout; the candidate
is the shared immutable prepared-Plan runtime at
`d4c18e8a5fdd3be46e9862bcd0df1eb1cf29eaaa`. Baseline/candidate CLI
SHA-256 values are
`8cb8388037c4a031dc51e0f430717206438c7cd73e67dd5f2a0650e2bd13826f`
and `9c6a8800ef0f0b5f4c801235d52e7bb0a101d1b528eea512f6b0f61d3f04a03b`.
Both use `rustc 1.98.1` and the same frozen input
and Plans. The uninstrumented cold CLI measurement includes process startup,
Plan read and validation, batch execution, serialization and output write;
its peak RSS comes from GNU time. Each configuration warms once and then runs
six interleaved baseline/candidate pairs. The OS page cache is not flushed.
Every run hashes the entire output and sample array before removing its large
temporary JSON file. The complete identity and raw paired records are kept
beside each summary.

Compiler measurements are separate from AMD128 runtime ratios. The
[macOS compiler record](compile-macos/records.json) uses the pinned LLVM/MLIR
23.1.1 plugin, one warmup and six byte-identical regenerations of the
indexed Plan. It includes canonical input read, three-layer lowering, MLIR
pass and Plan write, excluding compiler/plugin build.
The six measured process-wall times have a 239.157 ms median. This macOS
number is a reproducibility and cost-boundary check, not an AMD128 speedup.

## Results and decision

The [complete Summary matrix](cold-summary/summary.json) contains 324
measured rows. Every configuration warmed once, then ran six paired rounds.
All rows passed complete result-hash and matrix checks. The seed sequence is
`0,1,7,7` repeated; `sample_index` remains in request order. At a fixed
worker count, the complete CLI output is byte-identical across both binaries
and all three arms; sample arrays also match across worker counts.

For O5 + Summary indexed scanning, each cell gives the median paired
end-to-end gain and the number of positive pairs:

| Samples | 1 thread | 2 threads | 4 threads | 8 threads |
| ---: | ---: | ---: | ---: | ---: |
| 32 | +7.94% (6/6) | +6.62% (6/6) | +3.89% (6/6) | +0.11% (3/6) |
| 256 | +7.97% (6/6) | +6.96% (6/6) | +4.83% (6/6) | +1.01% (6/6) |

At 256 samples the baseline/candidate process-wall medians are
25.971/23.899, 14.572/13.558, 8.887/8.458 and 6.105/6.038 seconds for
1/2/4/8 threads. This corresponds to about 9.86/10.71, 17.57/18.88,
28.81/30.27 and 41.93/42.40 samples/s, with output writing included.
Peak RSS is about 2.86 GiB; the four median paired RSS ratios are
0.9983/0.9986/0.9986/0.9986, with no pair above 1.05.

The three-arm comparison shows where the benefit arises. No-index scanning
has paired gains of only +0.34% and -0.31% at 32/256 samples and one thread;
at eight threads they are +2.00% and +1.04%. Indexed scanning's excess over
no-index scanning at one thread falls from 0.371 to 0.109 seconds for 32
samples and from 2.834 to 0.706 seconds for 256 samples. Thus about 70.6%
and 75.1% of that *excess* disappears. This difference of three-arm medians
is an attribution estimate, not a direct timer for validation. Candidate
dispatch is still slower than indexed scanning after preparation: its
candidate median adds 0.159 seconds at 32 samples and 1.230 seconds at 256
samples, both at one thread. The [raw paired rows](cold-summary/records.jsonl)
retain every arm, thread count, wall time, RSS and result digest.

The predefined default-path gate requires both 32 and 256 samples to show
at least 5% stable O5 + Summary improvement in the tested 1/2/4/8-thread
range, with exact semantics and no repeatable >5% peak RSS rise. J35 meets
it at 1 and 2 threads, but misses it at 4 and 8 threads for both batch sizes.
Therefore the shared-preparation implementation remains experimental and
is not merged as the default path. The earlier F35 matrix remains historical
evidence and is not substituted for this J35 decision.

The separate [Full indexed-scan matrix](cold-full-cache/summary.json) contains
108 measured rows for the same counts and worker threads, again with six
paired rounds and exact output hashes. Its 256-sample output is 1.981 GB per
run. Median paired gains at 32 samples are +4.60/+3.87/+2.47/+0.19% for
1/2/4/8 threads; at 256 samples they are +5.10/+4.14/+2.72/+1.40%.
The 256-sample baseline/candidate walls are 42.785/40.589,
27.203/26.058, 19.330/18.808 and 16.162/15.955 seconds. Peak RSS is
about 9.6 GiB; no Full pair has a >5% rise. Full is reported separately
because its trace and output writing dilute the benefit visible in Summary.

## Preparation cost attribution

The [independent diagnostic builds](diagnostic/records.json) add counters to
the JSON Plan loader and sample initializer; their times are explanatory and
were excluded from the formal wall-clock comparison. At 256 samples, one
thread, indexed Plan, the counters report:

| Phase | Baseline | Shared preparation |
| --- | ---: | ---: |
| Plan file read | 0.500 ms | 0.554 ms |
| JSON parse | 8.467 ms | 8.611 ms |
| External Plan validation | 10.243 ms | 10.250 ms |
| Plan fingerprint | 2.687 ms | 2.747 ms |
| Batch validation / one prepared validation | 8.190 ms | 8.152 ms |
| Batch static build / one prepared static build | 0.354 ms | 0.388 ms |
| All per-sample validations | 3,196.355 ms | 0 |
| All per-sample static relationships | 113.722 ms | 0 |
| All sample initialization | 4,924.352 ms | 2,738.805 ms |

The 32-sample indexed counters similarly report 398.637 ms of per-sample
validation and 13.439 ms of per-sample static builds in the baseline, while
total initialization falls from 613.777 to 342.277 ms. The unindexed Plan's
256-sample validation counter is only 1.104 ms, consistent with its near-zero
formal gain. The JSON loader validation and batch-entry validation remain two
fixed checks; this change removes the checks inside each sample, not those
external load boundaries. The 256-sample indexed local validation plus static
counters total 3.310 seconds, but total initialization falls by only 2.186
seconds, and formal end-to-end wall falls by about 2.072 seconds. The
remaining dynamic initialization changed with execution/cache behavior;
these counters do not establish a separate cause for that difference.

The separate [uninstrumented Stage C capture](stagec-cache/summary.json)
uses the same indexed Plan, one thread and one post-warmup pass per variant;
it is a phase explanation, not the six-pair adoption evidence. For 256
samples, Summary reports baseline/candidate batch execution of
21.198/19.066 seconds, batch serialization of 1.023/0.990 seconds and JSON
write of 0.239/0.240 seconds. Full reports 32.076/30.294 seconds execution,
3.308/3.311 seconds serialization and 0.822/0.825 seconds write. Plan read,
parse/validation and fingerprint remain about 0.5, 17 and 2.8 ms. The
isolated first-sample initialization, including initial failure sampling,
is about 14 ms in either build; it does not measure the 256-sample sum.
Stage C runs its phases sequentially
with cache effects, so phase values should not be added to recreate the
separate end-to-end pass.

## Reused prepared handle

The [hot Rust benchmark](hot/records.json) holds one validated J35 indexed
Plan in a process and runs six paired public-batch and prepared-handle calls
per configuration, with identical sample hashes. One-time preparation takes
8.5–8.7 ms. At 256 samples the 1/2/4/8-thread paired median `run_ns`
gains are +0.004%, -0.136%, +0.894% and +1.219% (respectively 3/6, 2/6,
4/6 and 4/6 positive pairs); process peak RSS is about 2.98–3.00 GiB.
At 32 samples the gains range from +0.35% to +4.39%, but do not persist at
256 samples. A single-sample call improves by about 11.6%, consistent with
the fixed 8.6 ms preparation being a large part of an approximately 82 ms
public call. The hot `run_ns` boundary excludes output serialization; these
figures are separate from the cold CLI end-to-end ratios.

The subsequent PR review tightened the new public `PreparedBatchPlan::from_plan`
constructor so it derives the fingerprint from its in-memory Plan. The hot
records above belong to the pinned candidate commit and do not measure this
constructor's additional one-time fingerprint calculation. The measured
`run_ns` excludes preparation. The original JSON loading, cold CLI, Python
binding and legacy public-batch paths retain their fingerprint contracts.

## Python binding boundary

Each checkout has its own Linux PyO3 extension; their hashes and the common
indexed Plan hash are in the four `binding-*` identity files. The paired
driver starts a new Python process per row, warms one call, then measures
`run_batch(plan_bytes, seeds)` through native parsing, execution, transfer
and Python decoding. It excludes Python process startup and Plan-file read.
All six pairs in each configuration return the same complete sample-array
hash. The paired results are:

| Samples / threads | Baseline median | Candidate median | Median paired gain |
| --- | ---: | ---: | ---: |
| 32 / 1 | 3.250 s | 2.970 s | +8.57% (6/6) |
| 32 / 8 | 0.974 s | 0.953 s | +2.71% (6/6) |
| 256 / 1 | 25.763 s | 23.629 s | +8.45% (6/6) |
| 256 / 8 | 7.259 s | 7.070 s | +2.56% (6/6) |

These figures are specific to the Python call boundary and cannot be added
to the cold Rust CLI gains. [Raw binding records](binding-256-1/records.jsonl)
are retained for each configuration in sibling directories.
