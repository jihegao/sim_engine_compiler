# I02.var01 bounded CLI signoff — scheduled IN transfer

**Accepted scope:** One scheduled, zero-duration `ItemTransfer` of one
`TEACH-LRU-01` from `<OUTSIDE>` to `DEPOT-01` at hour 4. The accepted E04 FAST
model is the direct source parent. Its depot stock begins at one and its base
stock at zero. The child adds the transfer, enables item tracking and half-hour
item result collection, and changes the description; the other 28 source tables
remain byte-equivalent at table value level. The pre-run source SHA-256 is
`85ee84d85e610f753215882fca59cc3331a9ce0f3313ae635f2a7422e8abcf4d`;
the exact-diff SHA-256 is
`ca442900d9acc434da0e947f30a20804bd10f0a924e5dd6248e495513d27364f`.

The guarded session-0 SSH native run
`i02-var01-in-v102-ssh-20261002-01` preserved GUI PID 13340, completed all
five steps with zero conversion errors and one expected simulation-log warning,
and round-tripped all 22 populated authored tables. Its physical log shows one
transfer task created and arriving at hour 4; new item ID 1 raises depot stock
from one to two. The report-only run
`i02-var01-item-results-v102-ssh-20261002-01` used the sealed SXO and a pinned
local report selector, without recalculation. The native `ItemResults` table
identifies `TEACH-LRU-01` at `DEPOT-01` in all 72 half-hour bins: nominal
`STSZ` and on-hand `STOHA` are both one before hour 4 and two from hour 4.
This is the depot item-stock position; it does not count mounted aircraft
items. The pre-run contract's `ItemPositionResults` name was conditional; the
actual table is `ItemResults`.

At hour 10, the depot issues pre-existing item ID 0 for an ordinary failure.
`STOHA` falls from two to one while `STSZ` stays two; the base backorder clears
at hour 12. Failed item ID 2 returns repaired to depot at hour 13.1667, and
on-hand stock returns to two. `ItemResultsTotal.STSZ` is about 1.888889, the
36-hour time average of one for four hours and two for 32 hours, not a
terminal count. The native stock ledger and the item result series agree.

The author replay passed 21/21 checks. Independent read-only replay passed
650/650 checks and returned bounded GO. The two closures seal 12 native raw
files plus two report-only raw files; `evidence-index.json` records their
SHA-256 hashes and local paths. The saved proprietary `.sxs` and all raw native
files remain local and ignored by Git. `make_report_settings.py` recreates the
selector from the fingerprinted installed default; the report-only runner
pins the exact selector hash.

**Boundary:** This case establishes one `IN` transfer with `TFDT=0`, one
item, one depot, one seed, and the installed CLI. It does not establish OUT,
BETWEEN, delay, split transfer, shortage or transfer-backorder priority,
reorder-point changes, procurement, GUI visual behavior, or cross-engine
parity. I02 remains incomplete and Issue #18 stays open.
