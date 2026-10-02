# I01.var03 three-allocation POINT selection — bounded native matrix

This package tests whether one `Control.APID` selects `StockAllocation`, `ResourceAllocation` and `MaintenanceAllocation` together in a model with an active two-crew preparation and one repairable LRU. It extends the accepted joint stock/maintenance case with the accepted I01.var01 preparation/resource donor. The installed manual, physical pp. 338–339 and 439–445, and table dictionary describe the task match and POINT selection.

The four frozen inputs differ from each other only in `Control.APID` and description:

| POINT | BASE spare size | BASE P-CREW capacity | Failed-LRU repair |
| --- | ---: | ---: | --- |
| `AIR_BASIC` | 1 | 2 | BASE |
| `AIR_DEPOT` | 1 | 2 | DEPOT |
| `AIR_TWO_BASE` | 2 | 3 | BASE |
| `AIR_TWO_DEPOT` | 2 | 3 | DEPOT |

All four POINTs allocate zero DEPOT spares and zero P-OTHER. The same preparation takes 10+20 minutes, requests two P-CREW for its first subtask, and runs before each of three missions. LRU task, two-hour station transport, seed and 36-hour horizon are fixed. There are no authored `ItemReorder` business rows. Crew capacity 2/3 tracks stock size 1/2, so this matrix cannot isolate their separate causal effects.

## Native observation

Four serial guarded session-0 SSH runs preserved GUI PID13340 and all source fingerprints. Every arm exactly round-tripped 29 row-containing authored tables, converted with zero errors, produced valid SXO/report output and sealed 12 local raw files. Author replay passed 49/49 checks. Raw artifacts remain in ignored `runs/` directories, indexed with SHA-256 in `evidence-index.json`.

Each run performs three preparations at h7–7.5, h19–19.5 and h31–31.5. The first subtask leases and returns two P-CREW each time. All 72 half-hour `ResourceResults` bins carry the selected total capacity of 2 or 3; `NRUM` is about 0.6667 crew in each preparation's first bin, the interval-average number in use. No resource wait is reported.

The first ordinary LRU failure occurs at h9.8829 in all arms. BASE spare ID0 is issued at h10 and the aircraft is ready at h10.5. BASE stock starts at level 1 or 2, falls by one on issue and recovers after the failed item returns. BASE arms repair that item at h10.1667–11.1667. DEPOT arms send it two hours each way, repair at h12.1667–13.1667 and restock BASE at h15.1667.

The later trajectory differs. Both BASE arms complete missions two and three, with one failure and `MSUF` 2/3. Both DEPOT arms complete mission two, then have a second ordinary critical LRU failure at h33.9619 and abort mission three. A second spare is issued at h34, the aircraft is ready at h34.5, and the second failed item starts a two-hour trip to DEPOT at h34.1667. It remains in transit at the h36 horizon. These arms have two failures and `MSUF` 1/3. The corresponding physical BASE stock ends at level 0 or 1, rather than its initial level 1 or 2. All arms end with one ready aircraft.

`SystemResults` and `StockTotalResults` have 72 half-hour bins per arm. The System and Stock aggregate reports and summary are equal within each repair-station pair across stock/crew sizes, and differ between BASE and DEPOT as described. `ResourceResults` are equal within each crew-capacity pair across repair stations. `StockTotalResults.NBO` is zero even though the physical log records an open internal DEPOT repair backorder at the horizon; this aggregate is not a physical item ledger and does not expose on-hand stock quantity. The physical `model.log` supplies the stock and in-transit accounting.

## Scope

The claim is simultaneous selection of the three complete allocation tables by APID for this LRU, preparation task, four POINTs and seed. The case does not establish independent effects of crew capacity versus stock size, resource shortage, procurement, reorder, other task categories or levels, generic POINT selection, GUI visual behavior or cross-engine parity. Issue #18 remains open.
