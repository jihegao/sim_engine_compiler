# E15.var10: ROSIZ above the documented bound

The accepted E15 explicit-three stock model has depot STSIZ4 and ROSIZ2. This case changes only depot ROSIZ to 6; the installed manual says the maximum is `STSIZ+1 = 5` (physical page 517).

The original [v1.0.0](../E15-var10-rosiz-upper-bound-v1.0.0/) contract expected a converter error and no valid result. SIMLOX instead issued warning #168, completed the simulation and wrote a valid SXO. That frozen contract failed and remains an **excluded diagnostic**. Its 11 native raw files and failed gate are preserved by byte pins.

This separately reviewed v1.0.1 extension makes one report-only export from the sealed SXO. It does not recalculate the candidate or accepted parent. The selected report shows 72 depot half-hour bins with nominal STSZ4, on-hand STOHA3 until hour 10 and 2 thereafter, NRO0 and NBO0 throughout. The candidate's native event log has no depot reorder or delivery after physical ID0 issues at hour 10; the accepted parent starts a two-item order at hour 10 and delivers IDs5/6 at hour 11. Mission, system, summary and aggregate stock report tables match the accepted parent; only ItemResults and ItemResultsTotal differ.

The [scope signoff](cli-scope-signoff-2026-10-05.md) and [evidence index](evidence-index.json) pin the source and the two local raw runs. The result is the **observed warning and no-reorder outcome for one invalid input**. It does not define supported policy behavior for out-of-range ROSIZ values.
