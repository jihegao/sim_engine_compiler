# H03.var03 whole-aircraft attrition native CLI scope sign-off — 2026-10-02

**Decision:** Accept the observed permanent-aircraft-loss route for a certain `<ATTRITION>` `BATTLE-HIT` consequence versus the accepted position-FM direct-CM route. The child changes the FM consequence from `PROB=1` to 0 as it adds certain attrition, so the contrast is the configured pair. Issue #18 remains open.

## Frozen lineage and execution

- Accepted H03.var01 mode parent and byte-identical control SHA-256 `5297d5224b3a2086c26c663aa92cd51be7c349a24f7957428f47c21fcdc4ee7c`; H01.var01 `<ATTRITION>` schema reference SHA-256 `f519cd4549db879505c16bd5d4affb7e34f1db6227e71bebc27738442489d4f0`. Child SHA-256 `4b7a33a7458759fd3e8db0ad8f146929cdaf98ae409a9de4d8e8fe61186646b2`, contract SHA-256 `7cd19a4424a99bcdca28febf0d2d761c477476f5782b0e2c619f9681f1c2bf0b`, exact diff SHA-256 `3a19e2f2fc6eb06fc10e19cdcf50c2aaa525230084c26e2872e05290cd98c911`.
- Child adds one `DamageItem` row with `IID=<ATTRITION>` and `PROB=1`, changes `DamageFailureMode.PROB` 1→0 for `FM-POS-A`, and updates `DamageType` and problem descriptions. `MissionDamage.DAMP=1`, fixed mission schedule, parent FM/CM definitions, seed and horizon remain. Manual physical p193 and dictionary support permanent loss through this IID. Independent pre-run static review gave conditional GO after correcting the runner contract pin and 21/22-table checker count before native execution.
- Two fresh serial session-0 SSH runs held the host mutex and preserved GUI PID13340/session1. Each completed five native/check steps, zero converter errors, warning #108 only, 12 raw seals and exact 21/21 or 22/22 authored-table roundtrip. Author replay passes 26/26 checks and independent read-only replay passes 6,561/6,561 checks. The independent verdict and checker are recorded under `review/`.

## Observation and boundary

The control reproduces the H03.var01 three damage/FM/abort/half-hour-CM cycles, terminal ready1 and 1.5 aircraft-hours in repair. The child logs first-mission damage and attrition at h8.13665, aborts that mission, cancels the h20 and h32 missions at h20.3333 and h32.3333, and ends lost1/ready0 with no FM or CM task. Its 72 System bins integrate 27.86335 lost aircraft-hours; its `NDAM=0` is a native report result despite the explicit damage log. Control `NDAM=3`; both have ordinary `NFAIL=0`. All 72 Stock bins per arm have no demand/backorder and `PNB=1`.

This one-aircraft, fixed-seed contrast does not cover simultaneous positive FM and item consequences, population probabilities, alternate mission patterns, GUI visual behavior or cross-engine parity. A separate mixed traditional-LRU/system-owned-FM incomplete-repair diagnostic remains unpublished and unresolved.
