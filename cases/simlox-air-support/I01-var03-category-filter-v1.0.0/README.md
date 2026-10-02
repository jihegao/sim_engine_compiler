# I01.var03 category-aware task binding — bounded native matrix

This package tests the relationship between a task-referenced `ItemRepair` row, its `Tasks.TCID`, and the maintenance POINT selected by `Control.APID`. The accepted I01.var03 station case is the direct parent. Its fixed model supplies two workstation repair rows for the same LRU, a two-hour BASE↔DEPOT route, equal base spare1/depot spare0 stock under both POINTs, and a one-hour direct repair. The installed manual, physical pp. 338–339 and 439–441, describes the task category/level and station match.

The four inputs form a 2×2 matrix. `I01-LRU-DIRP` remains the task referenced by both `ItemRepair` rows in every arm. The real layer assigns that task `LRU-CM`; the alternate layer assigns it `DECOY-CM` and swaps the inert second task to `LRU-CM`. Both APIDs have complete allocations for both categories, crossed over the two stations: `AIR_BASIC` assigns `LRU-CM` to BASE and `DECOY-CM` to DEPOT; `AIR_DEPOT` does the reverse. The source diff freezes APID/description as the only within-layer change and the two `Tasks.TCID` cells/description as the only within-APID layer change. ItemRepair, station geometry, stock, mission, seed and horizon remain fixed.

## Native observation

Four guarded, serial session-0 SSH runs preserved GUI PID13340 and source fingerprints. All four imported/exported the 24 row-containing authored tables exactly, converted with zero errors (expected warning #108 and notice #2034), generated valid SXO and JSON report output, and SHA-256 sealed 12 local raw files each.

Every arm has the same physical LRU ID1 failure at h9.8829, base spare ID0 draw at h10, aircraft ready at h10.5, two later mission successes, and terminal ready aircraft1. The repair station crosses as predicted:

| Referenced task category | AIR_BASIC | AIR_DEPOT |
| --- | --- | --- |
| `LRU-CM` | BASE repair h10.1667–11.1667 | DEPOT repair h12.1667–13.1667 |
| `DECOY-CM` | DEPOT repair h12.1667–13.1667 | BASE repair h10.1667–11.1667 |

The DEPOT arms transport the same failed ID1 two hours each way and restock BASE at h15.1667; the BASE arms restock at h11.1667. All 72 half-hour SystemResults and StockTotalResults rows and the business summary match across all arms. The physical event logs establish the route, temporary depot backorder, and stock timing. Raw artifacts remain in ignored `runs/` directories and are indexed by ID and SHA-256 in `evidence-index.json`.

## Scope

The bounded claim is category-aware binding of this referenced repair task interacting with APID selection. The second task is inert and does not model competing live repair demand. Level filtering, simultaneous stock/resource/maintenance POINT selection, `<NONE>` reorder, generic station routing, GUI visual behavior and cross-engine parity remain unverified. Issue #18 remains open.
