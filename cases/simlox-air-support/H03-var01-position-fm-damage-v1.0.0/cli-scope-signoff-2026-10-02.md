# H03.var01 position failure-mode damage native CLI scope sign-off — 2026-10-02

**Decision:** Accept the one-position-FM `BATTLE-HIT` consequence and half-hour direct-CM route relative to its `PROB=0` control. Publish this bounded H03.var01 slice while Issue #18 remains open.

## Frozen lineage and execution

- Accepted D06 direct parent SHA-256 `ee7484a32492d1aa6cd90ad961620ecdd3de1244f09b16ba4a96a2978310ce78`; accepted H02 damage-table reference SHA-256 `82564db9cd0d3f916a87264d16d390a42bf886f5748c843070bea20e6b1c4a92`. Contract SHA-256 `6500075ab63b9e946fa45acee137ff91c3c51b13551e518759551cff948a8368`; exact diff SHA-256 `fecafd871994f7215dc11905befd3be7f1512f0326d4cafc6e3e601034e13cf2`.
- Parent-to-control adds only `DamageType`, `MissionDamage` and `DamageFailureMode`, changes ordinary `FM-POS-A.FRQ` from 300000 to positive `1e-9`, and updates description. Control-to-child changes only `DamageFailureMode.PROB` from 0 to 1 and description. The accepted `POS-A` FM and `BASE-01` `CMLocation.CMT=0.5` route remain. Installed manual physical pp192–193/424–425 and dictionary support the keys and route; pre-run independent static review gave conditional GO.
- Two fresh serial session-0 SSH runs held the host mutex and preserved GUI PID13340/session1. Each completed five native/check steps, exact 21/21 authored-table roundtrip, zero converter errors, and 12 SHA-256 sealed raw artifacts. Warning #108 is the only converter warning in each. Author replay passes 26/26 checks; independent read-only replay passes 2,087/2,087 checks.

## Observation and boundary

Both arms have three in-flight BATTLE-HIT events and three launched missions. Control `PROB=0` yields no FM consequence, no CM work, three successful missions and terminal ready1. Child `PROB=1` logs `FM-POS-A` on `<POS-A,0>` three times, aborts the missions, completes system CM tasks 0/1/2 in half an hour each, and returns ready after each. Each report contains 72 aligned System and Stock bins; `NDAM=3`, ordinary `NFAIL=0`, no stock demand or backorder, and terminal ready1. Child CM repair exposure is 1.5 aircraft-hours; control is zero. Raw artifacts remain local and are bound by path/hash in `evidence-index.json`.

An earlier mixed traditional-LRU/system-owned-FM diagnostic remains unpublished: it logged both consequences but warning #242 and no CM task, with later mission cancellation. The cause is unresolved; this acceptance does not cover simultaneous item/FM consequence or directly system-owned FM repair. One seed and position FM cannot establish stochastic frequency, other material paths, GUI visual behavior or cross-engine parity.
