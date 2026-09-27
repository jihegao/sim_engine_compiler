# Same-Rust three-arm CPU ablation — AMD128, 2026-09-27

## Outcome

The sole formal window completed **99/99 cells in 85.675827 seconds**, within the frozen 1200-second limit. None of 33 predeclared comparisons met the benefit threshold: 29 were classified as regression and four as no-demonstrated-benefit. Both cache and candidate regressed against scan in every measured group. This bounded experiment supports **no default adoption**. It is not a general complexity or statistical-significance claim.

For real J35 summary, candidate/scan paired median ratios were execution **1.162759**, end-to-end **1.181798**, and whole-process RSS **1.151377**. Candidate/cache also regressed (execution 1.061700, end-to-end 1.050009). Full observation retained the negative result. Guard or visit reduction is not sufficient evidence of a runtime benefit.

## Source and semantic admission

- Host: `g-1503-amd128`, 128 logical CPUs; formal cell processes pinned by `taskset -c 0-7`, one batch worker; driver snapshots retain its `0-127` affinity.
- Measured source: `cf50eec2f9fdf1ac76e3d292e8b42b6f33f98b38`; based on preserved PR #25 head `9737822b22b1ab4d8617b999a132440b1ffd90a0`. Prior F35 evidence and its 921.5-second window were not rerun or modified.
- Same existing Rust kernel and #8 dispatch implementations: scan without dispatch index, blocked-result cache using indexed Plan, and event-driven candidates using that indexed Plan. No new interpreter or independent optimized kernel.
- LLVM/MLIR 23.1.1, Rust 1.90.0, Python 3.12.13, SimPy 4.1.1. Toolchain provenance and binary hashes are included.
- Real J35 canonical input/manifest were reproduced by the official upstream exporter/Adapter at upstream `0e709bdcc2d692d9cfed49b9037c76ef71aefe33`, without a database. File SHA-256 `ff830e6c021b74491bb58fd902a46ed5bc852e7170f27300ff40c028e33e2793`; canonical semantic digest `faf7c801351fd1cd3817fe3f03fe2b7e95056a7c1d9733e5863b291fddc2a689`.
- Untimed verification: Rust 37, existing differential 40, IR reuse 9, admission controls 13, driver/summary/prior controls 39; all passed, no skips/filtered tests.
- Full admission: 10 inputs, 11 groups, 240 semantic rows, 60 profile outputs. Reference vs Rust legacy compares the complete result, with only sampled value_minutes allowing rel 2e-15/abs 1e-12; all other values exact. Rust legacy/O5 differs only by plan fingerprint; three Rust arms compare exactly, summary drops trace only, profiled/unprofiled results agree. Duplicate seeds [7,0,7,1] preserve order at workers 1 and 3.
- The initial untimed attempt at `ec1ac66` exposed a real local capacity diagnostic mismatch despite agreement among Rust arms. Logs are preserved. The narrow Rust-only fix restores local personnel/equipment rule IDs/details while retaining routed diagnostics; no Python, allocation, ordering, RNG, workload or tolerance change. Independent review and the full gate passed after the fix.
- Independent pre-window review validated 719 raw hashes, exact plans/binaries/schedule and all agent stop acknowledgements before state creation. No build/test/profile overlapped the formal window.

## Frozen experiment and interpretation

J35 uses its original 61920-minute horizon. Synthetic low-contention, sparse-affected and dense-affected families each use sizes 4/16/64 and a common 222-minute horizon; they are explicitly synthetic, not substituted upstream cases. Each group has three rotated paired repeats; each fresh process performs initial Plan loading, one warmup batch, a diagnostic single-sample execution, one segmented measured three-sample batch, and a second independent measured three-sample batch inside the end-to-end interval. Both measured batches use seeds [0,1,7]. All timed cells use event-time-v2, legacy-sequential-v1 and stable-topological-serial. Summary is measured for all ten inputs; full is additionally measured for J35.

Benefit requires execution and end-to-end median paired ratios <=0.95, all three end-to-end ratios <1, and RSS <=1.05. Regression is execution or end-to-end >=1.05, or RSS >1.05. Remaining comparisons are no-demonstrated-benefit. Ratios below are medians of paired ratios, not ratios of arm medians; smaller is better.

