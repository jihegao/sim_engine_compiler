# O5 Rust event-time-v2 conservative time-skipping prototype

Date: 2026-09-21

Status: implemented and accepted as an experimental `event-time-v2` candidate. This is not a replacement for `legacy-minute-v1`, and it is not yet a persistent callback scheduler.

## Outcome

The Rust runtime now has an explicit `event-time-v2` path. It derives the next observable minute from shipments, returns, running work, failure exposure, preventive thresholds, mission preparation/dispatch/success, deferred phase visibility, day boundaries and the requested horizon. It advances continuous job/failure countdown state across a proven-empty interval, then executes the unchanged canonical 15-phase minute table at the wake minute.

For F35 seed 0, the profiled run executed 1,609 wake minutes instead of 61,920 minute iterations and skipped 60,311 minutes. It rebuilt the conservative calendar 1,609 times, considered 384,040 candidate wakes, and preserved the repeated floating-point failure countdown through 18,440,262 explicit component ticks.

The implementation keeps mutable state in `Runtime`, outside `ExecutionPlan`. The compiler selects the profile explicitly, the profile participates in the Plan fingerprint, and `event-time-v2` rejects any non-canonical phase vector.

## Semantic verification

No tolerance or new golden was used for same-platform legacy/event comparison. The paired harness ignores only the expected `plan_fingerprint` difference and requires exact equality for seed, time, stop reason, RNG request tape, full trace, metrics and terminal state. Summary mode additionally requires both traces to be empty.

- Rust unit tests: 14 runtime + 6 paired-benchmark + 3 profile tests passed.
- Python/conformance/differential suite: 41 tests passed after rebuilding the local Rust binding.
- Event-specific differential suite: 9 tests passed in the required B1 → B3 → B2 → F35 order.
- F35 seeds `0`, `1`, `7`, both `full` and `summary`: exact business results, RNG and trace equality.
- F35 horizon checks at `299`, `300`, `301`, `61,919` and `61,920`: exact equality.
- Additional generated B1/B2/B3 parameter grid: 184 cases, 0 mismatches after excluding only Plan identity.
- AMD128 Rust tests and `cargo clippy --all-targets -- -D warnings`: passed offline with the locked dependencies.

Code review found and the tests now freeze two missed wakeups: a postflight job created after `resource_dispatch` that must request a remote spare on the next minute, and a zero-duration mission whose return becomes visible on the next minute.

## AMD128 paired benchmark

Protocol: one release binary, one process per session, CPU pinned to logical CPU 2, seeds `0/1/7`, `full/summary`, one warmup pair and six measured pairs per cell. Baseline/candidate order alternated. Runtime construction was outside `execution_ns`; `runtime.run(...)`, including result construction, was inside. Source bundle SHA-256 was `cd61564e034d755ff3ee681ce964a779d9db15ca867dc828201111810a71ecaf`; the two Plans were structurally equal after normalizing only `semantic_profile` (`paired_model_sha256` `9dfc9e834d4ca77c62b9f663b40046a2fc150464996caa49ff08707cb194d99c`).

The table is the median of the per-session medians from stable sessions 1 and 3:

| Observation | Seed | legacy-minute-v1 | event-time-v2 | Improvement |
|---|---:|---:|---:|---:|
| full | 0 | 354.613 ms | 75.764 ms | 78.63% |
| full | 1 | 319.882 ms | 77.917 ms | 75.65% |
| full | 7 | 289.923 ms | 87.768 ms | 69.74% |
| summary | 0 | 332.663 ms | 61.175 ms | 81.62% |
| summary | 1 | 296.262 ms | 62.629 ms | 78.88% |
| summary | 7 | 264.255 ms | 70.291 ms | 73.38% |

All 72 measured pairs in stable sessions 1 and 3 were exactly business-equivalent. Their maximum within-cell relative MAD was 0.524%. Session 2 is retained, not discarded: all 36 pairs were still positive and equivalent, but full/seed 0 had 3.565% relative MAD, above the predeclared 2% stability line, so it is not used in the headline table.

The local Apple M4 sessions independently showed 68.0%–82.0% improvement, but they are mechanism checks rather than formal acceptance evidence.

Raw evidence:

- `amd128-session-1.json`: stable, SHA-256 `b01eeb6cc32cbf74c5b6b1464e2f8db158b94c65152e18953c6b56468bc697cd`
- `amd128-session-2.json`: retained noisy session, SHA-256 `9da3cf4ac3ef3ec2fce35405357f685024aa57f1cb90fba747549d507dfceb5f`
- `amd128-session-3.json`: stable, SHA-256 `fc45ab73ad026f07866732ac98f0e357f8ec90af929e38021eb38f1a3d32e1a6`
- `amd128-host-manifest.txt`: host/toolchain manifest
- `local-session-1.json`, `local-session-2.json`: local mechanism check

## Rust DES references and boundary

The design borrows deterministic scheduling principles rather than importing a framework:

- [`simu-des`](https://docs.rs/simu-des/latest/simu/) uses a deterministic `(time, insertion)` event order and single-threaded execution per simulation, while independent simulations may run in parallel. That matches this repository's shared immutable Plan plus independent RunState model.
- [`simulacra::EventQueue`](https://docs.rs/simulacra/latest/simulacra/struct.EventQueue.html) uses integer time and an explicit sequence tie-breaker.
- [`Asynchronix Scheduler`](https://docs.rs/asynchronix/latest/asynchronix/time/struct.Scheduler.html) demonstrates keyed cancellation; [`simcore`](https://docs.rs/simcore/latest/src/simcore/state.rs.html) demonstrates lazy cancellation while peeking/popping.

No framework resource primitive was adopted because FIFO/actor scheduling would change the existing atomic multi-resource dispatcher and its `(priority, started_time, job_id)` order. Floating-point simulation time was also rejected; this Plan uses deterministic `i64` minutes.

## Limits and next step

This candidate is conservative time skipping, not yet SimPy-style persistent event callbacks:

- each wake rebuilds a temporary heap from current state and pops only the earliest minute;
- the wake minute still executes the complete canonical phase table;
- there are no persistent owner generations, stale-event removal or microstep convergence budgets;
- skipped job and failure exposure still applies repeated decrements, preserving legacy floating-point behavior but not eliminating that complexity;
- the Python SimPy reference remains a minute clock and does not execute `event-time-v2`.

The recommended next step is a separate O5b: replace state-derived calendar rebuilding with schedule/cancel calls at state transitions, owner generation tokens and a bounded `(time, microstep, phase, owner_order, sequence)` queue. It must retain the same exact differential gates before any direct callback applies business effects.
