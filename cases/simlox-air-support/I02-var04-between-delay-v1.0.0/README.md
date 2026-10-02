# I02.var04 — positive BETWEEN transfer duration

This bounded case extends accepted I02.var03. The parent has an hour-4 IN of
one LRU to `DEPOT-01` and an hour-6 BETWEEN transfer of one available LRU
from depot to `BASE-01` with `TFDT=0`. This child changes only that transfer's
`TFDT` to 2 hours and the description; 30 other tables remain unchanged.
The direct parent source, frozen child, and exact delta are SHA-256 pinned.

`build.py` and `describe_diff.py` reproduce the source and exact delta.
`check_roundtrip.py` checks all 22 populated authored tables after native
import/export. `run_native_ssh.ps1` uses the protected session-0 SSH queue and
preserves GUI PID 13340. `make_report_settings.py` recreates local proprietary
depot and base selectors from a fingerprinted installed default. The two
report-only runners export native `ItemResults` from the same sealed SXO
without recalculating. Raw native files and selectors stay local and ignored
by Git; their SHA-256 seals are recorded in `evidence-index.json`.

The native physical log shows item ID 0 leaving depot at h6 and arriving at
base at h8. In 72 half-hour `ItemResults` bins per station, depot nominal
`STSZ` and on-hand `STOHA` fall 2→1 at h6, while base nominal and on-hand
rise 0→1 at h8. The sum of those two *station positions* is one during
h6–8 while the item is in transit; it is two after the earlier IN outside
that interval. This is not loss of a physical item. Against the accepted
zero-delay parent, only four base `ItemResults` bins (h6–8) differ in
`STSZ`/`STOHA`; the depot report is unchanged apart from description.

Later ordinary aircraft demand at h10 consumes base ID 0. Depot ID 1
replenishes base at h12, and failed mounted ID 2 is repaired and returned
to depot at h13.1667. The two station ledgers and physical log distinguish
these events from the scheduled transfer. Native `SystemResults`,
`StockTotalResults`, mission results, and `ResultSummary` match the
zero-delay parent. Base `ItemResultsTotal` horizon-average `STSZ` and
`STOHA` each fall by 2/36.

This establishes one available-stock, two-hour BETWEEN after IN, at one seed,
one LRU, and two stations. It does not establish other durations, delayed
IN/OUT, unavailable-stock splitting or backorders, priority, reorder,
procurement, GUI visual behavior, or cross-engine parity.
