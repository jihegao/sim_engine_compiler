# I07.var07 same-time ROSIZ and OUT: bounded CLI signoff

**Decision:** `native_behavior_accepted_cli_scope` for one simultaneous
hour 5 scheduled ROSIZ change and depot OUT transfer. It becomes
`reusable_published` only after merge to `simlox/main`. Full I07 and Issue
#18 remain open; K01/K08 GUI observations remain blocked.

The frozen pair derives from accepted E15 explicit-three and accepted I02
OUT schema. Accepted I07.var02 isolated ROSIZ behavior is a pinned
prerequisite. The paired business input differs only in the
`ChangesStockAllocation` all-null control placeholder versus child
`[AIR_BASIC,TEACH-DU-01,DEPOT-01,5,1,null]`. The installed manual physical
pages 515–517 state that a ROSIZ change alone does not immediately order,
that a transfer changes nominal stock but not configured ROSIZ, and that a
same-time transfer uses the new ROSIZ to evaluate reorder state. The
predeclared contract treated a child-only hour 5 order as a hypothesis.
Independent reviewers approved the contract and runner before execution.

The unique matched pair ran in eight serial session-0 SSH CLI stages under
`Global\SimloxIssue18NativeQueue`, preserving GUI PID13340/session1. Exact
pre-calculation roundtrip covered 23 authored populated tables in each arm.
Both converters returned Errors0/Warnings1 (only #108)/Notes0. Native SXO,
event logs and selected reports are valid and nonempty. The immutable
closure pins 24 local raw files and all before/after source bytes.

At hour 5 both arms transfer physical depot ID0 OUT, changing nominal four
to three and on-hand three to two. The control starts no order; the child
starts reorder task0 and receives one physical ID4 at hour 6. At hour 10
both arms send depot ID1 toward base, which receives it at hour 12. Control
reorder task0 delivers two new IDs5/6 at hour 11; child task1 delivers one
new ID6 at hour 11. The observed batch sizes are one, two and one; no
batch size was inferred from ROSIZ alone. Both end with three depot units,
and neither has a backorder. Every stock snapshot and all 72 selected
half-hour item bins per arm reconcile. Mission, system, summary and stock
aggregate report rows agree across arms. Author replay passes **421/421**
checks; independent raw and ledger review is filed separately.

This signoff covers one fixed seed, one existing stock-based discardable DU,
one available-stock zero-delay OUT, and one exact-time ROSIZ change. It does
not cover other event ties, unavailable stock, nonzero transfer time,
multiple locations/orders, time-based reorder, GUI or cross-engine behavior.
