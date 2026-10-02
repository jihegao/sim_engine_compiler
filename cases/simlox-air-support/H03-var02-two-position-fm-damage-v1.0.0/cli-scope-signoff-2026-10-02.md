# H03.var02 two position-FM damage native CLI scope sign-off — 2026-10-02

**Decision:** Accept the observed two-mode `BATTLE-HIT` consequence on one physical `POS-A` and concurrent direct-CM route relative to the accepted one-mode control. Publish this bounded H03.var02 slice while Issue #18 remains open.

## Frozen lineage and execution

- Accepted H03.var01 direct parent and byte-identical control SHA-256 `5297d5224b3a2086c26c663aa92cd51be7c349a24f7957428f47c21fcdc4ee7c`; child SHA-256 `05a211fb310e7fce75de3212cb5c4e7c2d73e3f9cefab0b60a02ad5225f72d2e`. Contract SHA-256 `82c941aff7e5cc2e80ea5c41886296eae7850b1294c2fbb2a9c64a950ee3900a`; exact diff SHA-256 `672e6f55626f8bb6c26c28f4e16e27eba041e63277b4010f102abb3f06454c8b`.
- Child adds only `FM-POS-B` with positive ordinary `FRQ=1e-9` on `POS-A`, `BASE-01` `CMLocation.CMT=1.0`, and `BATTLE-HIT` `DamageFailureMode.PROB=1` for that mode, plus description. The existing `FM-POS-A` and half-hour CM row remain. The installed manual physical p193 permits multiple damage failure modes on a material item; pp424–425 and dictionary define the keys. Independent pre-run static review gave conditional GO.
- Two fresh serial session-0 SSH runs held the host mutex and preserved GUI PID13340/session1. Each completed five native/check steps, exact 21/21 authored-table roundtrip, zero converter errors, warning #108 only, and 12 sealed raw artifacts. Author replay passes 28/28 checks and independent read-only replay passes 6,631/6,631 checks. The independent verdict and checker are recorded under `review/`.

## Observation and boundary

Both arms have three launched missions and three in-flight `BATTLE-HIT` occurrences. The control yields one `FM-POS-A` consequence and a half-hour direct CM per event. The child yields two modes on physical `<POS-A,0>` and two simultaneous CM starts per event; the first task ends after 0.5 hour, leaves `FM-POS-B` and a partial repair, and the second ends after one hour with ready state restored. All six child CM tasks complete and all three missions abort in each arm. Each report has 72 aligned System and Stock bins, `NDAM=3`, ordinary `NFAIL=0`, no stock demand/backorder and terminal ready1. System repair occupancy integrates 1.5 versus 3.0 aircraft-hours for control and child; the child task durations overlap.

This is a fixed-seed, one-position observation. It does not prove probability independence or cover multiple material positions, item-plus-FM consequences, shortage, other stations, GUI visual behavior or cross-engine parity. A separate H03.var01 mixed traditional-LRU/system-owned-FM diagnostic remains unpublished and unresolved.
