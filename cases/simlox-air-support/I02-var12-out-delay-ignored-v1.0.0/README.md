# I02.var12 — OUT transfer duration diagnostic

The catalog labels I02.var12 “OUT ignores delay.” This case tests that label
against the accepted I02.var02 available-stock one-unit OUT from `DEPOT-01`
to `<OUTSIDE>` at hour 6. The preceding one-unit IN at hour 4 stays fixed.
Only the OUT row’s `ItemTransfer.TFDT` changes from 0 to 2 hours, plus the
description; 30 other tables and the IN row are unchanged.

The installed manual says TFDT is ignored for OUT. The native physical log
shows a narrower result: the item leaves depot stock at hour 6 in both arms,
but the TFDT2 task reports transfer time two hours and arrives at
`<OUTSIDE>` at hour 8 instead of hour 6. All selected depot ItemResults and
other business reports match the zero-duration parent. This is a bounded
counterexample to the literal “ignored” wording. It does not measure an
outside receiving-stock position, and the delayed arrival has no observed
downstream consequence in this geometry.

`build.py` and `describe_diff.py` freeze the exact source delta.
`run_native_ssh.ps1` runs guarded session-0 native import, roundtrip,
calculation and default report. `make_report_settings.py` recreates the
proprietary depot selector locally; `report_native_ssh.ps1` exports from the
sealed SXO without recalculation. Raw native files and selector stay in
ignored `runs/`. `evidence-index.json` records local paths and hashes, and
author and independent read-only checkers replay the evidence.

The scope is one available OUT after IN, one item/depot, one seed and TFDT
0 versus 2. Standalone OUT, shortage/split, other values, GUI rendering and
cross-engine behavior remain unverified.
