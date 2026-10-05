# I07.var10 v1.0.0 — preserved strict-gate diagnostic

This frozen candidate tested a scheduled ROSIZ value at the existing
`TEACH-DU-01` / `BASE-01` stock row, which has no `ItemReorder` record. The
control has an all-null `ChangesStockAllocation` placeholder; the child
alone sets ROSIZ one at hour 5. The installed manual says ROSIZ at a
non-reorder location is ignored.

The guarded native pair passed 22 authored-table roundtrips and both
calculations completed with zero conversion errors. The control converter
emitted only logging warning #108. The child emitted #108 and explicit
warning **#172: “No reorder data defined. ROSIZ ignored. TEACH-DU-01 /
BASE-01.”** The predeclared sole-#108 warning gate therefore stopped the
runner before the child's selected report export. The immutable closure
records this failure and seals 22 local raw files. Control and child native
event logs are byte-identical, but this v1.0.0 run is an **excluded
diagnostic**, not a positive accepted case.

The completed child SXO can be used for a separately reviewed report-only
follow-up without recalculating this model. No v1.0.0 raw artifact or old
pin is edited or relabeled. The protected GUI PID13340/session1 was
preserved.
