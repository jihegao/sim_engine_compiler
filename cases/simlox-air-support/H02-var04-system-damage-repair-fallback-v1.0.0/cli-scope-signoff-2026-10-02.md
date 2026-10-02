# H02.var04 native CLI scope sign-off — 2026-10-02

**Decision:** Accept the fixed-seed `DamageRepair` priority and ordinary `SystemRepair` fallback for this configured system-damage pair. Publish this bounded H02.var04 slice while Issue #18 remains open.

## Frozen sources and guarded runs

- Accepted direct parent H02.var01 `system-input.json` SHA-256 `67eb54c6148cd17c43e050eaf3d310bf7f66b96452526614ca1af416c16d9bcb`.
- Explicit source SHA-256 `061cf67e39a67e2e736fde700a22e8c144f686bf67d328ca01d6dd0d3d981513`; fallback source SHA-256 `2079ab266c2b7e48b6cc14d369b48c355b5fc36bb32145a66a6eb166b1f0415b`.
- Exact diff SHA-256 `51a03a7dd777c59c896a802de5c2c43007e50eaec97b5c800bf975e1104406ef`; contract SHA-256 `22548078839af3118443adae440e43d4cd8e17d0f930d3adc8806deceb12029d`.
- Installed manual physical p428 documents the damage-specific then ordinary repair lookup; installed dictionary and executable fingerprints are pinned in the contract and run closures. The pre-run static review gave conditional GO.
- Two fresh serial session-0 SSH runs held `Global\SimloxIssue18NativeQueue`, preserved GUI PID13340/session1, completed all five native/check steps, and sealed 12 raw files each. Authored-table roundtrips are exact for 18/17 row-containing tables. Both converters report zero errors and warnings #108/#126/#254; #254 states `REPF` is ignored for system damages.

## Observed native behavior

Both arms launch at h8, h20 and h32, then suffer `BATTLE-LOSS` at h8.78145, h21.1446 and h32.1965, aborting each mission. Their local system direct repairs begin at h9.28145, h21.6446 and h32.393. The explicit arm's three tasks plan one hour and complete at h10.2814, h22.6446 and h33.393. With the damage-specific row absent, the fallback arm's tasks plan two hours and complete at h11.2814, h23.6446 and h34.393. Readiness returns at completion. The second and third launches occur after the preceding repair in both arms.

Each report contains 72 aligned half-hour System and Stock bins and one ResultSummary row. Each has three `NDAM`, three `NREPT`, no ordinary failures, no attrition, terminal ready1, `MSTF=1` and `MSUF=0`. System repair exposure integrates three versus six aircraft-hours. Stock rows and ResultSummary are cell-identical. The event log establishes the changed direct-repair duration; the report independently reconciles it. Author replay passed 29/29 checks and independent read-only replay passed 7,490/7,490 assertions, including 7,362 per-arm event/report checks. Their verdicts and evidence are bound by `evidence-index.json`.

## Limits

This observation establishes lookup priority and fallback for one `BATTLE-LOSS` `<SYSTEM>` damage, one airframe, one station, three missions and one seed. It does not prove `DamageReplacement` or `ItemReplacement` order, item-level repair fallback, other maintenance structures, GUI visual behavior or cross-engine parity. Issue #18 remains open for those and the other planned cases.
