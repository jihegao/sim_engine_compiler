# E10.var08 ignored fields on a subprofile wrapper, v1.0.0

This bounded case derives from the [accepted nested FIXED repeat](../E10-var05-nested-repeat-v1.0.0/README.md). The installed manual, physical p. 336, says `MINBS`, `TPTIM`, and `TPTIMD` are ignored when `STPRID` references a subprofile instead of a basic `FIXED` or `ONDEM` policy. It tests that rule with nontrivial wrapper values while retaining the child basic policy.

## Frozen delta

The accepted `DOWN-POLICY -> REPEAT-FIXED` wrapper at relative h8 still repeats twice at a three-hour interval. Only its `MINBS` null→7, `TPTIM` null→9 hours, and `TPTIMD` null→`<EXP>` change, plus `ProblemDescription`. The `REPEAT-FIXED -> FIXED` child remains `TPTIM=2` hours. All station links, item and stock data, failure/repair, missions, seed 1, 36-hour horizon, and half-hour report settings are unchanged. See the [pre-run contract](contract.json), [exact diff](exact-diff.json), and [input](native-input.json).

The strict acceptance gate requires native import/export of the authored fields, zero conversion errors, h8/h11 FIXED points, child two-hour physical transport, an event log byte identical to the accepted parent, and equality of every non-description report table. The accepted parent and installed executable/manual/dictionary fingerprints are frozen in the contract and guarded runner.

## Native observation

Fresh guarded session-0 SSH run `e10-var08-ignored-v100-ssh-20261003-01` completed import, export, calculation, JSON report, and exact 22-table authored roundtrip under `Global\SimloxIssue18NativeQueue` while preserving active GUI PID 13340. Converter result: **Errors 0, Warnings 2, Notes 0**. Warning #108 concerns the enabled log; warning #152 explicitly says `MINBS`, `TPTIM`, and `TPTIMD` are valid only for `FIXED`/`ONDEM` and the wrapper data are ignored. The fields remain in the roundtripped input, while the native event log is byte identical to the parent and all non-description report tables are structurally equal.

The h8 point cancels with zero items. One h10 spare demand queues to h11, travels for the child policy's two hours, arrives h13, clears a three-hour local backorder, and restores aircraft readiness h13.3333. Failed item serial 1 moves upward, is repaired and restocked at the depot; one mission aborts and two later missions succeed. All 72 half-hour System/Stock bins reconcile; terminal aircraft readiness is one and backorders are zero. No maintenance resources are authored or allocated.

This covers one subprofile wrapper, one repeated FIXED child, one demand and one seed. It does not establish other nested depths, ONDEM children, multiple demands, overlapping windows, GUI visuals, or cross-engine behavior. Full E10, E11 and Issue #18 remain open. Bulky raw artifacts stay under ignored local `runs/` and are sealed in the evidence index.
