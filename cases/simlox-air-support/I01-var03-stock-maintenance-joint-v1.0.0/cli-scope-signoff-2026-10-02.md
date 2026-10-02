# I01.var03 bounded CLI signoff — joint stock and maintenance POINT selection

Status: accepted for the bounded joint stock/maintenance scope below, subject to PR review and merge. Issue #18 remains open.

## Frozen source and experiment

- Direct accepted parent: I01.var03 maintenance station base input SHA-256 `4e16325638ff7aafcf47306101b42a780c02b06f957c0036317e300eb63abf72`, merged in PR #254. E04 FAST is an indirect station-transport donor.
- Four frozen input SHA-256 hashes: one-base `96dd5cb98a9e5847fc7ae0d4236d6214dbe1825fe5c89c9e87ad3c951621b049`; one-depot `9e4f082d8e8bb9dc00a0d45e3b1dba6045bd1cc64ffe822d855c539285b12589`; two-base `c33af33250be2eae5054a80d25ef73461c2deba927924cffd135fd5f396b9b19`; two-depot `24500b239791936a7adc7ff0e83c674da8e813f19ec76ba9dc1cfde90391f763`. Exact diff SHA-256 `d5b7d14d8d169acbce8f871d451b7d33b610d8d7d8531d1391cb3be46ef05c81`; pre-run contract SHA-256 `b25e451482e46111333616ce66977c33693cf1acbee1cfdae2c2b6e1d2d560fe`.
- All four inputs contain the same four complete POINT groups in StockAllocation and MaintenanceAllocation. BASE stock STSIZ1 or2 crosses BASE/DEPOT repair for task-referenced `LRU-CM/BASE` ItemRepair. They differ only in Control.APID and description. Task, repair duration, transport, missions, seed and horizon are fixed. No ResourceAllocation or ItemReorder business rows are authored.
- Installed manual physical pp. 338–339 and 439–445 and table dictionary support the selected POINT groups and task match. Installed executable, manual and dictionary hashes are pinned in the contract.

## Native evidence

- Four fresh serial guarded session-0 SSH runs used `Global\SimloxIssue18NativeQueue` and preserved GUI PID13340. Each source-stable closure has no error, all 24 row-containing authored tables round-trip exactly, converter errors are zero (warning #108/notice #2034 only), SXO/report output is valid, and 12 raw files are SHA-256 sealed. Total local raw seals: 48; raw artifacts are ignored by Git.
- First physical LRU failure h9.8829, spare ID0 issue h10, aircraft ready h10.5, two later mission successes and terminal ready1 occur in every arm. One-spare arms initialize BASE stock level1 and fail installed item ID1; two-spare arms initialize level2 and fail installed ID2. BASE arms repair the failed physical item h10.1667–11.1667 and return it immediately. DEPOT arms transfer it two hours, repair h12.1667–13.1667, return it over two hours and restore BASE stock h15.1667. Physical stock events balance initial, issue and return to level1 or2. All 72 SystemResults and StockTotalResults bins and business summaries reconcile across four arms. The aggregate stock report does not expose on-hand quantity; the sealed physical log establishes the size difference.
- Author replay: 45/45 checks, SHA-256 `d1751d4ffd522f28fb10e2f4884cb940240c3afe8be2c205682563df2ef5c848`. Separate independent read-only replay: 1,747/1,747 checks, checker SHA-256 `9171f9ad5ee6521b2774addc33918f13f3aefa891e111ed60bfad0d113738099`, verdict SHA-256 `5a9ac04aae7302ef6c121928d942e46614132a4aaf359bd620a4ab0a23887edd`. One-spare physical logs are byte-identical to corresponding accepted station parent logs; all four arms' System/Stock report bins and summary equal the corresponding accepted parent.

## Scope and limits

This accepts only joint StockAllocation stock-size and MaintenanceAllocation repair-station selection by APID for one task-referenced LRU, two BASE stock levels, two stations and one seed. It does not establish ResourceAllocation selection in the same model, procurement, reorder, stock shortage, category/level interaction, generic POINT behavior, GUI visual behavior or cross-engine parity.
