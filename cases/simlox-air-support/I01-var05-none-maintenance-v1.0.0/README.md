# I01.var05: explicit `<NONE>` maintenance allocation — restricted diagnostic

This warning-bearing native pair tests the manual's `<NONE>` station value for a task-referenced ItemRepair record. It is **not** accepted as a complete reorder or item-conservation case.

Both arms derive from accepted I01.var01 and hold the `LRU-CM` task category, `BASE` task level, item/repair data, and one local spare at both stock POINTs fixed. The matching arm selects `AIR_BASIC`, whose MaintenanceAllocation row places `LRU-CM/BASE` at `BASE-01`. The `<NONE>` arm selects `AIR_NONE`, whose row places the same category and level at `<NONE>`. Only Control.APID and ProblemDescription differ between the two frozen sources. `ItemReorder` has no rows.

Both arms convert with zero errors, round-trip all 23 authored tables, experience the same h9.8829 critical LRU failure, take the spare at h10, restore aircraft readiness h10.5, and complete the later missions. In the matching arm, the failed original LRU begins direct repair h10.1667, completes h11.1667, and returns to local stock. In the `<NONE>` arm it arrives for maintenance but has no item DIRP task, completion, stock return, or reorder event. The local stock log remains at zero after the spare issue, and the native run emits warning #241, “ESS with incomplete repair of item at position: BASE-01 / TEACH-LRU-01.” The failed LRU's final disposition is unresolved.

Both raw reports have 72 aligned half-hour System/Stock bins and equal business report rows: one ordinary failure, half an hour of system repair occupancy, no aggregate backorder, later mission success, and terminal aircraft ready1. Those aggregate reports do not record the physical stock-return difference, so they cannot establish item conservation.

The installed manual's ItemReorder rules require a DU/PRU/DP/SPRU item and a DEPOT/STORE station. This model retains the accepted LRU at a WS base; adding a valid reorder route requires a separate source contrast. Run `build.py`, `describe_diff.py`, `validate_restricted.py`, and `review/independent_readonly.py` to check the frozen model and local sealed evidence. Raw artifacts stay under ignored `runs/`.
