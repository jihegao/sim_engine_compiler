# I02.var03 bounded CLI signoff — scheduled BETWEEN transfer

**Accepted scope:** One zero-duration, one-unit transfer of `TEACH-LRU-01`
from `DEPOT-01` to `BASE-01` at hour 6 after the accepted I02.var01 IN at
hour 4. The direct accepted parent source SHA-256 is
`85ee84d85e610f753215882fca59cc3331a9ce0f3313ae635f2a7422e8abcf4d`.
The child adds only this BETWEEN `ItemTransfer` row and changes the
description, leaving 30 other tables unchanged. Its frozen source SHA-256 is
`4842382bd3728f7f9520d3b20e1ad7148f7436f5132e9cc933773550d64b4560`;
exact-diff SHA-256 is
`3d037c2c54388760d4e58e5a88762567a1d4a5ff4a484587c70987a8336b72ae`.

The guarded session-0 SSH native run
`i02-var03-between-v100-ssh-20261002-01` preserved GUI PID 13340,
completed all five steps, converted with zero errors and one expected
simulation-log warning, and round-tripped all 22 populated authored tables.
The physical log shows IN adding item ID 1 to depot at h4, then one BETWEEN
task taking pre-existing ID 0 from depot and delivering that same item to
base at h6. Depot physical stock falls two→one and base stock rises zero→one.
Two report-only runs from the same sealed SXO used separately pinned depot and
base selectors. Their native `ItemResults` tables have 72 half-hour bins per
station: depot nominal `STSZ` and on-hand `STOHA` change 1→2 at h4 and 2→1
at h6; base changes 0→1 at h6. Two-station nominal stock remains two after
the earlier IN. These are station stock positions, not mounted item counts.

At h10, ordinary aircraft demand consumes base ID 0 and the system is ready
at h10.5. Depot ID 1 departs for base replenishment and arrives h12; failed
mounted ID 2 is repaired at depot and returns to depot stock at h13.1667.
The two on-hand series record these distinct later movements. Independent
replay finds no aggregate external backorder in this child, whereas the
accepted IN parent has a base backorder h10–12; system readiness differs
during h10–12.5. Mission summary and lifecycles remain equal. `ItemResultsTotal`
values are horizon averages, not terminal stock.

Author read-only replay passed 28/28 checks. Independent replay passed
1338/1338 checks and returned bounded GO. Three closures seal 12 native raw
files and two raw files for each station-specific report, 16 total;
`evidence-index.json` records their local paths and SHA-256 values. Native
files and proprietary `.sxs` selectors stay local and ignored by Git.
`make_report_settings.py` recreates both selectors from the fingerprinted
installed default, and each report runner pins its selector bytes.

**Boundary:** This establishes one available-stock, zero-delay BETWEEN after
IN at two stations, with one LRU, one seed, and the installed CLI. It does not
establish standalone BETWEEN, nonzero delay, unavailable-stock split or
transfer backorder, priority, reorder-point change, procurement, GUI visual
behavior, or cross-engine parity. I02 and Issue #18 remain open.
