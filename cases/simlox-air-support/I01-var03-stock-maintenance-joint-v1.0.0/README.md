# I01.var03 joint stock and maintenance POINT selection — bounded native matrix

This package tests whether one `Control.APID` choice jointly selects `StockAllocation` and `MaintenanceAllocation` rows in a model with a single failed LRU. Its direct parent is the accepted I01.var03 repair-station case. The installed manual, physical pp. 338–339 and 439–445, and the installed table dictionary describe the selected POINT groups, task match and stock-size field.

The four frozen inputs have identical authored tables except `Control.APID` and description. The four POINT groups form a 2×2 matrix:

| BASE spare size | BASE repair | DEPOT repair |
| --- | --- | --- |
| 1 | `AIR_BASIC` | `AIR_DEPOT` |
| 2 | `AIR_TWO_BASE` | `AIR_TWO_DEPOT` |

Every POINT has `DEPOT-01` stock size zero and a complete `LRU-CM/BASE` maintenance assignment. Both `ItemRepair` rows reference fixed task `I01-LRU-DIRP` and take one hour. Stations, two-hour transport, seed, missions and horizon are fixed. There are no authored `ItemReorder` or `ResourceAllocation` business rows.

## Native observation

Four serial guarded session-0 SSH runs preserved GUI PID13340 and all source fingerprints. Every arm exactly round-tripped the 24 row-containing authored tables, converted with zero errors, generated valid SXO and report output, and sealed 12 local raw files. Author replay passed 45/45 checks.

The first ordinary LRU failure occurs at h9.8829 in every arm; the base spare ID0 is issued at h10, the aircraft is ready at h10.5, two later missions succeed, and one aircraft is ready at the end. The physical log initializes BASE stock at level 1 or 2 according to the selected POINT. The extra spare changes the installed failed LRU from physical ID1 to ID2; the failed item is repaired and returned, restoring the selected stock level. BASE arms repair h10.1667–11.1667. DEPOT arms move the failed item two hours each way, repair h12.1667–13.1667 and return it to BASE stock h15.1667.

All 72 half-hour SystemResults and StockTotalResults rows and the business summary are equal across the four arms. `StockTotalResults` does **not** expose on-hand stock quantity in this model. The physical `model.log` stock initialization, issue and return events establish the size difference; the aggregate report corroborates absence of backorders and unchanged aircraft outcomes. Raw artifacts stay in ignored `runs/` directories and are indexed by ID and SHA-256 in `evidence-index.json`.

## Scope

The claim is simultaneous selection of these two allocation tables for one LRU, two stock levels, two repair stations and one seed. It does not test `ResourceAllocation` in the same model, procurement, reorder, stock shortage, category/level interaction, generic POINT selection, GUI visual behavior or cross-engine parity. Issue #18 remains open.
