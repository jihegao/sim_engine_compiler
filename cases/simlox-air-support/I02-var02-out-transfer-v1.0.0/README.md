# I02.var02 — scheduled OUT transfer from depot

This bounded case extends the accepted I02.var01 IN source. The parent moves
one LRU into `DEPOT-01` at hour 4, leaving two available physical spares.
The child adds one `ItemTransfer` row moving one LRU from `DEPOT-01` to
`<OUTSIDE>` at hour 6 with zero transfer duration. Its only other source
change is the description; 30 tables stay unchanged. The item remains tracked
with half-hour `ITEM` collection from the parent.

`build.py` and `describe_diff.py` reproduce and check the frozen source and
exact table delta. `check_roundtrip.py` checks the 22 populated authored
tables after native import/export. The guarded `run_native_ssh.ps1` uses the
session-0 SSH queue and preserves GUI PID 13340. `make_report_settings.py`
recreates a local proprietary selector from the pinned installed default, and
`probe_item_report_results_ssh.ps1` exports item-position tables from the
sealed SXO without recalculation. Native files and the `.sxs` selector stay
local, ignored by Git and SHA-256 sealed in `evidence-index.json`.

The observed `ItemResults` depot position has nominal `STSZ` and on-hand
`STOHA` of one before hour 4, two from hours 4–6, and one from hour 6 onward
until later ordinary demand changes on-hand stock. At hour 6 the OUT task
removes physical item ID 0. At hour 10, ordinary demand takes the remaining
spare ID 1; depot on-hand falls to zero while nominal stock remains one.
Repair of failed item ID 2 restores depot on-hand to one after hour 13.

This establishes one available-stock OUT within an IN-then-OUT sequence. It
does not establish an OUT-only scenario, unavailable-stock split or transfer
backorder, BETWEEN, nonzero delay, priority, reorder, procurement, GUI visual
behavior, or cross-engine parity.
