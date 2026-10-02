# H02.var03 intermediate damaged-LRU repair fraction

Eight preselected seeds 1–8 use the accepted [H02.var03 REPF endpoint source](../H02-var03-repf-zero-v1.0.0/README.md). Every child sets `DamageItem.REPF=0.5` for a directly mounted LRU. Seed 1 changes only REPF and the description; seeds 2–8 also set `Control.RSEED` to the named seed. The model keeps one aircraft, one local spare, certain in-flight BATTLE-HIT damage, explicit DamageReplacement, ordinary one-hour ItemRepair, three fixed missions and horizon36. The [contract](contract.json) and [exact diff](exact-diff.json) freeze all eight inputs before this batch.

All eight fresh guarded session-0 SSH runs convert with zero errors, exactly roundtrip 24 authored row-containing tables, preserve GUI PID13340 and produce 72 aligned half-hour System and Stock bins. The item log records 23 damage decisions across the set: 14 damaged LRUs complete direct repair and 9 are discarded. These are observed counts from selected deterministic seeds, not a measured repair probability.

| Seed | Damaged LRU IDs repaired | Discarded IDs | Spare issues | Backorder path | Terminal aircraft |
| --- | --- | --- | --- | --- | --- |
| 1 | — | 1, 2 | 0 | one remains open; third mission cancels | unready |
| 2 | 1, 2, 3 | — | 0, 1, 2 | none | ready |
| 3 | 2 | 1, 3 | 0 | repaired ID 2 clears first backorder; another remains open | unready |
| 4 | 1, 2, 3 | — | 0, 1, 2 | none | ready |
| 5 | 2 | 1, 3 | 0 | repaired ID 2 clears first backorder; another remains open | unready |
| 6 | 1, 2, 3 | — | 0, 1, 2 | none | ready |
| 7 | 1, 3 | 2 | 0, 1 | repaired ID 3 clears backorder | ready |
| 8 | 2 | 1, 3 | 0 | repaired ID 2 clears first backorder; another remains open | unready |

Seed 7 directly observes both paths under the same half-value input: damaged LRU1 repairs and returns to stock, damaged LRU2 is discarded, and damaged LRU3 repairs and satisfies the later backorder. A repair routed directly to a waiting demand is logged as `Backorder removed`, without a separate `Put back replacement item` entry. This distinction matters for seeds 3, 5, 7 and 8. System `NDAM/NREPT`, Stock `NDD/NWT/NBO/PNB`, mission events and terminal readiness reconcile in the 103-check [author replay](author-validation.json) and 30,723-check independent [read-only review](review/independent-readonly-2026-10-02.json). The [evidence index](evidence-index.json) binds all source and raw hashes; bulky raw runs remain local and ignored by Git.

Four earlier seed1–4 `-01` attempts are preserved as excluded diagnostics. A copied checker contained a Python syntax error; import, export, calculation and report steps ran, but the checker failed, so those closures are not accepted. The corrected checker and runner were independently reviewed before the complete eight-run `-02` set. A separate prior seed1 half-value diagnostic yielded the discard path and is disclosed in the contract; it is not counted as an additional independent seed.

This small, preselected seed set demonstrates repair and discard realizations for this model. Its seeds were chosen after the disclosed seed1 diagnostic; the 14/23 observation does not estimate a 50% frequency or establish independent draws. Other LRU structures, stations, damage consequences, repair-data fallback priority, GUI visual behavior and cross-engine parity remain unverified.
