# I02.var02 bounded CLI signoff — scheduled OUT transfer

**Accepted scope:** One zero-duration, one-unit OUT transfer from `DEPOT-01`
to `<OUTSIDE>` at hour 6 after the accepted I02.var01 one-unit IN at hour 4.
The direct accepted parent source SHA-256 is
`85ee84d85e610f753215882fca59cc3331a9ce0f3313ae635f2a7422e8abcf4d`.
The child adds only the OUT `ItemTransfer` row and changes the description;
30 other tables remain unchanged. Its frozen source SHA-256 is
`7b15a1e0a6efcee9c772ac39dd52bb742a6eb23b6b711cf8e3cbc681aabe07e0`,
and exact-diff SHA-256 is
`affbb2846318c225c1d8d7a092c12c295ddcf9d65eeb1a4915cef382ab7f4135`.

The guarded session-0 SSH native run
`i02-var02-out-v100-ssh-20261002-01` preserved GUI PID 13340, completed all
five steps, converted with zero errors and one expected simulation-log warning,
and round-tripped all 22 populated authored tables. The physical log shows
the h4 IN stocking item ID 1 alongside pre-existing ID 0; at h6 one OUT task
takes ID 0 from the depot and completes. Depot physical stock falls from two
to one, retaining ID 1. The report-only run
`i02-var02-item-results-v100-ssh-20261002-01` used the sealed SXO and pinned
local report selector without recalculation. Its native `ItemResults` depot
position has 72 half-hour rows: nominal `STSZ` and on-hand `STOHA` are one
before h4, two h4–h6, and one from h6 until later ordinary demand affects
on-hand stock. This is a depot item-stock position, not a mounted aircraft
count.

At h10 ordinary demand issues remaining ID 1, lowering depot on-hand to zero
while nominal stock stays one. ID 1 reaches the base at h12 and clears the
base backorder. Failed mounted ID 2 reaches depot for repair and returns to
depot stock at h13.1667, restoring on-hand to one. Later mission and system
outcomes match the sealed accepted IN parent, as the independent replay
checks. `ItemResultsTotal` numbers are 36-hour averages, not terminal stock.

Author read-only replay passed 20/20 checks. Independent replay passed
1022/1022 checks and returned bounded GO. The two closures seal 12 native raw
files and two report-only raw files; `evidence-index.json` records their local
paths and SHA-256 values. Native files and the proprietary `.sxs` stay local
and ignored by Git. `make_report_settings.py` recreates the selector from a
fingerprinted installed default; the report-only runner pins the exact bytes.

**Boundary:** This establishes one available-stock OUT transfer in an
IN-then-OUT sequence, with one LRU, one depot, `TFDT=0`, one seed, and the
installed CLI. It does not establish a standalone OUT-only scenario,
unavailable-stock split or transfer backorder, BETWEEN, nonzero delay,
priority, reorder-point change, procurement, GUI visual behavior, or
cross-engine parity. I02 and Issue #18 remain open.
