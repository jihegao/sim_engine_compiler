# Independent pre-run review — E15.var07 explicit ISTOH v1.0.2

**Decision: GO for one guarded above-nominal diagnostic.** No SIMLOX process was invoked by this review. The frozen positive gate is falsifiable: if the native converter, first demand, physical opening stock or selected 72-bin ItemResults ledger differs, this immutable run is excluded. A successful run would support only the tested explicit ISTOH5 opening-state boundary, not a general stock-cap or later reorder rule.

## Frozen lineage and source

- Current SHA-256: contract `746a1f54da4afab8ad7bd34a6f2aae65fb8c8e969ce14043a325192937a32b44`; runner `93444f2c12342cdd988f4fcdf4ec8fd2cf5554e0ace6d696f6dda14db4403004`; input `897fc56e248f71b0b2c6e2616d4be476b24d7564f76053768d3980e93ccc6a7e`; builder `841b4963014e22be3cf996a25e38e54a52a7b06e7e0737dd4f1c3e6f639e7547`; roundtrip checker `684279d087f82efb3921eb8eb6ad5e6839d6a51dd7851284a882dc6ed6e7558d`.
- All **13** literal runner SHA pins are exactly 64 hex characters and match current files, including accepted v1.0.1 input/signoff/evidence index/event log/selected report, selector and builder, installed executable and manual. The PowerShell parser reports zero errors; unique run ID `e15-var07-istoh-five-v102-ssh-20261005-01` is unoccupied.
- Independent table comparison finds exactly **one cell** changed from the accepted explicit-three source: `StockAllocation` row `AIR_BASIC / TEACH-DU-01 / DEPOT-01`, `ISTOH` integer 3→5. All 31 table structures and other data cells are equal, with 21 row-containing authored tables. STSIZ4, ROSIZ2, ItemReorder.LEADT1, TRACK, seed1, 36-hour horizon and selected report setting are unchanged.
- The installed manual physical pp445–447 permits explicit ISTOH above nominal STSIZ at a reorder position during the initial phase, says it defaults to STSIZ+AINST if omitted, and sets the stock-based minimum to STSIZ−ROSIZ (here 2). It distinguishes nominal STSZ from actual on-hand STOHA and limits the initial-stock choice to the initial period. Thus ISTOH5 with nominal4 is a supported, meaningful boundary.

## Guards and interpretation

The runner verifies SSH session0 and an `sshd.exe` ancestor, obtains the nonblocking host-wide mutex, pins GUI PID13340/session1/start time and active session, uses hidden CLI children and a target-identity-checked 60-second watchdog, and seals source hashes before/after and raw files. It checks exact 21-table import/export before calculation, then requires converter Errors0/Warnings1/Notes0 with sole #108, nonempty SXO/event log and selected ten-table report. These are adequate pre-run gates.

At the source level, opening depot stock five is one above nominal four. One inherited h10 depot issue would leave four, above reorder point two, so no h0/h10 order is predicted. The contract appropriately demands physical item identities and all 72 selected depot bins rather than inferring success from the input cell. Extra opening items can shift physical IDs or stochastic consumption; the contract's inherited h10 timing and stock ledger must be tested against raw native evidence. No wider value range, later replenishment, GUI-only behavior or cross-engine claim is preapproved.
