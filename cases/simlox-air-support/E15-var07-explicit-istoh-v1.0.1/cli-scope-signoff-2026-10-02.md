# E15 explicit initial on-hand stock: bounded CLI signoff

**Decision:** `native_behavior_accepted_cli_scope` for one stock-based reorder
contrast at a DU depot. It becomes `reusable_published` only after merge to
`simlox/main`. The frozen contract's `E15.var07` tag is a pre-run work label:
catalog E15.var07 asks for an explicit `ISTOH` **above** nominal `STSIZ`,
whereas this pair uses 3 below nominal 4. Therefore this publication does
**not** accept the catalog E15.var07 boundary. Full E15 and Issue #18 remain
open.

The accepted E02 catalog prerequisite input SHA-256 is
`12ef9bfd6ab88f7a796733bca0a283bfbf4e0be525eba02f3e98122212ac49dd`.
The direct accepted G01.var03 DU donor input SHA-256 is
`c409f4b210b9f60e5f36bf6b15f56aaba95f4b08b4f6b6de290b60d65086d7d9`.
Installed manual SHA-256 is
`39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`
(physical pp. 216, 218, 343, 345 and 445–447); dictionary SHA-256 is
`11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`.
The dictionary defines `Item.TRACK` as an item-result collection switch,
default `N`. The installed executable SHA-256 is
`fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`.

The two frozen inputs are SHA-256
`602dedfdb3491ab430abe4c68426c28203738fe1b2b1173d5d66955d00b6102e`
(default) and `bb57aecc7285d8eef5c71ba1b7f6b6f7dd9fb4cc46f3e6d88e863eb1da3f206f`
(explicit-three). Compared with G01, both set `Item.TRACK=Y`, depot
`StockAllocation.STSIZ=4` and `ROSIZ=2`; only the explicit arm sets depot
`ISTOH=3`. Descriptions differ. The other 28 tables are unchanged; between
arms the only behavioral input difference is depot `ISTOH`. The frozen
[contract](contract.json) SHA-256 is
`704e7951cfbfb7cab9274d4f5c723c065c0b2781c2244927686082e1f74208f4`;
the [exact diff](exact-diff.json) SHA-256 is
`db9dbaa3b986896c84d9634e414d1308d0a555dbccc0831fc8768d6d4d7dc3dc`.

Two serial guarded session-0 SSH native runs used the host-wide
`Global\SimloxIssue18NativeQueue` mutex and preserved active GUI PID 13340.
Import, export, calculation, default JSON report and checker exited zero in
each arm. All 21 authored populated tables round-tripped exactly. Conversion
reported zero errors and only expected logging warning #108. Both outputs
and reports are valid and nonempty. Main run closure SHA-256 values are
`f00b8fc07a4deb1db33b6142f0704e373a5db09197e8f6190fd0b22947e6feff`
(default) and `79e4729d44a4a3ed524ad9e0f0559c4d98c3aff64278bf553c3768f956c435e5`
(explicit-three). The pinned `TEACH-DU-01` / `DEPOT-01` selector produced
two further guarded report exports with closure SHA-256
`640e77479b0930137ca7f97e1f346babc9de7132ec33cd6f9ca400fb8295b249`
and `1bf91edb10034e912a49e1b810f7d5697f351a0eb50d51cefd8fa24bcdc9bbb8`.
The [evidence index](evidence-index.json) lists all 28 accepted local raw
hashes and the excluded diagnostic seals; raw files stay local under ignored
`runs/`.

At h0 depot on-hand is four by default and three with explicit `ISTOH=3`,
while nominal `STSZ` is four in both. The aircraft's installed DU fails at
h9.8829; h10 ordinary demand issues the local spare and depot DU physical
ID 0. After that issue the depot has three by default, above reorder point
`STSIZ−ROSIZ=2`, and no reorder occurs. The explicit arm reaches two and
starts exactly one two-unit reorder at h10. It completes after the configured
one-hour lead at h11, adding new physical DU IDs 5 and 6. The discarded
failed DU does not return to stock. The depot shipment of physical ID 0
reaches the base at h12 in both arms. The base is replenished, the aircraft
is ready at h10.5, the first mission aborts and the two later missions
succeed. The terminal aircraft is ready in both arms.

Selected depot `ItemResults` contains 72 half-hour bins per arm. `STSZ=4`
and ordinary `NBO=0` throughout. Default `STOHA` is 4 before h10 and 3
from h10 through h36; explicit `STOHA` is 3 before h10, 2 in the two bins
h10–11, then 4 from h11 through h36. `ItemResultsTotal.STOHA` is a
horizon average, approximately 3.27778 versus 3.66667, not a terminal
level. Its `NRO` is 0 versus 1. Selected System, Mission, aggregate Stock
and ResultSummary results agree between arms, with three missions started,
two successful and terminal readiness one.

[Author replay](author-validation-2026-10-02.json) passed **242/242** checks.
A separate [read-only reviewer](review/independent-readonly-2026-10-02.json)
replayed raw evidence without importing the author checker and passed
**1,598/1,598** checks. [Independent static review](review/independent-static-pre-run-2026-10-02.md)
approved both fresh native launches and selected report exports.

The v1.0.0 diagnostic pair had the expected event contrast, but its selected
report omitted `ItemResults` because `Item.TRACK` was unset. It failed that
predeclared evidence gate and is explicitly excluded; v1.0.1 made a fresh
source, contract and pair of native runs.

This acceptance covers one fixed seed, one DU, one base/depot pair, one
ordinary demand, `STSIZ=4`, `ROSIZ=2`, a fixed one-hour lead and a 36-hour
horizon. It does not establish the time-based reorder strategy, multiple
outstanding orders, random leads, initial stock at or below the reorder
point, explicit ISTOH above nominal as planned for catalog E15.var07, AINST,
planned-transfer procurement behavior, other stations/seeds,
GUI-only behavior or cross-engine equivalence. Full E15, I02, I07 and
Issue #18 remain open.
