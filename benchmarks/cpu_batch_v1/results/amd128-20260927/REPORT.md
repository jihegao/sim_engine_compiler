# Issue #6 CPU batch baseline — AMD128 — 2026-09-27

Status: **formal measurement complete; independent data review accepted within scope**.

The single preregistered window completed all 56 cells with no failed or
missing cell in `921.500818382 s`, inside the 1,200-second limit.  The window ran
from `2026-09-27T06:06:00Z` through `2026-09-27T06:21:23Z`.  No formal rerun was
performed.

This is a same-host F35 43-day CPU baseline for the default unindexed
`event-time-v2` scan path.  It does not measure candidate dispatch, persistent
cross-call Plan handles, compilation, GPU execution, or another machine.

## Primary N=64 results

All primary cells used the identical `[0,1,7,7] * 16` seed list, one warmup,
three rotated repeats, CPUs `0-7`, and worker counts `1/2/4/8`.  Time columns
are the backend-specific warm primary boundary.  `Time` is
`median [minimum–maximum]`; MAD is median absolute deviation.  Throughput,
paired speedup, paired efficiency, and whole-process RSS are medians across the
three repeats.

| Backend | Observation | Workers | Time s, median [min–max] | MAD s | Samples/s | Paired speedup | Efficiency | RSS MiB |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Rust | Full | 1 | 7.327 [7.312–7.334] | 0.007 | 8.74 | 1.000 | 1.000 | 4913.5 |
| Rust | Full | 2 | 3.643 [3.640–3.647] | 0.003 | 17.57 | 2.011 | 1.006 | 4919.2 |
| Rust | Full | 4 | 1.579 [1.579–1.581] | 0.000 | 40.53 | 4.633 | 1.158 | 4921.0 |
| Rust | Full | 8 | 0.874 [0.868–0.878] | 0.004 | 73.24 | 8.393 | 1.049 | 4927.5 |
| Rust | Summary | 1 | 5.146 [4.755–5.171] | 0.025 | 12.44 | 1.000 | 1.000 | 1626.4 |
| Rust | Summary | 2 | 2.369 [2.360–2.591] | 0.009 | 27.01 | 2.007 | 1.003 | 1627.2 |
| Rust | Summary | 4 | 1.192 [1.188–1.195] | 0.003 | 53.70 | 4.306 | 1.076 | 1628.8 |
| Rust | Summary | 8 | 0.660 [0.632–0.662] | 0.001 | 96.91 | 7.829 | 0.979 | 1634.4 |
| PyO3 | Full | 1 | 12.172 [12.122–12.180] | 0.009 | 5.26 | 1.000 | 1.000 | 3261.1 |
| PyO3 | Full | 2 | 8.289 [8.254–8.397] | 0.035 | 7.72 | 1.468 | 0.734 | 3765.4 |
| PyO3 | Full | 4 | 6.291 [6.285–6.335] | 0.006 | 10.17 | 1.929 | 0.482 | 4213.8 |
| PyO3 | Full | 8 | 5.334 [5.266–5.362] | 0.028 | 12.00 | 2.273 | 0.284 | 4440.4 |
| PyO3 | Summary | 1 | 6.454 [6.452–6.496] | 0.002 | 9.92 | 1.000 | 1.000 | 1502.7 |
| PyO3 | Summary | 2 | 3.655 [3.646–3.661] | 0.007 | 17.51 | 1.770 | 0.885 | 1504.9 |
| PyO3 | Summary | 4 | 2.588 [2.566–2.591] | 0.003 | 24.73 | 2.507 | 0.627 | 1504.6 |
| PyO3 | Summary | 8 | 1.947 [1.921–1.973] | 0.026 | 32.87 | 3.315 | 0.414 | 1434.7 |

Rust Full produced observed paired median speedups of `4.633×` at four workers
and `8.393×` at eight workers, hence observed efficiencies above 100%.  Those
are host/cache/sample-specific results from three repeats.  They do not establish
algorithmic superlinearity, and this evidence has no hardware-counter or
frequency data that would justify attributing the values to cache, frequency,
or another mechanism.  No new timing run was added to resolve the effect.

## Startup probes

These eight single cells are descriptive N=1/N=8 startup and crossover probes.
They were not repeated and are excluded from every scaling claim.

