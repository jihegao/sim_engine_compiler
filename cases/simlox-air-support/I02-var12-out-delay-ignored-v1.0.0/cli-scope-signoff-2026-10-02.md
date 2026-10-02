# I02.var12 bounded CLI classification — OUT TFDT2

**Source and control:** Accepted I02.var02 one-unit `DEPOT-01`→`<OUTSIDE>`
OUT at h6 follows its unchanged h4 IN. The child changes only the OUT row’s
`ItemTransfer.TFDT` 0→2 hours and description; the IN row and 30 other
tables match. Parent source SHA-256 is
`7b15a1e0a6efcee9c772ac39dd52bb742a6eb23b6b711cf8e3cbc681aabe07e0`,
child source SHA-256 is
`a9eec9544de1b9c52b6dcf0ecd826ccbe524dbaba383dc9e66e694571e42cfc5`,
and exact-diff SHA-256 is
`317b5a2817613c89ef56c8b172ec4eaad9b8f2fd65db894a3470308c6b6ddae1`.
The installed manual p478 states that TFDT is ignored for OUT; this
single-run matched contrast directly tests that statement.

The guarded session-0 SSH native run
`i02-var12-out-delay2-v100-ssh-20261002-01` preserved GUI PID 13340,
completed five steps, converted with zero errors and exactly round-tripped
22 populated authored tables. Its sealed SXO fed report-only export
`i02-var12-depot-item-v100-ssh-20261002-01`. Two closures seal 14 local raw
files. Native output and the proprietary report selector remain local and
ignored by Git.

The parent physically removes item ID 0 from depot at h6 and logs OUT
transfer time zero, arriving outside at h6. The child removes the same ID
at h6 but logs transfer time two hours and OUT arrival at h8. With those
two task timing lines excluded, every other physical model-log line equals
the parent. All selected business report tables, including 72 half-hour
depot ItemResults rows, and all default business report tables equal the
parent. Depot nominal/on-hand stock is 1 before h4, 2 from h4 to h6 and 1
after h6 until later ordinary demand; h10 demand and h13.1667 repair are
unchanged. The item-report total values are horizon averages, not terminal
stock.

Author read-only replay passed 29/29 checks. Separate independent read-only
replay passed 361/361 with all 14 child raw seals, returned restricted GO
for the bounded timing counterexample and NO-GO for the literal ignored
claim. Its checker and exact verdict are under `review/` and indexed in
`evidence-index.json`.

**Classification:** The literal positive hypothesis “TFDT is ignored for
OUT” is **NO-GO** in this installed CLI run because native OUT transfer
duration and arrival differ. A **restricted GO** applies to the observed
unchanged depot stock departure and business reports. `<OUTSIDE>` has no
reported stock position here, and the delayed OUT arrival has no observed
downstream consequence. One available OUT after IN, one IID/depot, TFDT0
versus 2 and seed1 do not establish other delays, standalone OUT,
shortages, GUI rendering or cross-engine parity. I02 and Issue #18 remain
open.
