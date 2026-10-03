# F02.var03 native CLI scope signoff — 2026-10-04

**Decision: ACCEPT a bounded one-versus-two P-MAINT capacity comparison for `simlox/main`.** This is one F02.var03 conflict/no-conflict dimension, not a global no-conflict claim. F02.var04 and Issue #18 remain open; product `main` is unchanged.

## Frozen source and execution

- The accepted one-worker control is [F02.var02 risk](../F02-var01-var02-integrated-fleet-v1.0.2/cli-scope-signoff-2026-10-04.md): parent input SHA-256 `ae46b08a6ef6fd063906b888fb3c73fba06edcb57acc1a4ade49fc62c53fd7d3`, native closure `b82da3cbed601408e4a72cda5c2fd498286a8f1b3ebfa07c003d4d4f8e6c91c4`, evidence index `a6c704eefc00c544be0ef54ca4487ebe27b99258130d6650d3923c17421fc906`.
- The [pre-run contract](contract.json) SHA-256 is `cd4749948227c6747e09080e76b20078eb1124c79cf8bc0d5fd6ba3bec5447ac`; [child input](no-conflict-input.json) `120981bcf34f2500f10d896f44db48e49d60b28c7a1c2712044fc6fa0d34b109`; [exact parent diff](exact-diff.json) `dd6c578d4f2fdb8e972824b5e1ce3ae0be141c887c47458467816acbdc50f329`. The sole authored change is `ResourceAllocation` row 0, P-MAINT at BASE, `RQTY 1→2`. Installed SIMLOX executable SHA-256 is `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`; manual `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`; dictionary `11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`. Proprietary sources are not uploaded.
- New guarded session-0 SSH run `f02-var03-pmaint2-v100-ssh-20261004-01` used `Global\SimloxIssue18NativeQueue`, hidden native CLI processes and preserved GUI PID 13340. Its closure SHA-256 is `36c4b56a022595f5b2d08561ed1e864ef4c6b392cdb06e8f9d418a7dea7ea251`. Import, export, calculation, report and exact 30-populated-table roundtrip completed. Converter Errors 0, Warnings 1 (known ENLOG #108), Notes 0. The [evidence index](evidence-index.json) SHA-256 is `5f8eef8422da6ea39e8844768544f0228de564f78197f4630d56a0c5d65cb7db`; it seals 12 new raw files locally and pins the accepted control.

## Observed worker and report behavior

The accepted control has simultaneous first-day PM subtask requests at hour 28.5: aircraft 0 uses the sole P-MAINT until 29.5, then aircraft 1 uses it until 30.5. The child grants one worker to each at 28.5 and both PMs complete at 29.5, eliminating that worker wait. Its second-day PMs also overlap from 53.5 to 54.5; the parent completed them at 54.5 and 55.5. The one-worker P-CREW pool still queues preparation work.

The mission summary, one critical fault, aborted risk mission, cancelled fourth mission, physical two-way depot LRU/SRU route and all 120 half-hour StockTotalResults rows match the parent. SystemResults changes occur only in eight PM/availability fields; ResourceResults changes occur only in capacity, occupancy and waiting fields. Both arms finish with two ready aircraft, no stock backorder and no worker wait. The [author replay](author-validation-2026-10-04.json) passes **834/834** checks, SHA-256 `9f8be567acc8e6f9041fc007df918755ffdd30e115457b7e2f3dd3c0dbdd4afb`. A separate reviewer used [independent code](review/independent_replay.py), SHA-256 `00ab0ef4cebc6b2fe10a6b8bb447bb315e2920706cb6644dd8827e586dfed1a7`, and recorded [8,151/8,151 GO](review/independent-verdict.json), verdict SHA-256 `8ebe0df2d5b0187840216a9c8ef14d32c2706f7a68f97d0aca1e5af0d4edee7e`.

## Scope boundary

One seed, two aircraft, one base/depot pair, a single named worker-pool capacity switch and 60 hours. Crew waiting persists; the child is not universally conflict free. This evidence does not establish other resource mixes, scheduling priorities, population risk, larger fleets, terminal-in-progress variants, GUI visual behavior or cross-engine equivalence. F02 and Issue #18 remain open.
