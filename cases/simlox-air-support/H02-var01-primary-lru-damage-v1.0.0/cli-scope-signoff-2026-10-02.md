# H02.var01 primary-LRU native CLI scope sign-off — 2026-10-02

**Decision:** Accept one fixed-seed primary-LRU damage, local spare replacement and repairable-item return contrast. Publish this bounded H02.var01 slice while Issue #18 remains open.

## Frozen lineage and model

- Direct E01 parent SHA-256 `84ca1828f3669d2c91c9d826cae3187e0968ae9f8fed602d97155d2e82e99931`; H02 schema reference SHA-256 `67eb54c6148cd17c43e050eaf3d310bf7f66b96452526614ca1af416c16d9bcb`.
- Quiet control input SHA-256 `10e0b88f6c332292d9b22f0c6fd5e993eb225169a0909cf016e439bbaa581bb5`; child input SHA-256 `82564db9cd0d3f916a87264d16d390a42bf886f5748c843070bea20e6b1c4a92`.
- Exact diff SHA-256 `0995626c32d7586540c4d02d3bf0e50a1667756c2bee7e2628e698842eb8fc71`; pre-run contract SHA-256 `e1c24df6bbe399dcd0d3e503f0e5acec31fcc1ff9d5cf52051d14606b81afb4f`.
- E01-to-control changes only System.FRT and Item.FRT from 300000 to zero and the description. Control-to-child adds DamageType, MissionDamage, DamageItem and DamageReplacement plus its description. Manual physical pp193,425–428,432–433 and the installed dictionary support the directly mounted LRU, `REPF` and damage-specific replacement row.

## Native events and reconciliation

Both fresh serial session-0 SSH runs held `Global\SimloxIssue18NativeQueue`, completed import, export, calculation, JSON report and authored-table check, and preserved GUI PID13340/session1. The control/child exactly roundtrip 20/24 authored row-containing tables. Both converters report zero errors; warning #108 enables the log and warning #2053 notes the deliberately zero item FRT. All 24 raw files match their closure seals.

The quiet control launches at h8/20/32 and succeeds at h10/22/34 without damage or stock draw. The child logs BATTLE-HIT damage to physical LRU IDs 1/2/3 at h8.78145/20.7434/32.3406, each aborting its mission. At returns h9.28145/21.2434/32.6812, local spare IDs 0/1/2 are issued. Each system SURP task executes the E01-SURP ten-minute remove and twenty-minute fit subtasks; the aircraft is ready at h9.78145/21.7434/33.1812. Removed LRU IDs 1/2/3 start one-hour item DIRP at h9.44811/21.4101/32.8479 and return to BASE-01 stock at h10.4481/22.4101/33.8479. The model log shows physical stock level one-to-zero-to-one in every cycle. Both later missions launch and the aircraft ends ready.

Each arm has 72 aligned half-hour System and Stock bins and one ResultSummary row. Child System rows total `NDAM=3`, `NREPT=3`, zero ordinary failures, three half-hour-integrated system repair exposures of 0.5 hour each, zero lost-aircraft hours and terminal ready1. Child Stock rows have three `NDD` markers and no backorders; `PNB=1` remains a nominal aggregate in every bin, so instantaneous physical stock levels are read from the log. ResultSummary `MSTF=1` in both; `MSUF=1` in control and zero in child, consistent with three explicit aborts. Author replay passed 32/32 and independent read-only replay passed 7,701/7,701; their verdicts and the 24 raw seals are bound by `evidence-index.json`.

## Limits

This one-seed observation uses `REPF=1`, one directly mounted LRU, one spare and an explicit `DamageReplacement`. The ordinary E01 replacement path has the same task and duration, so it does not isolate the priority of DamageReplacement over fallback. It does not test discarded or intermediate repair fractions, damage over an existing failure, multiple consequences, shortage, other stations, GUI visual behavior or cross-engine parity.
