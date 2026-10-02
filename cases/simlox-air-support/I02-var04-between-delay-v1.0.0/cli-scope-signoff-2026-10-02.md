# I02.var04 bounded CLI signoff — positive BETWEEN duration

**Accepted scope:** One available-stock, one-unit `TEACH-LRU-01` transfer
from `DEPOT-01` to `BASE-01`, scheduled at h6 after the accepted h4 IN. The
direct accepted I02.var03 parent has `TFDT=0`; this child changes that one
cell to `TFDT=2.0` and the description, leaving 30 other tables unchanged.
Parent source SHA-256 is
`4842382bd3728f7f9520d3b20e1ad7148f7436f5132e9cc933773550d64b4560`;
child source SHA-256 is
`607b5d5bc9d3c850b533b4bc50e202e6719c23182b47038fdf056222bfce2f39`;
exact-diff SHA-256 is
`04b0e304c0a2ecddb05b2d3f623faf499e972fc5fbc1ce05937c8fd5bbc62700`.

Guarded session-0 SSH native run `i02-var04-delay2-v100-ssh-20261002-01`
preserved GUI PID 13340, completed all five steps, converted with zero errors
and one expected simulation-log warning, and round-tripped all 22 populated
authored tables. The physical log shows item ID 0 leaving depot at h6 and
arriving base at h8. Two report-only exports from the same sealed SXO use
separately pinned depot and base selectors. Each native `ItemResults` table
has 72 half-hour bins. Depot `STSZ`/`STOHA` fall 2→1 at h6; base rises 0→1
at h8. The h6–8 sum of station nominal positions is one while the item is
physically in transit. The zero-delay parent places it at base at h6. Four
base bins change; depot bins, selected `SystemResults` and mission reports
remain equal. Base horizon-average `STSZ` and `STOHA` each fall by 2/36.

At h10, ordinary aircraft demand consumes base ID 0; depot ID 1 replenishes
base at h12, and failed mounted ID 2 returns to depot after repair at
h13.1667. These later events are distinct from the scheduled transfer.
Author read-only replay passed 32/32 checks. Independent read-only replay
passed 1492/1492 checks and returned bounded GO. Three closures seal 12 native
raw files and two raw files for each station-specific report, 16 total.
Native files and proprietary `.sxs` selectors remain local and ignored by
Git. `evidence-index.json` records their local paths and SHA-256 values.

**Boundary:** This establishes `TFDT=2` versus accepted `TFDT=0` for one
available-stock BETWEEN after IN at two stations, one LRU, one seed, and the
installed CLI. It does not establish other TFDT values, delayed IN/OUT,
shortage splitting or transfer backorders, priority, reorder, procurement,
GUI visual behavior, or cross-engine parity. I02 and Issue #18 remain open.
