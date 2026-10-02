# I02.var05 — source shortage during BETWEEN

This bounded case extends accepted I02.var03. The parent requests one LRU
from `DEPOT-01` to `BASE-01` at h6 after an h4 IN. This child requests three
instead, changing only `ItemTransfer.TFQTY` and the description; 30 other
tables are unchanged. Depot has two physical LRUs immediately before h6.

The guarded session-0 native run preserved GUI PID 13340, converted with
zero errors, and round-tripped all 22 populated authored tables. Physical
IDs 0 and 1 leave depot and arrive at base at h6. The third request becomes
one transfer backorder. At h10, ordinary aircraft demand uses base ID 0 and
creates a separate ordinary depot backorder. Failed mounted ID 2 finishes
depot repair at h13.1667; the transfer backorder is removed and a second
BETWEEN task moves ID 2 to base. The ordinary depot backorder remains in the
log and in the station report through h36. This one direct contention shows
the transfer request taking that returned item first.

Two report-only exports from the same sealed SXO each provide 72 half-hour
native `ItemResults` bins. At h6, depot `STSZ` and `STOHA` fall 2→0. Base
`STSZ` rises 0→3 while `STOHA` rises 0→2. Thus the target nominal position
records the full three-unit request when only two physical units have
arrived and one transfer backorder remains. Base on-hand falls to one at h10
and rises to two after the h13.1667 second transfer; terminal depot nominal
and on-hand are zero, base nominal three and on-hand two. Depot `NBO` is zero
through h10 and one thereafter; it does not count the separate h6 transfer
backorder. The unchanged aggregate `StockTotalResults.NBO=0` does not erase
the depot's item-position `NBO=1`. The summed *station nominal* positions change from two to three
at h6. The physical item-ID ledger keeps the scheduled shortfall separate
from the mounted item and ordinary demand.

The installed manual describes nominal updates as transfers actually occur.
The native target `STSZ=3` at the first two-unit sub-transfer is more specific
than that general description. This package reports the native observation
without claiming per-sub-transfer nominal conservation or a general rule.

`build.py`, `describe_diff.py`, and `validate.py` reproduce the source delta
and replay the accepted evidence. `make_report_settings.py` recreates local
proprietary depot/base selectors from a pinned installed default. Raw run
files and selectors remain local, ignored by Git and SHA-256 sealed in
`evidence-index.json`.

This establishes one available-two/request-three, zero-delay BETWEEN after
IN at one seed. It does not establish zero-stock behavior, arbitrary split
quantities, generic priority, lateral support, reorder or procurement,
positive delay, GUI visual behavior, or cross-engine parity.
