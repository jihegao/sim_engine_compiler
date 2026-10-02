# I01.var01 stock-only two-POINT APID native CLI scope sign-off — 2026-10-02

**Decision:** Accept the observed `Control.APID` selection of two `StockAllocation.POINT` rows in the bounded E01 model. Publish stock-only I01.var01 while Issue #18 remains open.

## Frozen lineage and execution

- Accepted E01 direct parent SHA-256 `84ca1828f3669d2c91c9d826cae3187e0968ae9f8fed602d97155d2e82e99931`. Stocked source SHA-256 `9e88c4bb95e1ca1ad4ec255c0fb9996fcbab8cd80b61972771574eb416233bfb`; empty source `e12e73daf6ca0820ff2b513fc241a7d9cb8721ed3812dad1fc78d315974baf55`. Exact diff SHA-256 `58bfd2a35a80c841176d7ab55804bdf1e176812360abb107041da626a14bd0bc`; contract SHA-256 `b697f25a2e88efbdb501ea4df7bb3ebb585e84403c9b1d3e36218b565b08386f`.
- Parent-to-control adds only the `AIR_EMPTY` stock row with `STSIZ=0` and updates description. Control-to-child changes only `Control.APID` from `AIR_BASIC` to `AIR_EMPTY` and updates description. Both retain `AIR_BASIC` stock1, `AIR_EMPTY` stock0, the E01 failure/replacement/item-repair model, fixed mission schedule and seed. Installed manual physical pp439–445 and dictionary support APID/POINT and stock key semantics. Independent pre-run static review gave GO after a runner success-gate repair made nonzero calc, converter errors, invalid SXO and report failure fatal before execution.
- Two fresh serial session-0 SSH runs held the host mutex and preserved GUI PID13340/session1. Both complete five native/check steps, exact 20/20 authored-table roundtrip, zero converter errors, warning #108 only and 12 sealed raw artifacts. Author replay passes 30/30 checks; independent read-only replay passes 7,604/7,604 assertions and is recorded under `review/`.

## Observation and boundary

The stocked arm starts with one local spare and takes it at h10 after the same h9.8829 critical LRU failure; its half-hour system replacement ends at h10.5. The empty arm starts with zero stock, opens a backorder at h10, waits during FIT until the failed LRU's one-hour direct repair returns it at h11.1667, then ends replacement and restores ready at h11.5. The stocked native event log and ResultSummary/SystemResults/StockTotalResults rows match accepted E01. Both later missions succeed and both end ready1. The 72-bin Stock ledger integrates empty-arm backorder occupancy to 1.16667 hours with no stocked-arm backorder; the empty System ledger also has one hour of item wait (`NSYWI`). Both System reports contain one ordinary failure, half an hour of active system repair and no loss.

Only stock POINT selection is accepted. ResourceAllocation and MaintenanceAllocation are not populated in this pair; their APID relationship, task category/level filtering, APID blank, STID=`<NONE>`, StationVariant, procurement, GUI visual behavior and cross-engine parity remain unverified.
