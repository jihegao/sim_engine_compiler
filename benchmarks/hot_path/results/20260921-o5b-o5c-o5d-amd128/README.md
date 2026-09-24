# O5b/O5c/O5d AMD128 experiments

Date: 2026-09-21

Status: all three experiments are complete. O5b is rejected, O5c is not collected because its stable improvement stays below the predeclared engineering line, and O5d passes the semantic and performance gates as a candidate for a separate integration change. This experiment did not merge O5d into the accepted O5a runtime.

## Decisions

| Experiment | Mechanism | AMD128 result | Decision |
|---|---|---:|---|
| O5b | Persistent wake heap with owner generations and lazy stale-token removal | 56.03%–72.65% slower by the cross-session median improvement statistic | Reject and retain only the source diff/evidence |
| O5c | Start the canonical minute table at the earliest conservative phase rank | 0.71%–1.58% faster, positive in every session/cell | Do not collect; below the approximately 5% engineering line |
| O5d | Analytically advance continuous job/failure countdown state under exactness guards | 30.61%–41.16% faster, positive in every session/cell | Accept as an experimental candidate for separate integration |

O5b is the planned persistent-calendar experiment, but this implementation still scans runtime state and reconciles a desired-wake `BTreeMap` at each wake. It therefore tests heap reuse plus generation invalidation, not the stronger transition-owned `schedule/cancel` design. O5c and O5d were derived as bounded follow-up experiments: selective phase entry and guarded continuous-state bulk advance respectively.

## Semantic gate

The paired benchmark normalizes only `semantic_profile` and then requires exact equality of seed, result time, stop reason, RNG request tape, full trace, metrics, terminal state and all other business result fields. Summary mode additionally requires an empty trace. Each of the six AMD128 JSON files per experiment contains 36 measured legacy/event pairs.

- O5b: 108/108 pairs reported `business_equivalent=true`; O5a/O5b business-result hashes match for every session, seed and observation level.
- O5c: 108/108 pairs reported `business_equivalent=true`; O5a/O5c business-result hashes match for every session, seed and observation level.
- O5d: 108/108 pairs reported `business_equivalent=true`; O5a/O5d business-result hashes match for every session, seed and observation level.
- O5d local validation: Rust unit/all-target tests 26/26, `clippy --all-targets --all-features -D warnings`, event-time differential 9/9, and the repository Python suite 41/41 passed. The first full-suite attempt used a system interpreter without SimPy and failed during import; the authoritative rerun used the repository virtual environment and passed.

No tolerance, golden update or omitted business field was used for the same-platform candidate comparisons.

## AMD128 protocol

The host is AMD Ryzen Threadripper PRO 3995WX, Ubuntu 22.04.5, Rust 1.98.1. Every process was pinned to logical CPU 50 and run serially. The retained host snapshot recorded the `schedutil` governor and background desktop/FastLink processes on other CPUs, so this was not an isolated fixed-power environment. That snapshot was captured at 00:50 CST; O5d ran after a later reconnection and did not capture contemporaneous load/frequency, so those fields describe the host setup rather than the exact O5d run-time load.

For each experiment:

- fixed F35 43-day Plans, seeds `0/1/7`, observation levels `full/summary`;
- one warmup and six measured repeats per cell;
- three sessions, with baseline/candidate order alternated across sessions;
- release binaries built offline from the locked dependency set;
- `execution_ns` includes `Runtime::run(...)` and result construction, but not Plan loading/runtime construction;
- the table reports the median of the three per-session medians for baseline and candidate, and separately the median of the three per-session improvement percentages. The latter is intentionally not recomputed from the two displayed aggregate medians.

The O5a binary SHA-256 is `52a5cd25597e567272bf181b234c6b6b458eeefa876c909d0dfd173ead102197`.

## O5b: persistent calendar reconciliation

| Observation | Seed | O5a | O5b | Median session improvement | Session range |
|---|---:|---:|---:|---:|---:|
| full | 0 | 75.665 ms | 120.922 ms | -59.82% | -60.58% to -31.20% |
| full | 1 | 77.580 ms | 124.236 ms | -60.28% | -60.73% to -32.32% |
| full | 7 | 87.326 ms | 136.152 ms | -56.03% | -56.54% to -30.20% |
| summary | 0 | 61.371 ms | 105.862 ms | -72.65% | -72.82% to -72.02% |
| summary | 1 | 63.027 ms | 108.680 ms | -72.23% | -73.34% to -72.03% |
| summary | 7 | 70.473 ms | 118.165 ms | -67.22% | -68.33% to -67.10% |

The implementation's development profile reported calendar rebuilds falling from 1,609 to 4, but that raw profile was not retained in this evidence directory. The source diff shows that each wake still reconciles ownership by scanning state and maintaining a `BTreeMap`; the formal wall-clock records show that this extra work dominates any rebuild saving. Session 3's O5a full cells exceeded the 2% stability line for seeds 0 and 7 (4.638% and 3.481% relative MAD), but every O5b session/cell remained substantially slower, so the decision does not depend on discarding that session.

O5b candidate binary SHA-256: `089e0a7a92217344ccfda0c052f02ac674e2e5da89b241c01b901e23db1affde`. Source diff SHA-256: `f83433d504f09d351e79e599eb45025d86956e1d2a42311dafdeb272b930f9b3`.

## O5c: conservative phase entry

