# I02.var03 — scheduled BETWEEN transfer

This bounded case extends accepted I02.var01 IN. The parent adds one LRU to
`DEPOT-01` at hour 4, making depot stock two while `BASE-01` stock is zero.
The child adds one `ItemTransfer` row from depot to base at hour 6 with quantity
one and zero transfer duration. Its only other source change is the
description; 30 tables remain unchanged. Item tracking and half-hour result
collection are inherited from the parent.

`build.py` and `describe_diff.py` reproduce the source and exact delta.
`check_roundtrip.py` checks all 22 populated authored tables after native
import/export. `run_native_ssh.ps1` uses the protected session-0 SSH queue and
preserves GUI PID 13340. `make_report_settings.py` recreates local proprietary
selectors for both depot and base from a fingerprinted installed default.
The two report-only runners export `ItemResults` from the same sealed SXO
without recalculating. Raw native files and selectors are ignored by Git and
SHA-256 sealed in `evidence-index.json`.

The observed physical item ID 0 moves from depot to base at hour 6. In 72
half-hour `ItemResults` rows per station, depot nominal/on-hand stock changes
2→1 and base nominal/on-hand changes 0→1 at that hour. Across the two
stations, nominal stock remains two after the accepted hour-4 IN. At hour 10,
ordinary aircraft demand consumes base item ID 0 and depot sends item ID 1 to
replenish base. Failed item ID 2 is repaired at depot and returns to depot
stock. These later events have a separate physical and report ledger.

The accepted claim covers one available-stock, zero-delay BETWEEN after IN,
at one seed and two stations. It does not establish standalone BETWEEN,
nonzero delay, shortage splitting or transfer backorders, priority, reorder,
procurement, GUI visual behavior, or cross-engine parity.
