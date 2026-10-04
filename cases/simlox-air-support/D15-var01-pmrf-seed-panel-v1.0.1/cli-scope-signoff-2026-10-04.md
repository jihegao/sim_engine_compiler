# D15.var01 CLI scope sign-off — 2026-10-04

**Decision:** Accept this fixed five-seed `PMRF` panel as a reusable, bounded native SIMLOX CLI case under Issue #18. The source [contract](contract.json), [independent verdict](review/independent-verdict.json) and [evidence index](evidence-index.json) identify the exact inputs, runs and limits. The seed-1 v1.0.0 pair remains excluded because its fractional arm had four exchanges and no observed no-exchange opportunity.

## Frozen comparison and observations

| Seed | `PMRF=1` exchanges / four PMs | `PMRF=0.5` exchanges / four PMs | Fractional no-exchange PMs |
| --- | ---: | ---: | ---: |
| 2 | 4 | 2 | 2 |
| 3 | 4 | 4 | 0 |
| 4 | 4 | 2 | 2 |
| 5 | 4 | 3 | 1 |
| 6 | 4 | 2 | 2 |

Every arm reached system PM at 24, 48.5, 73 and 97.5 hours. Each physical replacement requested one local spare at the PM start, removed the installed LRU during the REMOVE phase, fitted a distinct physical LRU, then overhauled the removed item at `BASE-01` before returning it to stock. The fractional panel contains both exchange and no-exchange observations and four mixed seeds; seed 3's four exchanges are retained. All three fixed missions succeeded per arm. At the last half-hour bin (119.5–120), each selected item report has on-hand stock one and backorders zero.

## Evidence and review

- Ten native inputs have exact populated-cell import/export roundtrips. All 40 import/export/calculate/default-report steps exited zero with the protected GUI preserved. Each converter logged errors 0, warnings 1, notes 0; warning #108 states that enabling simulation logging may generate a large file.
- The native run `d15-var01-pmrf-seed-panel-v101-ssh-20261004-01` has closure SHA-256 `ab02b29de7bb7cfe4397aae19d34d95a3a31f31c2f0fe7fe692d398f8f768fc9` and 102 sealed raw files.
- The selected item report run `d15-var01-pmrf-seed-panel-v101-item-report-ssh-20261004-01` has closure SHA-256 `84d5b2a88889cd431afca79f9341a0534cc4c3e500530107645542a99bfab77c` and 22 sealed raw files. All ten reports select `TEACH-LRU-01` at `BASE-01` with 240 half-hour `ItemResults` rows and no default-report fallback. Per-bin item demand, withdrawal, PM and on-hand stock reconcile with event timestamps; `NBO` is zero throughout.
- The separate reviewer replay returned `GO_FULL_CONTRACT_BOUNDED` with 2,503/2,503 checks and no failures. It verified source pins, both closures, all raw SHA-256 seals, roundtrips, fixed source deltas, physical events and selected report rows. Its checker and verdict are under `review/`.
- Both native runs used session-0 loopback SSH with an `sshd.exe` ancestor, `Global\SimloxIssue18NativeQueue`, hidden CLI children, targeted watchdogs, source hashes before and after, and the active GUI PID 13340/session 1. Product `main` was not changed.

## Accepted scope and limits

The evidence supports four observed scheduled system calendar PM opportunities per arm, deterministic replacement with `PMRF=1`, and both replacement and no-replacement branches for `PMRF=0.5` across the five prespecified seeds in this one-aircraft, one-LRU, one-local-spare geometry. It supports the observed local stock movement and selected item report ledger. It does not establish a population probability, random-draw independence, `PMRQ>1`, `PMRQD`, `SCHED=N`, `FMIQ`, `FMDP`, PM failure modes, alternate locations, GUI rendering or cross-engine parity. Those D15 variants need separate evidence.
