# I07.var09 time-to-stock strategy-switch rejection

This version tests one `ChangesItemReorder.ROINT` 16-to-0 switch on the accepted E15.var01 time-based reorder model. The attempted change is authored at hour 5, with the original one-hour `LEADT` explicitly repeated. The installed SIMLOX manual says strategy types cannot be switched through this table and that a change would take effect only after the original interval. No application time is inferred from a converter rejection.

The prior v1.0.0 run remains an excluded diagnostic. Its change row omitted `LEADT`, producing both #84 (undefined lead) and #375 (inconsistent `ROINT`). The separate v1.0.1 source changes only that row's `LEADT` from null to 1.0. Neither accepted E15 behavior nor the excluded run was recalculated.

One reviewed, guarded SSH session-0 run roundtripped all 22 authored populated tables exactly and reported Errors 1, Warnings 2, Notes 0. The sole error is #375 under `ChangesItemReorder` record 1 for `TEACH-DU-01/DEPOT-01`; the warnings are #108 and #376. The `.sxo` is four bytes and there is no event log or report. The result supports this installed converter's rejection of this one strategy-switch attempt. It does not prove runtime reorder behavior, reverse switching, other intervals or change times, GUI behavior, cross-engine equivalence, full I07.var09, I07, or Issue #18.

The local ignored `runs/` directories retain both immutable raw runs. The [evidence index](evidence-index.json) pins their bytes; the [contract](contract.json), [author replay](author-validation-2026-10-05.json), [signoff](cli-scope-signoff-2026-10-05.md), and independent reviews describe the bounded decision.
