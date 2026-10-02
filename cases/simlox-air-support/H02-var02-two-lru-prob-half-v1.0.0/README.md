# H02.var02 two directly mounted LRUs with per-item damage consequence

This bounded cohort starts from the accepted [H02.var01 primary-LRU damage source](../H02-var01-primary-lru-damage-v1.0.0/README.md). It changes the directly mounted `TEACH-LRU-01` quantity to two and local spare stock to two. The control sets `DamageItem.PROB=0`, retaining three fixed `BATTLE-HIT` system damage opportunities with no item consequence. Eight children set `PROB=0.5` and use preselected seeds 1–8. `DAMP=1`, `REPF=1`, damage replacement, one-hour item direct repair, mission schedule and horizon36 remain fixed. The [contract](contract.json), [exact diff](exact-diff.json), and [quantity-two reference](../G01-var05-qty-two-v1.0.0/README.md) pin lineage and model settings. Installed SIMLOX manual physical p425 says this probability applies to each individual mounted copy when `QTYPM>1`.

Nine fresh serial session-0 SSH native runs held `Global\SimloxIssue18NativeQueue` and preserved GUI PID13340. Every input completed import, export, calculation, JSON report and exact 24-table authored-row roundtrip. Native conversion reported zero errors, with inherited warnings #108 and #2053. Each closure seals 12 raw artifacts by SHA-256. Local raw runs are ignored by Git and bound in the [evidence index](evidence-index.json).

| Arm | Damaged physical LRU IDs in the three mission damage events | Aborts | Successes |
|---|---|---:|---:|
| Control | none / none / none | 0 | 3 |
| Seed 1 | 2,3 / 4,5 / 6 | 3 | 0 |
| Seed 2 | 2 / 3,4 / none | 2 | 1 |
| Seed 3 | 2 / 3 / 4 | 3 | 0 |
| Seed 4 | 2,3 / none / 4,5 | 2 | 1 |
| Seed 5 | 2 / 3 / 4 | 3 | 0 |
| Seed 6 | 2 / 3,4 / none | 2 | 1 |
| Seed 7 | 2,3 / 4 / 5 | 3 | 0 |
| Seed 8 | none / 2,3 / 4 | 2 | 1 |

Across the 24 seeded damage events, 4 produce zero, 12 one, and 8 two damaged mounted LRUs. The 28 damaged physical items each have a local spare issue, removal, one-hour direct repair and stock return. Events with no item consequence allow mission completion; events with one or two item consequences abort that mission and trigger half-hour damage replacement. Two replacement tasks at the same event execute in parallel, so `NREPT`, `NDD` and `NWT` count items while `NSYRP` measures one half-hour aircraft repair occupancy. Each report has 72 aligned half-hour System and Stock bins, no backorder or attrition, and terminal ready1. The [author replay](validate_native.py) and an independent read-only replay under `review/` verify sources, raw seals, event identities, stock flow and report ledgers.

The eight seeds were selected before running. Their deterministic outcomes demonstrate zero, one and two physical consequences in this configuration. They do not estimate a population probability or prove statistical independence. Other item types, nested structures, stations, shortages, GUI visual behavior and cross-engine parity remain outside this slice. Issue #18 remains open.
