# I01.var03 bounded CLI signoff — simultaneous three-allocation POINT selection

Status: accepted for the bounded scope below, subject to final staged audit, PR review and merge. Issue #18 remains open.

## Frozen source and experiment

- Direct accepted parent: I01.var03 joint stock/maintenance one-base input SHA-256 `96dd5cb98a9e5847fc7ae0d4236d6214dbe1825fe5c89c9e87ad3c951621b049`, merged in PR #257 at `4df9fa5a5fbfaf4415ccf96c24837854261fad70`. Accepted I01.var01 resource/preparation donor selected input SHA-256 `ac35a07731c629e16ba6bd83183eaca9c244161c2cc05a07cf7b2127cd52bbc5`. E04 FAST is an indirect station-transport donor.
- Four frozen input SHA-256 hashes: one-base `fd2fc5714d805cd6808e4da726e2a56b214022ec589593ec521240d974f1ae29`; one-depot `bc79c4efcbc8777c22e23c4ce941d961927360b5a14885c85a5424b3e531c6e8`; two-base `a6d10230e5440c643764c954715e28822a8ebed7c6dccdbb40ea131a6f84a5dd`; two-depot `78afc1450623bbd93cad4db36667587650ee52f5d76078442d3901411d2c1c58`. Exact diff SHA-256 `6122f02087643277e3a2d2a389b3985495b748005525c2d71c6982810cb8fdb3`; pre-run contract SHA-256 `4b4f5aa411afbb1d505af2642a5ae8617e6225e0a90b4e45c47a1a1b60523911`.
- All four inputs contain the same four complete POINT groups in StockAllocation, ResourceAllocation and MaintenanceAllocation. BASE stock size1 with P-CREW2 or stock size2 with P-CREW3 crosses BASE/DEPOT one-hour failed-LRU repair. Inputs differ only in Control.APID and description. Same active two-crew preparation, task, transport, missions, seed and horizon. No ItemReorder business rows. Installed manual physical pp. 338–339 and 439–445 and dictionary support the selection and task match; installed source hashes are pinned in the contract.

## Native evidence

- Four fresh serial guarded session-0 SSH runs used `Global\SimloxIssue18NativeQueue` and preserved GUI PID13340. Each source-stable closure has no error, all 29 row-containing authored tables round-trip exactly, converter errors are zero (warning #108/notice #2034 only), SXO/report output is valid, and 12 raw files are SHA-256 sealed. Total local raw seals: 48; raw artifacts are ignored by Git.
- Three active preparations at h7–7.5, h19–19.5 and h31–31.5 each lease and return two P-CREW for their first 10-minute subtask. All 72 ResourceResults bins show selected total capacity2 or3 and zero resource wait; first-bin `NRUM` during each preparation is about 0.6667 crew as the interval-average number in use.
- First ordinary LRU failure h9.8829, base spare ID0 issue h10 and aircraft ready h10.5 occur in all four arms. One-spare arms initialize BASE stock level1 and fail installed item ID1; two-spare arms initialize level2 and fail ID2. BASE arms repair h10.1667–11.1667; DEPOT arms transport outbound two hours, repair h12.1667–13.1667 and return/restock h15.1667. Physical stock initialization, issue and first return reconcile.
- Later outcomes diverge. BASE arms complete two later missions, report one failure and `MSUF` 2/3, and end with stock level1/2. DEPOT arms complete mission two, have a second ordinary LRU failure h33.9619 and abort mission three, report two failures and `MSUF` 1/3. They issue a second spare h34, return the aircraft to ready at h34.5, and send the second failed item outbound at h34.1667. It is still in transit at the h36 horizon; BASE stock ends at level0/1. All four arms end with one ready aircraft.
- Each SystemResults, StockTotalResults and ResourceResults report has 72 half-hour bins. System/Stock reports and summary are equal within station across stock/crew sizes; resource report is equal within capacity across stations. `StockTotalResults.NBO` remains zero although physical `model.log` records an open internal DEPOT repair backorder at the horizon. This aggregate does not show on-hand stock or replace physical item accounting.
- Author replay: 49/49 checks, validation SHA-256 `a273da624dc0db1dda8f5d3e28ab307f4528e51764d6ae275b24897dc4390fcb`.
- Separate independent read-only replay: 2,029/2,029 checks, checker SHA-256 `0c96e8db81cfa4c3bedde65db11396fa75b07e6fe07f65f154eeb8270ba5ec09`, GO verdict SHA-256 `55d93cbfdec1ebaec57a5e556b4d4a573c6ae57dbc87915ecc058c3f44dd4fd5`.

## Scope and limits

The candidate claim is simultaneous APID selection of these three allocation tables for one LRU, one preparation task, four POINTs and one seed. Crew capacity2/3 is correlated with spare size1/2 and does not isolate a separate resource effect. No resource shortage, procurement, reorder, other categories or levels, generic POINT selection, GUI visual behavior or cross-engine parity is established.
