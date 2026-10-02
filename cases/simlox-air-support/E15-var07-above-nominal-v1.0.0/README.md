# E15.var07: explicit opening stock above nominal

This bounded native CLI pair compares the [accepted E15 default arm](../E15-var07-explicit-istoh-v1.0.1/cli-scope-signoff-2026-10-02.md) with a frozen child that changes depot `StockAllocation.ISTOH` from omitted to 6. Nominal `STSIZ` is 4. The only other source change is `ProblemDescription.PDESC`; [exact-diff.json](exact-diff.json) records both cells. The [contract](contract.json) froze the predictions before the child native run.

The child [native input](native-input.json) and parent each have 21 populated authored tables. The child ran through guarded session-0 SSH import, export, calculation and JSON report, with exact round-trip and only logging warning #108. A second guarded export selected depot `ItemResults`. All local native raw outputs stay under ignored `runs/`; [evidence-index.json](evidence-index.json) seals their hashes.

The selected 72 half-hour bins show physical depot on-hand 6 before h10 and 5 afterward, against parent 4 then 3. Both keep nominal 4, ordinary backorder 0, and reorder count 0. The h10 depot issue and h12 base receipt occur in both. Selected system, aggregate stock and mission reports are equal. Three missions start, two succeed, and the aircraft ends ready. This accepts the explicit-above-nominal boundary of catalog E15.var07 for the one fixed seed and one-stock-position scope described in the [CLI signoff](cli-scope-signoff-2026-10-02.md).

Run `validate_native.py` to replay author checks against local sealed raw files. The independent checker and verdict are alongside it. The publication index points to this package; broader E15 and Issue #18 remain open.