| Backend | Observation | N | Workers | Warm time s | Samples/s | Whole-process wall s | RSS MiB |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Rust | Summary | 1 | 1 | 0.070 | 14.34 | 0.403 | 50.0 |
| PyO3 | Summary | 1 | 1 | 0.095 | 10.52 | 0.395 | 54.1 |
| Rust | Full | 1 | 1 | 0.092 | 10.87 | 0.607 | 117.0 |
| PyO3 | Full | 1 | 1 | 0.160 | 6.26 | 0.712 | 103.0 |
| Rust | Summary | 8 | 8 | 0.080 | 99.67 | 0.707 | 231.3 |
| PyO3 | Summary | 8 | 8 | 0.246 | 32.49 | 1.394 | 221.0 |
| Rust | Full | 8 | 8 | 0.110 | 72.90 | 1.496 | 660.8 |
| PyO3 | Full | 8 | 8 | 0.666 | 12.01 | 3.813 | 635.0 |

## Semantic admission

The primary semantic gate passed all 21 checks.  Every check's actual
`first_exact_divergence` was null, including the Python-reference comparison.
The latter retained the existing repository policy permitting only
`float_rel_tol=2e-15` and `float_abs_tol=1e-12`, but no tolerance was needed by
the observed results.  The legacy→O5 comparisons normalized only the expected
top-level Plan fingerprint; Full/Summary, duplicate-seed, worker-order, and
Rust/PyO3 comparisons were otherwise strict under their named observation
contract.

The untimed effective-eight supplement then passed 32/32 strict actual-result
checks for seeds `[7,0,7,1,0,1,7,7]`, Full/Summary, Rust/PyO3, and eight
effective workers.  It was a semantic supplement, not an N=64 timing pilot.
Candidate dispatch was absent from the Rust commands and unavailable through
the selected public PyO3 `run_batch` boundary.

These checks and hashes establish local artifact integrity and semantic
admission for this checkout.  They are not third-party attestation or an
external replication.

## Timing and memory boundaries

- Rust primary time is `stage-c-benchmark`'s `batch_execution_ns`.  It includes
  per-call preparation, Rayon pool construction, RunState initialization and
  execution.  It excludes Plan read/parse/fingerprint, result serialization,
  write, and process startup.  The fresh process first performs an untimed
  batch warmup; the tool also executes a timed single-sample diagnostic before
  the primary batch and a separate second end-to-end batch afterwards.
- PyO3 primary time is the public `run_batch` call.  It bundles Plan
  conversion, native parse/validation/preparation, pool creation, initialization,
  execution, Rust serialization/transfer, and Python JSON decoding.  Its Plan
  read, wrapper encoding/write, import, and process startup are outside that
  primary call. Plan-identity parsing and warmup validation/hashing happen
  before the timed call and influence process cache history; they are not
  zero-cost work. Available stages and whole-process wall distributions are
  retained in `summary.json`; batch initialization cannot be separated from
  execution through these supported boundaries.
- The timing boundaries differ, so this report computes no Rust↔PyO3 speedup or
  ratio and does not infer unavailable stages by subtraction.
- GNU time RSS is the high-water mark of the entire fresh process, not batch
  incremental allocation.  Rust RSS includes warmup plus the stage-c diagnostic
  executions and evidence work.  PyO3 retains both the warmup and measured
  result trees to prove equality, so its RSS can include both trees plus proof,
  encoding, imports, and evidence writes.  The two RSS series must not form an
  incremental-memory ratio.  Allocation counts, batch-only RSS, and per-thread
  peaks were not measured.
- The three-repeat min/max/MAD values describe this window's observed spread;
  they are not confidence intervals and do not constitute scientific
  uncertainty analysis. N64 repeats only three distinct seeds, not 64
  independent scenarios; this limits workload generalization.

## Frozen identity

