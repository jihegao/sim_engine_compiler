# E15.var10 v1.0.0: excluded strict negative diagnostic

The accepted E15 explicit-three stock-based DU model has depot STSIZ4, ROSIZ2 and initial on-hand3. This candidate changes only depot ROSIZ to 6, exceeding the installed manual's `STSIZ+1 = 5` limit (physical page 517).

The frozen contract required an explicit converter **error** tied to this row and no valid simulation result. The guarded native run instead reported Errors0, Warnings #108 and #168 (`Reorder size too large (ROSIZ > STSIZ+1): TEACH-DU-01`), Notes0, then completed calculation and wrote a nonempty SXO. Its exact 21 populated-table roundtrip and raw files are sealed. The runner correctly failed its predeclared gate. This version is `excluded_diagnostic`; its result must not be recast as an accepted error or invalid-output case.

A later version may independently review the warning and sealed result under a new contract. No recalculation of this candidate or accepted E15 parent is required for that source-bound review.