| Group | Comparison | Execution | End-to-end | RSS | Frozen classification |
|---|---|---:|---:|---:|---|
| j35 | cache/scan | 1.095186 | 1.121293 | 1.146983 | regression |
| j35 | candidates/scan | 1.162759 | 1.181798 | 1.151377 | regression |
| j35 | candidates/cache | 1.061700 | 1.050009 | 1.003792 | regression |
| synthetic-low-contention-n4 | cache/scan | 1.212123 | 1.243464 | 1.000000 | regression |
| synthetic-low-contention-n4 | candidates/scan | 1.254139 | 1.292024 | 1.000000 | regression |
| synthetic-low-contention-n4 | candidates/cache | 1.040760 | 1.022410 | 1.000000 | no-demonstrated-benefit |
| synthetic-low-contention-n16 | cache/scan | 1.106406 | 1.140388 | 1.000000 | regression |
| synthetic-low-contention-n16 | candidates/scan | 1.252797 | 1.257685 | 1.000000 | regression |
| synthetic-low-contention-n16 | candidates/cache | 1.137297 | 1.093178 | 1.000000 | regression |
| synthetic-low-contention-n64 | cache/scan | 1.125185 | 1.093366 | 1.000000 | regression |
| synthetic-low-contention-n64 | candidates/scan | 1.740270 | 1.579463 | 1.000000 | regression |
| synthetic-low-contention-n64 | candidates/cache | 1.565966 | 1.444588 | 1.000000 | regression |
| synthetic-sparse-affected-n4 | cache/scan | 1.248981 | 1.234098 | 1.000000 | regression |
| synthetic-sparse-affected-n4 | candidates/scan | 1.267991 | 1.269445 | 1.000000 | regression |
| synthetic-sparse-affected-n4 | candidates/cache | 1.021474 | 1.014457 | 1.000000 | no-demonstrated-benefit |
| synthetic-sparse-affected-n16 | cache/scan | 1.151429 | 1.215108 | 1.000000 | regression |
| synthetic-sparse-affected-n16 | candidates/scan | 1.202609 | 1.236575 | 1.000000 | regression |
| synthetic-sparse-affected-n16 | candidates/cache | 1.043553 | 1.030750 | 1.000000 | no-demonstrated-benefit |
| synthetic-sparse-affected-n64 | cache/scan | 1.089833 | 1.165908 | 1.000000 | regression |
| synthetic-sparse-affected-n64 | candidates/scan | 1.132925 | 1.176377 | 1.000000 | regression |
| synthetic-sparse-affected-n64 | candidates/cache | 1.034850 | 1.013997 | 1.000000 | no-demonstrated-benefit |
| synthetic-dense-affected-n4 | cache/scan | 1.187366 | 1.166729 | 1.000000 | regression |
| synthetic-dense-affected-n4 | candidates/scan | 1.248762 | 1.216515 | 1.000000 | regression |
| synthetic-dense-affected-n4 | candidates/cache | 1.054347 | 1.042671 | 1.000000 | regression |
| synthetic-dense-affected-n16 | cache/scan | 1.136212 | 1.176034 | 1.000000 | regression |
| synthetic-dense-affected-n16 | candidates/scan | 1.193810 | 1.180767 | 1.000000 | regression |
| synthetic-dense-affected-n16 | candidates/cache | 1.050694 | 1.024846 | 1.000000 | regression |
| synthetic-dense-affected-n64 | cache/scan | 1.099932 | 1.093365 | 1.000000 | regression |
| synthetic-dense-affected-n64 | candidates/scan | 1.250430 | 1.215723 | 1.000000 | regression |
| synthetic-dense-affected-n64 | candidates/cache | 1.025092 | 1.089405 | 1.000000 | regression |
| j35-full | cache/scan | 1.211107 | 1.083789 | 1.046905 | regression |
| j35-full | candidates/scan | 1.272900 | 1.119747 | 1.046758 | regression |
| j35-full | candidates/cache | 1.053613 | 1.033178 | 0.999860 | regression |

## Timing and memory boundaries

