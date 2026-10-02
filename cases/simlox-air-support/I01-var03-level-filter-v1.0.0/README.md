# I01.var03 level-aware task binding — bounded native matrix

This package tests how the level attached to a task-referenced `ItemRepair` row and `Control.APID` jointly select a maintenance station. Its direct parent is the accepted I01.var03 station case. The installed manual, physical pp. 338–339 and 439–441, describes task category/level and maintenance allocation matching.

The four inputs form a 2×2 matrix. Both `ItemRepair` station rows always reference `I01-LRU-DIRP`; both Tasks have category `LRU-CM` and equal neutral descriptions. In the base layer, the referenced task has `TLID=BASE`, which maps to `LEVL=1`; in the alternate layer it has `TLID=ALT`, which maps to `LEVL=2`. The second Task is inert and receives the opposite TLID. Both APIDs allocate both levels with crossed stations: `AIR_BASIC` sends BASE to BASE-01 and ALT to DEPOT-01; `AIR_DEPOT` reverses these. Within a layer, only `Control.APID` and description change. Within an APID, only the two `Tasks.TLID` cells and description change. The repair rows, stock, station geometry, mission, seed and horizon stay fixed.

## Native observation

Four serial guarded session-0 SSH runs preserved GUI PID13340 and all source fingerprints. Each imported and exported the 24 row-containing authored tables exactly, converted with zero errors, generated valid SXO and report output, and SHA-256 sealed 12 local raw files. The converter emitted the expected warning #108 and notice #2034. Author replay passed 45/45 checks.

Every arm has the same physical LRU ID1 failure at h9.8829, BASE spare ID0 draw at h10, aircraft ready at h10.5, two later mission successes and terminal ready aircraft1. The repair route crosses as predicted:

| Referenced task level | AIR_BASIC | AIR_DEPOT |
| --- | --- | --- |
| BASE, LEVL1 | BASE repair h10.1667–11.1667 | DEPOT repair h12.1667–13.1667 |
| ALT, LEVL2 | DEPOT repair h12.1667–13.1667 | BASE repair h10.1667–11.1667 |

The DEPOT arms transport the failed ID1 two hours each way and restock BASE at h15.1667; the BASE arms restock at h11.1667. All 72 half-hour SystemResults and StockTotalResults rows and business summaries match across the arms. Raw artifacts remain in ignored `runs/` directories and are indexed by ID and SHA-256 in `evidence-index.json`.

## Scope

The claim is bounded level-aware binding for one referenced repair task interacting with APID selection. Since `BASE` and `ALT` also map to different numeric LEVL values, the experiment does not isolate TLID label from LEVL. The second task is inert; no competing live repair demand is tested. Category interaction, simultaneous three-allocation POINT selection, `<NONE>` reorder, generic routing, GUI visual behavior and cross-engine parity remain unverified. Issue #18 remains open.
