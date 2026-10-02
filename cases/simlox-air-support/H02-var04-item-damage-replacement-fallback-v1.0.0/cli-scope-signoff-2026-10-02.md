# H02.var04 damaged-LRU replacement fallback native CLI scope sign-off — 2026-10-02

**Decision:** Accept the fixed-seed `DamageReplacement` priority and ordinary `ItemReplacement` fallback for this directly mounted LRU. Publish this bounded H02.var04 slice while Issue #18 remains open.

## Frozen lineage and model

- Accepted H02.var01 primary-LRU source SHA-256 `82564db9cd0d3f916a87264d16d390a42bf886f5748c843070bea20e6b1c4a92`.
- Explicit input SHA-256 `511e5f0ae17a1ea9cd7794b926fd6f2fd63814116f4ca9571a0d18e4181c5d92`; fallback input SHA-256 `2e29c2ea72304544c68281e8629bd242cca3d6252cbbe7cea2c48e0a00716a97`.
- Exact diff SHA-256 `ec95b415eadba5032413d523fc38afdce12db4864e7deec5cf7446eab8708c82`; contract SHA-256 `c093910abcdcf57ebca688abda7bc3523c7d6fada99c368d6f2bb31e597090e4`.
- Parent to explicit adds only the ordinary one-hour `ItemReplacement` row and description. Explicit to fallback clears only the half-hour `DamageReplacement` row and changes description. Installed manual physical p428 specifies the lookup order; installed dictionary keys and executable/manual fingerprints are sealed in the contract and native closures. Pre-run static review gave conditional GO.

## Native observation and report

Both fresh serial session-0 SSH runs held `Global\SimloxIssue18NativeQueue`, preserved GUI PID13340/session1, completed five native/check steps, and sealed 12 raw files each. Exact authored-table roundtrips cover 25/24 row-containing tables. Conversion errors are zero in both; inherited warnings #108/#2053 remain. The inherited 10-column `ItemReplacement` table, whose last extra columns are null, survives native conversion and roundtrip.

Both arms launch at h8/20/32, damage LRU IDs1/2/3 at h8.78145/20.7434/32.3406, abort, and issue spare IDs0/1/2 after return. Explicit system SURP tasks start h9.28145/21.2434/32.6812 and finish h9.78145/21.7434/33.1812. Fallback SURP tasks start at the same times and finish h10.2814/22.2434/33.6812. The explicit `E01-SURP` subtasks have one-sixth-hour remove and one-third-hour fit; ordinary fallback subtasks each last half an hour. Removed LRUs undergo inherited one-hour item direct repair and return to stock. All three later readiness windows reconcile with the mission schedule.

Each report has 72 aligned half-hour System and Stock bins and one ResultSummary row. Both have three `NDAM`, three `NREPT`, three stock demands and receipts, no ordinary failures, attrition or backorders, `MSTF=1`, `MSUF=0`, and terminal ready1. System repair exposure integrates 1.5 versus 3 aircraft-hours. Author replay passed 32/32 checks; independent read-only replay passed 7,501/7,501 assertions, including 7,358 event/report checks. Their hashes are bound in `evidence-index.json`.

## Limits

This pair isolates the configured damage-specific replacement row against ordinary replacement for one directly mounted primary LRU, one base and one seed. It does not establish replacement behavior under shortage, multiple damaged items, other repair levels or stations, GUI visual behavior or cross-engine parity. Issue #18 remains open.
