# I01.var03 maintenance station selection — bounded native case

This package tests `Control.APID` selection of the repair station for a task-referenced failed LRU. The accepted direct parent is the I01.var01 stocked input, SHA-256 `9e88c4bb95e1ca1ad4ec255c0fb9996fcbab8cd80b61972771574eb416233bfb`. The accepted E04 FAST case contributes only the DEPOT-01 workstation and the two-hour BASE-01 → DEPOT-01 support link. The installed SIMLOX manual, physical pp. 338–339 and 439–441, defines the task category/level and station match for an active `ItemRepair` row.

The common model has one failed LRU repair task `I01-LRU-DIRP` of `LRU-CM/BASE`, one-hour direct repair rows at both BASE-01 and DEPOT-01, and equal stock under both POINTs (BASE spare 1, DEPOT spare 0). `MaintenanceAllocation` maps `AIR_BASIC` to BASE-01 and `AIR_DEPOT` to DEPOT-01 for that same category and level. The two inputs differ only in `Control.APID` and description. No authored ItemReorder or ResourceAllocation rows exist. The source/contract/diff fingerprints are frozen before the native runs in `contract.json`.

## Native observation

Two serial session-0 SSH runs used the host-wide `Global\SimloxIssue18NativeQueue` mutex and preserved GUI PID13340. Both imported and exported all 24 row-containing authored tables exactly, converted with zero errors (one expected warning #108 and notice #2034), produced valid SXO and JSON reports, and sealed 12 raw files each under ignored `runs/` paths.

In both runs, aircraft `TEACH-AIR-01` suffers the same failed physical LRU ID1 at h9.8829, aborts its mission, takes spare ID0 from BASE stock at h10, and returns to readiness at h10.5. In the BASE arm, failed ID1 undergoes direct repair at BASE h10.1667–11.1667 and restores BASE stock to one. In the DEPOT arm, ID1 departs BASE h10.1667, arrives DEPOT h12.1667, repairs there h12.1667–13.1667, returns in a second two-hour transport, and restores BASE stock to one at h15.1667. DEPOT records a temporary backorder h10.1667–13.1667. Both later missions succeed, and both have one ready aircraft at the terminal observation. The 72 half-hour SystemResults and StockTotalResults bins and summary are equal between arms; the physical event log distinguishes the repair route and stock-restoration time.

`validate.py` checks frozen lineage, all 24 local raw seals, two native closures, source-preserving roundtrips, conversion, physical-ID event sequence, stock balance, reports, and terminal state. A separate reviewer replays the evidence without importing this validator. `evidence-index.json` lists the local raw run IDs and SHA-256 hashes, without including proprietary or bulky raw artifacts in Git.

## Scope

The accepted claim is bounded APID repair-station selection for this one `LRU-CM/BASE` task. Routing and temporary stock effects follow from the selected station and are observed here. This pair does not independently test positive category or level filtering, simultaneous stock/resource/maintenance allocation selection, `<NONE>` reorder behavior, generic station routing, GUI visual behavior, or cross-engine parity. Issue #18 remains open.