| Item | Identity |
| --- | --- |
| Base commit | `595cb5eee9987324b19a8c3566f201f937e05f15` |
| Preparation/harness commit | `7ee2930ff16b26b07077405f0cd918ba6f294bc0` |
| Frozen source aggregate SHA-256 | `74139fc7d569f0f185c045a6ff4ca54f86d05033be8120c38111b20f47dfd942` |
| Manifest SHA-256 | `b529e41107a9b547c9329a10902da2559aed661c699c4027f9d95e077a0231d3` |
| Summary SHA-256 | `d46668d90f8b5c8f39d9baf006600f925d10193f6331c7e47e605e30a4aaaf64` |
| Measurement state SHA-256 | `46273aa25530987cf4e0d8940e7372f230462a791e3bf3137d2402f86c5575cc` |
| Protocol SHA-256 at reporting | `408d091d1fa26720b45b57f568ca110ed71cc09f4e30efb40db57bf7de8401f4` |
| Timed Plan SHA-256 / fingerprint | `beab59ac007f566d5e864346ddde6b5194420fae47e9eec9d0f710c76244163c` / `a7a27a982adc8b073cce0370c42d9e7284a48d2d038430e82618e906f4248ecc` |
| Seed list / schedule SHA-256 | `62747a163c1f63326f39722926ca6b910d50a4706942bcdbce403e996daee284` / `1d9395e596efe54401b24e1fbcfec185c9f8bb495016900a4238c9072d8b04a0` |
| Rust benchmark / runtime SHA-256 | `03d7d0e7ea1e7de10505936e8a7675f728bc580a4def52ee121f4dad64a9004a` / `316eeb625a4297b580821cb836d2ce90dee876efbbc7db2770cbcaf033ea536e` |
| PyO3 extension SHA-256 | `61dbcad01fb877e9c1b35acaffe1398c8b69305557ae126ca00450ef1c8acd6a` |
| Toolchains | Rust/Cargo `1.90.0`; CPython `3.12.13` |
| Host / placement | `g-1503-amd128`; AMD 3995WX; CPUs `0-7`, eight physical cores, one NUMA node; SMT siblings `64-71` excluded |

The timed Plan was the 43-day `event-time-v2`,
`stable-topological-serial`, `legacy-sequential-v1` Plan with no resource
dispatch index and source-input digest
`6b7730e1203dbbf0f04fed56bdebb1a58a7ff6c013c76ea2e63e86649de6c2f6`.
Plan compilation, release builds, and semantic admission were completed before
the window and were not timed.
Governor was `schedutil`, boost enabled, and affinity allowed CPUs0-127 before
the per-cell taskset restriction. CPU quota was not readable in this session;
no claim of unrestricted CPU quota is made. No host tuning was performed.

## Window controls and disclosed deviation

Preflight retained full process inventories, live snapshots, and agent stop
acknowledgements.  `top` monitoring at a requested five-second interval continued throughout the formal
window.  The known-tool scan did not initially meet the intended 30-second
cadence: the first two manual checks were at `06:06:23Z` and `06:07:13Z`;
the retained 30-second cadence began at `06:08:12Z`.  This deviation is kept in
the evidence and was not repaired with a rerun.

The retained monitors showed no known CPU-heavy benchmark, build, or test
overlap.  This is a controlled best-effort observation, not proof that the OS,
desktop, remote-access, or network services produced zero background load.
Those ordinary services were not stopped.

Independent read-back counted 183 `top` snapshots (175 gaps of five seconds,
seven of six seconds) and 29 known-tool scans. Background activity was nonzero:
one Codex snapshot reached 22.2% CPU and the editor extension host reached
29.0% CPU. The snapshots do not identify their affinity, so neither contention
on CPUs 0-7 nor its absence can be inferred. These are shared-host observations,
not exclusive-host peak-performance estimates.

Eight full host/process snapshots remain unchanged in the local evidence
directory but are excluded from the public archive because they contain
unrelated personal process information. The public state is an explicitly
named derivative with machine snapshots omitted, not a byte-identical original.
See [EVIDENCE.md](EVIDENCE.md) for exclusions and verification limits. Task-scoped
host and artifact paths in the frozen manifest are retained as provenance.

## Evidence and review status

- [summary.json](summary.json) — generated 16-row primary aggregates and eight
  startup probes.
- [manifest.json](manifest.json) — frozen source, artifacts, Plan, topology,
  schedule, and admission policy.
- [raw-evidence.tar.gz](raw-evidence.tar.gz) — 268 byte-preserved public raw
  files, with eight local-only host snapshots excluded as documented above.
- [independent-data-review.json](independent-data-review.json) — scope-limited
  acceptance of all cell evidence, semantic supplement, independently
  recomputed statistics, and local monitoring review.

The archive was extracted into a fresh directory and all 268 inventory hashes
verified. Independent acceptance covers this local run's data integrity and
reporting, not external replication, general optimization adoption, Windows
acceptance, or issue closure. Exact final-head CI is tracked in the Draft PR.