[phases.csv](phases.csv) contains every arm/group phase median. Raw reports retain individual repeats. Plan read, parse/validation, fingerprint, single RunState initialization, single execution/serialization, batch execution/serialization/write and end-to-end are measured separately by the existing Stage C harness. Batch execution includes prepared-plan preparation, worker-pool setup, per-sample initialization and execution; it is not pure scheduler time. End-to-end is a separately executed read→parse→fingerprint→batch→serialize→write interval, not the sum of separately measured phase medians; it excludes warmup and diagnostic single-sample work. Whole-process wall and GNU time RSS include the entire fresh Stage C process, including initial loading, warmup, single-sample and both measured batch executions; RSS is not batch-only or per-sample memory.

Core→MLIR→Plan compilation was recorded before formal timing, with whole compiler-process RSS; Python import/lowering/Core stage timers are also retained, with separate RSS explicitly unavailable. These are absolute preparation diagnostics, not paired compilation benchmarks or amortization evidence. Compiler diagnostics are summarized in compilation.csv.

Counters are collected only in the separate seed-0 profile runs and validated against unprofiled outputs. Conditional profiling hooks remain compiled into the timed common kernel; this experiment does not establish zero overhead versus the previous binary. Tiny synthetic batches and three repeats limit generalization; no confidence intervals or broad speedup claim are inferred.

## Workload shape and IR reuse

[workload-counters.csv](workload-counters.csv) preserves all 60 seed-0 counter rows. [counter-review.md](counter-review.md) gives the independent scale-by-scale analysis. In sparse N64, candidate guards fall from 432 to 160, but require 832 index waiter visits and 544 summary merge inputs. Dense N64 full observation adds 476 replay visits to 484 candidate visits, matching scan's 960 outer visits. Low-contention N64 saves no guards and incurs 8,320 index waiter visits and 8,192 merge inputs. J35 saves 607 guards while traversing 21,082 index waiters and 202,770 dependency rules. These counts are consistent with maintenance costs offsetting selectivity; they do not measure per-operation causal cost or prove an asymptotic result.

IR reuse changes mission frequency, resource counts and process composition through persisted Business IR, then lowers to Core IR and independent Plans under both profiles. Six revisions have distinct fingerprints and explicit edited paths. The legacy variants have Python reference outputs; event-time Python execution remains unsupported and is checked through the cross-profile/Rust gates. This is bounded synthetic model/IR reuse without per-variant runtime code changes, not a J35 provenance claim.

## Host admission and completion

Preflight normalized 1-minute load: 0.001602173; postflight: 0.009262085; threshold 0.05. Visible PIDs: 1483 / 1482. Both snapshots had no detected heavy processes. All cell before/after admission and overlap checks passed. This does not establish zero background load. The once-only state is complete, with no missing cells, retry, resume, or second window.

## Evidence layout

- `summary.json`: all ratios, paired repeats, arm medians, classification and limits.
- `pre-window-review.json`: independent admission and stopped-agent receipt.
- `raw-evidence.tar.gz`: a publication derivative of run-relative evidence, including failed untimed attempt, successful logs/receipt, Business/Core/Plans, reference and Rust outputs, profiles, formal manifest/state and every cell report/time/record. The state omits only pre/post `ps_output`; the duplicate console is excluded.
- `EVIDENCE.json`: bundle hash, complete file inventory, original/published state hashes and explicit redaction record; original absolute paths identify the originating checkout and are not rewritten.
- `toolchain-preparation.json`: download/attestation/build identities. Large external toolchain archives and executable binaries are omitted; their hashes and source versions are retained.

Extract the archive at repository root to recover `runs/three-arm-v1/`. The pure evidence summarizer can verify the frozen run from another checkout; live admission/build validators additionally require the original paths or a newly generated local evidence set. Do not rerun formal timing to reproduce this report. Generated runs remain separate from frozen upstream source snapshots.

Raw pre/post process arguments contained credential-looking assignments from unrelated services. Original state/console remain immutable locally; the public derivative removes the complete `ps_output` strings and excludes the duplicate console. All load, PID visibility, known-heavy-process lists, per-cell overlap results, command/timing/result hashes and counters remain unchanged. This limits public reinspection of unrelated process arguments, not the disclosed numerical comparisons.
