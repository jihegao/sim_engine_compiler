# I01.var02 blank APID stock-only native CLI scope sign-off — 2026-10-02

**Decision:** Accept a stock-only blank-APID observation in the bounded I01.var01 model. Keep Issue #18 open.

## Frozen lineage and execution

- Accepted I01.var01 stocked source is the byte-identical selected control, SHA-256 `9e88c4bb95e1ca1ad4ec255c0fb9996fcbab8cd80b61972771574eb416233bfb`. Blank child source SHA-256 `fc351e8b0a54c66eefa65055b7aea21a6ceef8539ce3c2960da30fd845376a01`. The exact diff SHA-256 is `123c556b7017f75778d04a8d4308e81cec63c4d4f8f759695cb877f685fb1b02`; the pre-run contract SHA-256 is `00c1065b397a9936323d012471b433b468fc6ac0d54eeb1e232eb5257928237a`.
- Only Control.APID `AIR_BASIC`→blank/null and ProblemDescription change. Both sources retain two stock POINT rows, one aircraft, one ordinary critical LRU failure, explicit system replacement, direct item repair, seed1, three missions and horizon36. ResourceAllocation remains empty and MaintenanceAllocation absent. The manual's blank-APID no-filter wording concerns maintenance policy; this case observes stock behavior separately. An independent pre-run static review gave GO for diagnostic native execution.
- Two fresh serial session-0 SSH runs held the host mutex and preserved GUI PID13340/session1. Each completed five native/check steps, exact 20/20 authored-table roundtrip, zero converter errors, valid native output and 12 sealed raw artifacts. Author replay passes 34/34 checks; independent read-only replay passes 7,582/7,582 assertions and is recorded under `review/`.

## Observation and boundary

The blank arm's converter emits notice #102, “Simulation with no stock.” Its native event log is byte-identical to accepted I01.var01 AIR_EMPTY, and its ResultSummary, SystemResults and StockTotalResults rows also match. The selected control is byte-identical to accepted I01.var01 AIR_BASIC in both event log and full native report. The shared h9.8829 critical LRU failure aborts mission 1. Selected APID takes a local spare h10 and restores ready h10.5. Blank APID backorders h10, reuses the failed LRU when its direct repair ends h11.1667, and restores ready h11.5. Later missions succeed, both terminal systems are ready1. Across 72 half-hour bins, blank has one hour of SystemResults.NSYWI and 1.16667 StockTotalResults.NBO backorder-hours, versus zero for selected; both have 0.5 active system-repair hours.

Only stock behavior for a blank APID with these two POINT rows is accepted. ResourceAllocation/MaintenanceAllocation blank selection, task category/level filtering, STID=`<NONE>`, StationVariant, procurement, GUI visual behavior and cross-engine parity remain unverified. No universal claim about all blank-APID models follows from this seed and one station.