| Observation | Seed | O5a | O5c | Median session improvement | Session range |
|---|---:|---:|---:|---:|---:|
| full | 0 | 75.172 ms | 74.171 ms | 1.33% | 0.97% to 1.67% |
| full | 1 | 77.223 ms | 76.243 ms | 1.27% | 0.77% to 1.56% |
| full | 7 | 86.936 ms | 85.545 ms | 1.58% | 0.91% to 1.87% |
| summary | 0 | 61.417 ms | 60.928 ms | 0.89% | 0.59% to 0.93% |
| summary | 1 | 62.788 ms | 62.339 ms | 0.71% | 0.47% to 0.92% |
| summary | 7 | 70.494 ms | 69.774 ms | 1.11% | 0.86% to 1.17% |

All 18 session/cells were positive and the maximum within-cell relative MAD was 0.453%. The effect is therefore directionally stable, but below the plan's approximately 5% default collection line for a semantics-sensitive optimization. The candidate remains a source diff rather than being layered into O5d.

O5c candidate binary SHA-256: `42ac24393d3b1b4e37dc0288303688bf271adef4e322ce03daac4ffed78a648a`. Source diff SHA-256: `0c80a9d31cd1cd1e0c2f36aaf82ca0e818ed4ba4e9478e766333add376dac858`.

## O5d: guarded analytic continuous advance

| Observation | Seed | O5a | O5d | Median session improvement | Session range |
|---|---:|---:|---:|---:|---:|
| full | 0 | 75.294 ms | 50.665 ms | 32.93% | 32.54% to 33.01% |
| full | 1 | 77.665 ms | 53.737 ms | 30.61% | 30.58% to 30.81% |
| full | 7 | 87.170 ms | 58.202 ms | 33.32% | 33.22% to 33.65% |
| summary | 0 | 61.239 ms | 36.470 ms | 40.55% | 40.22% to 40.85% |
| summary | 1 | 62.757 ms | 39.157 ms | 37.42% | 37.30% to 37.83% |
| summary | 7 | 70.549 ms | 41.512 ms | 41.16% | 40.88% to 41.25% |

All 18 session/cells were positive. The maximum within-cell relative MAD was 1.063%, below the plan's 2% stability line. The O5d binary SHA-256 is `d2ddf01836d357364341b9f6be29a5ee8d646ea559c9afc7129b9ebd358d6e02`; source bundle SHA-256 is `6ac05c9f000a93f2a49fe0f4cf84bdca682f3f3da543fa21b1aae50238434bd6`; source diff SHA-256 is `46ab2a5fa699f73e2263e047bb7c3b7deff3e17ff2eb17d1ec692caadfe7b1d4`.

The implementation uses checked subtraction for integer job timers. Floating-point failure timers use one subtraction only when the value is finite, positive, at most `2^53`, the skipped span is positive, and the span remains strictly before the due tick. Non-finite, out-of-range and due-crossing values retain the repeated-decrement path.

The standalone guard experiment generated 1,570 boundary/grid cases: 1,205 exact equalities, 31 deliberately exposed bulk/repeated mismatches and 334 oracle-budget/invalid fallbacks. The guard accepted 68/68 verified integer equalities and 1,133/1,133 verified floating-point equalities, accepted no observed mismatch, and rejected all 31 observed floating-point mismatches. The controller observed byte-identical local/AMD128 output hashes; the JSON schema itself does not embed a host/build/source identity, so the retained file is mechanism evidence rather than independently host-bound benchmark evidence.

The local profiled F35 seed-0 summary run retained the same logical counts of 85,558 job ticks and 18,440,262 failure ticks, but executed them through 4,970 job and 869,688 failure analytic advances; no F35 fallback was needed. This is mechanism evidence for the fixed case, not a claim that every Plan stays in the fast-path envelope.

## Evidence inventory

- `amd128-host-manifest.txt`: host/build manifest embedded by O5b/O5c evidence; SHA-256 `918fa77dd002d00ca61d2c94fdf67bda91f5c5b53e6d5d4aac96fe6c73f1b794`.
- `amd128-host-manifest-o5d.txt`: O5d-extended manifest; SHA-256 `751ee02c946708be08d164bf242303be1c3fff41f8e5d8f0cc6865907beb6903`.
- `o5b/` and `o5c/`: three baseline/candidate sessions plus retained source diffs.
- `o5d/amd128-continuous-advance.json`: standalone exactness/guard experiment.
- `o5d-runtime/`: three O5a/O5d sessions, source diff and the local mechanism profile. The Linux binaries and vendor archive remain on AMD128 rather than in this local evidence directory; their hashes were live-read from AMD128 and are embedded in the formal JSON/manifest.
- `report-sha256.txt`: SHA-256 inventory for the retained report artifacts.

## Boundaries and next action

Implemented and verified: the three bounded candidates, exact result gates, raw AMD128 sessions, O5d guard tests and fallback behavior.

Measured: fixed F35 seeds `0/1/7`, full/summary, single pinned logical CPU, three serial sessions. Compile, initialization, serialization/write, batch throughput and peak memory are outside this comparison.

Not established: general equivalence for arbitrary Plans, a transition-owned persistent scheduler, callback microstep convergence, or cross-platform bit identity outside the guarded operations. O5d should be integrated as its own reviewed change and rerun through the repository's normal acceptance suite; O5b/O5c should not be layered into that integration.
