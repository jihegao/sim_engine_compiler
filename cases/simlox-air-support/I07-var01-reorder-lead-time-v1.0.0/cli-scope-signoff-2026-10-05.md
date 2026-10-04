# I07.var01 CLI scope signoff — 2026-10-05

**Candidate scope:** a scheduled `ChangesItemReorder.LEADT` update at h5, from one hour to three, on the existing E15 `TEACH-DU-01`/`DEPOT-01` stock-based reorder. This accepts one bounded I07.var01 slice, subject to independent replay; the full ChangesItemReorder feature remains unverified.

The guarded session-0 SSH run `i07-var01-reorder-leadt-v100-ssh-20261005-01` completed 8/8 import, export, calculate and selected-report steps. Each arm had converter errors zero, reviewed warning 108, and notes zero. All 22 row-containing authored tables per arm, including the all-null control change row, exactly match native export by columns, datatypes and rows. The closure seals 22 local raw files and unchanged source hashes, with protected GUI identity preserved around every native child.

The same h10 demand starts one two-unit reorder in each arm. Control's reorder lasts one hour and is delivered at h11; change lasts three hours and is delivered at h13. Selected 72 half-hour `ItemResults` bins at the depot show initial on-hand three, on-hand two until the respective delivery, and four afterward. `NRO` marks one reorder. Both arms retain the first mission abort at h9.8829 and later successful h20 and h32 missions. Author replay passes 94/94 checks. Publication requires independent replay to pass.

The `ChangesItemReorder` change event is established by the frozen source row and observed later-order duration, not by a separate change announcement in the native log. Raw native bytes stay in ignored local `runs/` and their hashes are published in `evidence-index.json`.

**Limits:** one seed, one existing ItemReorder, LEADT only, change before a stock-based reorder. No outstanding-order retention, interval policy, `LEADTD`, tie-time change, other Changes tables, GUI, cross-engine or full Issue #18 claim.
